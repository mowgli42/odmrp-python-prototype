"""Python reference ODMRP node (draft + ADRs 001–004)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from odmrp_sim.model.app_payload import AppPayload
from odmrp_sim.model.packets import (
    GroupId,
    JoinQueryHeader,
    JoinReplyEntry,
    NodeId,
    Packet,
    PacketKind,
    make_data_with_jq,
    make_join_reply,
)
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import FGEntry, InboxItem, NodeState, Position, RouteEntry, SourceSession
from odmrp_sim.protocol import seqnum
from odmrp_sim.protocol.tables import MessageCache
from odmrp_sim.sim.rng import SeededRng


@dataclass
class _PendingJR:
    group: GroupId
    entries: list[JoinReplyEntry]
    due: float


@dataclass
class PythonODMRPNode:
    """Time-driven pure-output ODMRP implementation."""

    node_id: NodeId = -1
    params: ProtocolParams = field(default_factory=ProtocolParams)
    pos: Position = field(default_factory=lambda: Position(0.0, 0.0))
    range: float = 130.0
    _rng: SeededRng | None = None
    _members: set[GroupId] = field(default_factory=set)
    _routes: dict[NodeId, RouteEntry] = field(default_factory=dict)
    _fg: dict[GroupId, FGEntry] = field(default_factory=dict)
    _cache: MessageCache = field(default_factory=MessageCache)
    _sessions: dict[GroupId, SourceSession] = field(default_factory=dict)
    _inbox: list[InboxItem] = field(default_factory=list)
    _jr_seq: int = 0
    _pending_jr: list[_PendingJR] = field(default_factory=list)
    _jr_sent: dict[GroupId, frozenset[tuple[NodeId, NodeId]]] = field(default_factory=dict)
    _queued_payloads: dict[GroupId, list[bytes]] = field(default_factory=dict)
    _now: float = 0.0
    # local delivery callbacks observed via inbox; transfers handled by host services

    def configure(self, node_id: NodeId, params: ProtocolParams, rng_seed: int) -> None:
        self.node_id = node_id
        self.params = params
        self._rng = SeededRng(rng_seed)
        self._cache = MessageCache(params.message_cache_size)

    def set_membership(self, group: GroupId, member: bool, now: float) -> list[Packet]:
        self._now = now
        if member:
            self._members.add(group)
        else:
            self._members.discard(group)
        return []

    def originate(self, group: GroupId, payload: bytes, now: float) -> list[Packet]:
        self._now = now
        session = self._sessions.get(group)
        if session is None:
            session = SourceSession(group=group, next_seq=1)
            self._sessions[group] = session
        session.last_data_at = now
        # Queue payload; send with JQ (piggyback)
        self._queued_payloads.setdefault(group, []).append(payload)
        return self._emit_join_query(group, now, force_payload=True)

    def receive(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]:
        self._now = now
        if packet.kind == PacketKind.JOIN_REPLY:
            return self._handle_join_reply(packet, previous_hop, now)
        if packet.kind in (PacketKind.JOIN_QUERY, PacketKind.DATA):
            return self._handle_data_or_jq(packet, previous_hop, now)
        return []

    def advance(self, now: float) -> list[Packet]:
        self._now = now
        out: list[Packet] = []
        # Fire due Join Reply delays
        still: list[_PendingJR] = []
        for p in self._pending_jr:
            if p.due <= now + 1e-12:
                out.extend(self._send_join_reply(p.group, p.entries, now))
            else:
                still.append(p)
        self._pending_jr = still

        # Soft-state expiry
        expired_routes = [s for s, e in self._routes.items() if e.expires_at <= now]
        for s in expired_routes:
            del self._routes[s]
        expired_fg = [g for g, e in self._fg.items() if e.expires_at <= now]
        for g in expired_fg:
            del self._fg[g]
            self._jr_sent.pop(g, None)

        # Source refresh / idle
        for group, session in list(self._sessions.items()):
            if session.next_refresh_at is not None and session.next_refresh_at <= now + 1e-12:
                idle = now - session.last_data_at
                if idle > self.params.source_idle_timeout and not self._queued_payloads.get(group):
                    session.next_refresh_at = None
                    continue
                out.extend(self._emit_join_query(group, now, force_payload=False))
        return out

    def next_timer(self) -> float | None:
        times: list[float] = []
        for p in self._pending_jr:
            times.append(p.due)
        for e in self._routes.values():
            times.append(e.expires_at)
        for e in self._fg.values():
            times.append(e.expires_at)
        for s in self._sessions.values():
            if s.next_refresh_at is not None:
                times.append(s.next_refresh_at)
        return min(times) if times else None

    def get_state(self) -> NodeState:
        return NodeState(
            id=self.node_id,
            pos=copy.deepcopy(self.pos),
            range=self.range,
            members=set(self._members),
            routes={k: copy.deepcopy(v) for k, v in self._routes.items()},
            forwarding_groups={k: copy.deepcopy(v) for k, v in self._fg.items()},
            last_seq_by_source={},
            message_cache_size=len(self._cache),
            sessions=[copy.deepcopy(s) for s in self._sessions.values()],
            inbox=list(self._inbox),
            jr_sent_this_refresh=dict(self._jr_sent),
        )

    # --- internals ---------------------------------------------------------

    def _emit_join_query(self, group: GroupId, now: float, *, force_payload: bool) -> list[Packet]:
        session = self._sessions.setdefault(group, SourceSession(group=group, next_seq=1))
        queue = self._queued_payloads.setdefault(group, [])
        if force_payload or queue:
            payload = queue.pop(0) if queue else b""
            piggybacked = True
        else:
            payload = b""
            piggybacked = False
        seq = session.next_seq
        session.next_seq = seqnum.next_seq(seq)
        session.last_data_at = now if payload else session.last_data_at
        session.next_refresh_at = now + self.params.route_refresh_interval
        # cache own transmission so we drop echoes
        self._cache.add(self.node_id, seq, now)
        pkt = make_data_with_jq(
            source=self.node_id,
            group=group,
            seq=seq,
            payload=payload,
            ttl=self.params.join_query_ttl,
            piggybacked=piggybacked,
        )
        # Reset JR suppression for new refresh cycle at receivers/intermediates is per-node;
        # at source we clear our own sent table for this group.
        self._jr_sent.pop(group, None)
        return [pkt]

    def _handle_data_or_jq(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]:
        out: list[Packet] = []
        has_jq = packet.join_query is not None or packet.kind == PacketKind.JOIN_QUERY

        if self._cache.contains(packet.source, packet.seq):
            return out  # duplicate — host may log drop
        self._cache.add(packet.source, packet.seq, now)

        if has_jq:
            # Backward learning (always on first sight of this seq)
            self._routes[packet.source] = RouteEntry(
                next_hop=previous_hop,
                seq=packet.seq,
                expires_at=now + self.params.route_timeout,
            )
            if packet.group in self._members:
                self._deliver(packet, now)
                # Schedule Join Reply
                entry = JoinReplyEntry(sender=packet.source, next_hop=previous_hop)
                due = now + self.params.jr_delay
                self._pending_jr.append(_PendingJR(group=packet.group, entries=[entry], due=due))
            # Rebroadcast if TTL remains
            if packet.ttl > 1:
                fwd = packet.copy_for_forward(previous_hop=self.node_id)
                # Keep kind JOIN_QUERY if header present
                if packet.join_query:
                    fwd.join_query = JoinQueryHeader(piggybacked=packet.join_query.piggybacked)
                out.append(fwd)
            return out

        # Pure DATA (no JQ header)
        if packet.group in self._members:
            self._deliver(packet, now)
        if self._is_fg(packet.group, packet.source) and packet.ttl > 1:
            out.append(packet.copy_for_forward(previous_hop=self.node_id))
        return out

    def _handle_join_reply(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]:
        matched = [e for e in packet.entries if e.next_hop == self.node_id]
        if not matched:
            return []

        # Entries whose sender is ourselves mean the JR has returned to the source:
        # mark mesh established, but the source is not an FG member (draft §5.1.6).
        for m in matched:
            if m.sender == self.node_id:
                sess = self._sessions.get(packet.group)
                if sess:
                    sess.mesh_established = True

        forward_matched = [m for m in matched if m.sender != self.node_id]
        if not forward_matched:
            return []

        # Become / refresh FG for the group (ADR-003)
        entry = self._fg.get(packet.group)
        if entry is None:
            entry = FGEntry(expires_at=now + self.params.fg_timeout, last_refresh=now)
            self._fg[packet.group] = entry
        else:
            entry.expires_at = now + self.params.fg_timeout
            entry.last_refresh = now
        for m in forward_matched:
            entry.refreshed_by.add(m.sender)

        # Build upstream JR from routing table
        upstream: list[JoinReplyEntry] = []
        for m in forward_matched:
            route = self._routes.get(m.sender)
            if route is None:
                continue
            upstream.append(JoinReplyEntry(sender=m.sender, next_hop=route.next_hop))

        if not upstream:
            return []

        # Suppression: once per refresh if table identical
        sig = frozenset((e.sender, e.next_hop) for e in upstream)
        if self._jr_sent.get(packet.group) == sig:
            return []
        return self._send_join_reply(packet.group, upstream, now, from_fg=True)

    def _send_join_reply(
        self,
        group: GroupId,
        entries: list[JoinReplyEntry],
        now: float,
        *,
        from_fg: bool = False,
    ) -> list[Packet]:
        sig = frozenset((e.sender, e.next_hop) for e in entries)
        if self._jr_sent.get(group) == sig:
            return []
        self._jr_sent[group] = sig
        self._jr_seq = seqnum.next_seq(self._jr_seq)
        # If we are an FG member already, mark F flag
        from_fg_node = from_fg or (group in self._fg)
        pkt = make_join_reply(
            source=self.node_id,
            group=group,
            seq=self._jr_seq,
            previous_hop=self.node_id,
            entries=entries,
            from_fg_node=from_fg_node,
            ttl=self.params.join_query_ttl,
        )
        return [pkt]

    def _is_fg(self, group: GroupId, source: NodeId) -> bool:
        if self.params.fg_scope == "source_group":
            key = f"{source}:{group}"
            return key in self._fg or group in self._fg
        return group in self._fg

    def _deliver(self, packet: Packet, now: float) -> None:
        if not packet.payload:
            return
        try:
            app = AppPayload.decode(packet.payload)
        except Exception:
            app = AppPayload(kind="text", message_id=f"raw-{packet.id}", body=packet.payload.decode("utf-8", errors="replace"))
        self._inbox.append(
            InboxItem(
                message_id=app.message_id,
                group=packet.group,
                source=packet.source,
                app_kind=app.kind,
                body=app.body,
                transfer_id=app.transfer_id,
                index=app.index,
                total=app.total,
                t=now,
            )
        )


def is_duplicate_drop(node: PythonODMRPNode, packet: Packet) -> bool:
    """Helper for host: would this packet be dropped as duplicate?"""
    return node._cache.contains(packet.source, packet.seq)
