"""Packet model — Join Query piggyback (ADR-002), Join Reply table (ADR-004)."""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

NodeId = int
GroupId = str
PacketId = int

_packet_ids = itertools.count(1)


def next_packet_id() -> PacketId:
    return next(_packet_ids)


def reset_packet_ids(start: int = 1) -> None:
    global _packet_ids
    _packet_ids = itertools.count(start)


class PacketKind(str, Enum):
    JOIN_QUERY = "JOIN_QUERY"
    JOIN_REPLY = "JOIN_REPLY"
    DATA = "DATA"


@dataclass
class MobilityInfo:
    velocity: float = 0.0
    direction: float = 0.0


@dataclass
class JoinQueryHeader:
    piggybacked: bool = True
    mobility: MobilityInfo | None = None
    min_let: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "piggybacked": self.piggybacked,
            "mobility": asdict(self.mobility) if self.mobility else None,
            "min_let": self.min_let,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> JoinQueryHeader | None:
        if not d:
            return None
        mob = d.get("mobility")
        return cls(
            piggybacked=bool(d.get("piggybacked", True)),
            mobility=MobilityInfo(**mob) if mob else None,
            min_let=d.get("min_let"),
        )


@dataclass
class JoinReplyEntry:
    sender: NodeId
    next_hop: NodeId
    route_expiration: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> JoinReplyEntry:
        return cls(
            sender=int(d["sender"]),
            next_hop=int(d["next_hop"]),
            route_expiration=d.get("route_expiration"),
        )


@dataclass
class Packet:
    kind: PacketKind
    source: NodeId
    group: GroupId
    seq: int
    previous_hop: NodeId
    ttl: int = 32
    hop_count: int = 0
    id: PacketId = field(default_factory=next_packet_id)
    # DATA / JOIN_QUERY fields
    join_query: JoinQueryHeader | None = None
    payload: bytes = b""
    # JOIN_REPLY fields
    ack_request: bool = False
    from_fg_node: bool = False
    entries: list[JoinReplyEntry] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.entries)

    def copy_for_forward(self, previous_hop: NodeId, *, ttl: int | None = None) -> Packet:
        return Packet(
            kind=self.kind,
            source=self.source,
            group=self.group,
            seq=self.seq,
            previous_hop=previous_hop,
            ttl=self.ttl - 1 if ttl is None else ttl,
            hop_count=self.hop_count + 1,
            join_query=self.join_query,
            payload=self.payload,
            ack_request=self.ack_request,
            from_fg_node=self.from_fg_node,
            entries=[JoinReplyEntry(e.sender, e.next_hop, e.route_expiration) for e in self.entries],
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind.value,
            "source": self.source,
            "group": self.group,
            "seq": self.seq,
            "previous_hop": self.previous_hop,
            "ttl": self.ttl,
            "hop_count": self.hop_count,
        }
        if self.kind in (PacketKind.JOIN_QUERY, PacketKind.DATA):
            d["join_query"] = self.join_query.to_dict() if self.join_query else None
            d["payload_len"] = len(self.payload)
            # Keep a short printable preview for traces / UI
            try:
                d["payload_preview"] = self.payload[:64].decode("utf-8", errors="replace")
            except Exception:
                d["payload_preview"] = ""
        if self.kind == PacketKind.JOIN_REPLY:
            d["ack_request"] = self.ack_request
            d["from_fg_node"] = self.from_fg_node
            d["count"] = self.count
            d["entries"] = [e.to_dict() for e in self.entries]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Packet:
        kind = PacketKind(d["kind"])
        entries = [JoinReplyEntry.from_dict(e) for e in d.get("entries", [])]
        return cls(
            id=int(d.get("id", next_packet_id())),
            kind=kind,
            source=int(d["source"]),
            group=str(d["group"]),
            seq=int(d["seq"]),
            previous_hop=int(d["previous_hop"]),
            ttl=int(d.get("ttl", 32)),
            hop_count=int(d.get("hop_count", 0)),
            join_query=JoinQueryHeader.from_dict(d.get("join_query")),
            payload=d.get("payload", b"") if isinstance(d.get("payload"), (bytes, bytearray)) else b"",
            ack_request=bool(d.get("ack_request", False)),
            from_fg_node=bool(d.get("from_fg_node", False)),
            entries=entries,
        )


def make_data_with_jq(
    *,
    source: NodeId,
    group: GroupId,
    seq: int,
    payload: bytes,
    ttl: int,
    piggybacked: bool = True,
) -> Packet:
    return Packet(
        kind=PacketKind.JOIN_QUERY if True else PacketKind.DATA,
        source=source,
        group=group,
        seq=seq,
        previous_hop=source,
        ttl=ttl,
        hop_count=0,
        join_query=JoinQueryHeader(piggybacked=piggybacked),
        payload=payload,
    )


def make_join_reply(
    *,
    source: NodeId,
    group: GroupId,
    seq: int,
    previous_hop: NodeId,
    entries: list[JoinReplyEntry],
    from_fg_node: bool = False,
    ack_request: bool = False,
    ttl: int = 32,
) -> Packet:
    return Packet(
        kind=PacketKind.JOIN_REPLY,
        source=source,
        group=group,
        seq=seq,
        previous_hop=previous_hop,
        ttl=ttl,
        hop_count=0,
        ack_request=ack_request,
        from_fg_node=from_fg_node,
        entries=entries,
    )
