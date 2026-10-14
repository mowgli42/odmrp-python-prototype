"""Per-node observable state and table entry types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from odmrp_sim.model.packets import GroupId, NodeId


@dataclass
class Position:
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass
class RouteEntry:
    next_hop: NodeId
    seq: int
    expires_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FGEntry:
    expires_at: float
    refreshed_by: set[NodeId] = field(default_factory=set)
    last_refresh: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "expires_at": self.expires_at,
            "refreshed_by": sorted(self.refreshed_by),
            "last_refresh": self.last_refresh,
        }


@dataclass
class SourceSession:
    group: GroupId
    next_seq: int = 1
    last_data_at: float = 0.0
    next_refresh_at: float | None = None
    mesh_established: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InboxItem:
    message_id: str
    group: GroupId
    source: NodeId
    app_kind: str
    body: str | None = None
    transfer_id: str | None = None
    index: int | None = None
    total: int | None = None
    t: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NodeState:
    id: NodeId
    pos: Position
    range: float
    members: set[GroupId] = field(default_factory=set)
    routes: dict[NodeId, RouteEntry] = field(default_factory=dict)
    forwarding_groups: dict[GroupId, FGEntry] = field(default_factory=dict)
    last_seq_by_source: dict[NodeId, int] = field(default_factory=dict)
    message_cache_size: int = 0
    sessions: list[SourceSession] = field(default_factory=list)
    inbox: list[InboxItem] = field(default_factory=list)
    jr_sent_this_refresh: dict[GroupId, frozenset[tuple[NodeId, NodeId]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pos": self.pos.to_dict(),
            "range": self.range,
            "members": sorted(self.members),
            "routes": {str(k): v.to_dict() for k, v in self.routes.items()},
            "forwarding_groups": {k: v.to_dict() for k, v in self.forwarding_groups.items()},
            "last_seq_by_source": {str(k): v for k, v in self.last_seq_by_source.items()},
            "message_cache_size": self.message_cache_size,
            "sessions": [s.to_dict() for s in self.sessions],
            "inbox": [i.to_dict() for i in self.inbox],
            "fg": sorted(self.forwarding_groups.keys()),
        }
