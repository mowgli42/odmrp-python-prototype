"""NodeHost: wraps an ODMRPNode, owns position, transmits via Medium."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odmrp_sim.model.packets import GroupId, NodeId, Packet, PacketKind
from odmrp_sim.model.state import Position
from odmrp_sim.protocol.external_node import ExternalProcessNode
from odmrp_sim.protocol.python_node import PythonODMRPNode

if TYPE_CHECKING:
    from odmrp_sim.events.bus import EventBus
    from odmrp_sim.model.params import ProtocolParams
    from odmrp_sim.protocol.interface import ODMRPNode
    from odmrp_sim.sim.medium import Medium


class NodeHost:
    def __init__(
        self,
        node_id: NodeId,
        impl: ODMRPNode,
        params: ProtocolParams,
        bus: EventBus,
        medium: Medium,
        rng_seed: int,
        pos: Position,
        range_: float,
        *,
        impl_name: str = "python",
        log_path: Path | None = None,
    ) -> None:
        self.id = node_id
        self.impl = impl
        self.params = params
        self.bus = bus
        self.medium = medium
        self.pos = pos
        self.range = range_
        self.impl_name = impl_name
        self.log_path = log_path
        impl.configure(node_id, params, rng_seed)
        if isinstance(impl, (PythonODMRPNode, ExternalProcessNode)):
            impl.pos = pos
            impl.range = range_

    def set_membership(self, group: GroupId, member: bool, now: float) -> None:
        pkts = self.impl.set_membership(group, member, now)
        self.bus.emit(now, self.id, "state.member", group=group, member=member)
        self._tx_all(pkts, now)

    def originate(self, group: GroupId, payload: bytes, now: float) -> None:
        before = self.impl.get_state()
        pkts = self.impl.originate(group, payload, now)
        self._tx_all(pkts, now)
        self._diff_state(before, now)

    def on_receive(self, packet: Packet, previous_hop: NodeId, now: float) -> None:
        # SA/JREAP stream chunks: consume-while-forward outside ODMRP FG rebroadcast
        sa = self._sa_feed()
        if sa is not None and sa.handle_packet(self.id, packet, previous_hop, now):
            return
        before = self.impl.get_state()
        # Duplicate check for drop tracing (Python node only)
        if isinstance(self.impl, PythonODMRPNode) and packet.kind != PacketKind.JOIN_REPLY:
            if self.impl._cache.contains(packet.source, packet.seq):
                self.bus.emit(now, self.id, "drop", packet_id=packet.id, reason="duplicate")
                return
        pkts = self.impl.receive(packet, previous_hop, now)
        after = self.impl.get_state()
        # Local deliveries
        if len(after.inbox) > len(before.inbox):
            for item in after.inbox[len(before.inbox) :]:
                self.bus.emit(
                    now,
                    self.id,
                    "deliver",
                    packet_id=packet.id,
                    message_id=item.message_id,
                    group=item.group,
                    app_kind=item.app_kind,
                    index=item.index,
                    total=item.total,
                )
        # Drop if JR unmatched and nothing tx'd — optional
        if packet.kind == PacketKind.JOIN_REPLY and not pkts:
            # either unmatched or suppressed — not necessarily a drop
            pass
        if packet.kind == PacketKind.DATA and not pkts:
            if isinstance(self.impl, PythonODMRPNode) and not self.impl._is_fg(packet.group, packet.source):
                if packet.group not in self.impl._members:
                    self.bus.emit(now, self.id, "drop", packet_id=packet.id, reason="not_fg")
        self._tx_all(pkts, now)
        self._diff_state(before, now)

    def advance(self, now: float) -> None:
        before = self.impl.get_state()
        pkts = self.impl.advance(now)
        self._tx_all(pkts, now)
        self._diff_state(before, now)

    def next_timer(self) -> float | None:
        return self.impl.next_timer()

    def get_state(self):
        st = self.impl.get_state()
        st.pos = self.pos
        st.range = self.range
        return st

    def _tx_all(self, packets: list[Packet], now: float) -> None:
        """All ODMRP TX (JQ / JR / DATA) exits only via neighbor-send."""
        for pkt in packets:
            if pkt.previous_hop < 0:
                pkt.previous_hop = self.id
            self.medium.neighbor_send(self.id, pkt, now)

    def _sa_feed(self):
        """Resolve SaFeedService from the owning engine when present."""
        # Medium.on_deliver is bound to SimulationEngine._on_deliver
        cb = getattr(self.medium, "on_deliver", None)
        if cb is None:
            return None
        eng = getattr(cb, "__self__", None)
        return getattr(eng, "sa_feed", None) if eng is not None else None

    def _diff_state(self, before, now: float) -> None:
        after = self.impl.get_state()
        for src, route in after.routes.items():
            old = before.routes.get(src)
            if old is None:
                self.bus.emit(
                    now, self.id, "state.route",
                    source=src, next_hop=route.next_hop, seq=route.seq,
                    expires_at=route.expires_at, op="set",
                )
            elif old.seq != route.seq or old.next_hop != route.next_hop:
                self.bus.emit(
                    now, self.id, "state.route",
                    source=src, next_hop=route.next_hop, seq=route.seq,
                    expires_at=route.expires_at, op="refresh",
                )
        for src in set(before.routes) - set(after.routes):
            self.bus.emit(now, self.id, "state.route", source=src, op="expire", next_hop=-1, seq=0, expires_at=now)
        for g, fg in after.forwarding_groups.items():
            old = before.forwarding_groups.get(g)
            if old is None:
                self.bus.emit(
                    now, self.id, "state.fg",
                    group=g, expires_at=fg.expires_at,
                    refreshed_by=sorted(fg.refreshed_by), op="set",
                )
            elif old.expires_at != fg.expires_at:
                self.bus.emit(
                    now, self.id, "state.fg",
                    group=g, expires_at=fg.expires_at,
                    refreshed_by=sorted(fg.refreshed_by), op="refresh",
                )
        for g in set(before.forwarding_groups) - set(after.forwarding_groups):
            self.bus.emit(now, self.id, "state.fg", group=g, expires_at=now, refreshed_by=[], op="expire")
