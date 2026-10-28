"""Address book + logical neighbor relations for IPsec-tunnel overlay ODMRP.

Inspired by Commlink-Directory Contact/Capability/CommLink and
Commlink-Schedule Asset lists. Neighbors are soft-state tunnel peers —
not IP multicast/broadcast adjacency.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from odmrp_sim.model.packets import NodeId

NeighborStatus = Literal["up", "down", "pending", "expired", "recommended"]
NeighborReason = Literal[
    "configured",
    "discovered",
    "super_node",
    "geo",
    "capability",
    "manual",
    "expired",
]


@dataclass
class NodeCapabilities:
    """Capability flags for an overlay node."""

    is_super_node: bool = False
    can_stage_products: bool = False
    has_satcom: bool = False
    has_los_radio: bool = False
    max_tunnels: int | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> NodeCapabilities:
        if not d:
            return cls()
        return cls(
            is_super_node=bool(d.get("is_super_node", False)),
            can_stage_products=bool(d.get("can_stage_products", False)),
            has_satcom=bool(d.get("has_satcom", False)),
            has_los_radio=bool(d.get("has_los_radio", False)),
            max_tunnels=d.get("max_tunnels"),
            tags=[str(t) for t in d.get("tags", [])],
        )


@dataclass
class NeighborRelation:
    """One logical neighbor / tunnel peer for a node."""

    peer_id: NodeId
    tunnel_endpoint: str  # URI or host:port, e.g. ipsec://10.0.0.5:500
    status: NeighborStatus = "pending"
    priority: int = 100  # lower = preferred
    reason: NeighborReason = "configured"
    expires_at: float | None = None  # sim time; None = no soft-state expiry
    link_id: str | None = None
    last_refresh: float = 0.0

    def is_active(self, now: float) -> bool:
        if self.status in ("down", "expired"):
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return self.status in ("up", "pending", "recommended")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NeighborRelation:
        return cls(
            peer_id=int(d["peer_id"]),
            tunnel_endpoint=str(d["tunnel_endpoint"]),
            status=str(d.get("status", "pending")),  # type: ignore[arg-type]
            priority=int(d.get("priority", 100)),
            reason=str(d.get("reason", "configured")),  # type: ignore[arg-type]
            expires_at=float(d["expires_at"]) if d.get("expires_at") is not None else None,
            link_id=d.get("link_id"),
            last_refresh=float(d.get("last_refresh", 0.0)),
        )


@dataclass
class AddressBookEntry:
    """One node in the overlay address book."""

    node_id: NodeId
    callsign: str = ""
    name: str = ""
    platform: str = "mobile"  # site | mobile | aircraft
    tunnel_endpoint: str = ""  # this node's own underlay endpoint
    capabilities: NodeCapabilities = field(default_factory=NodeCapabilities)
    neighbors: list[NeighborRelation] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    position: dict[str, float] | None = None  # optional lat/lon/alt or x/y
    status: str = "active"
    addressbook_ref: str | None = None  # Commlink-Directory Contact/@id

    def active_neighbors(self, now: float = 0.0) -> list[NeighborRelation]:
        return [n for n in self.neighbors if n.is_active(now)]

    def neighbor_ids(self, now: float = 0.0) -> list[NodeId]:
        return [n.peer_id for n in self.active_neighbors(now)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "callsign": self.callsign,
            "name": self.name,
            "platform": self.platform,
            "tunnel_endpoint": self.tunnel_endpoint,
            "capabilities": self.capabilities.to_dict(),
            "neighbors": [n.to_dict() for n in self.neighbors],
            "groups": list(self.groups),
            "position": self.position,
            "status": self.status,
            "addressbook_ref": self.addressbook_ref,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AddressBookEntry:
        return cls(
            node_id=int(d["node_id"]),
            callsign=str(d.get("callsign") or d.get("name") or f"n{d['node_id']}"),
            name=str(d.get("name") or ""),
            platform=str(d.get("platform", "mobile")),
            tunnel_endpoint=str(d.get("tunnel_endpoint", "")),
            capabilities=NodeCapabilities.from_dict(d.get("capabilities")),
            neighbors=[NeighborRelation.from_dict(n) for n in d.get("neighbors", [])],
            groups=[str(g) for g in d.get("groups", [])],
            position=d.get("position"),
            status=str(d.get("status", "active")),
            addressbook_ref=d.get("addressbook_ref"),
        )


@dataclass
class AddressBook:
    """Collection of overlay node entries + metadata."""

    name: str = "default"
    version: str = "1.0"
    nodes: dict[NodeId, AddressBookEntry] = field(default_factory=dict)
    description: str = ""

    def upsert(self, entry: AddressBookEntry) -> None:
        self.nodes[entry.node_id] = entry

    def get(self, node_id: NodeId) -> AddressBookEntry | None:
        return self.nodes.get(node_id)

    def super_nodes(self) -> list[AddressBookEntry]:
        return [e for e in self.nodes.values() if e.capabilities.is_super_node]

    def logical_links(self, now: float = 0.0) -> list[list[NodeId]]:
        """Undirected unique active neighbor edges for visualization."""
        seen: set[tuple[NodeId, NodeId]] = set()
        out: list[list[NodeId]] = []
        for entry in self.nodes.values():
            for nb in entry.active_neighbors(now):
                a, b = entry.node_id, nb.peer_id
                key = (a, b) if a < b else (b, a)
                if key not in seen:
                    seen.add(key)
                    out.append([key[0], key[1]])
        out.sort()
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "nodes": [e.to_dict() for e in sorted(self.nodes.values(), key=lambda e: e.node_id)],
            "logical_links": self.logical_links(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AddressBook:
        book = cls(
            name=str(d.get("name", "default")),
            version=str(d.get("version", "1.0")),
            description=str(d.get("description", "")),
        )
        for raw in d.get("nodes", []):
            entry = AddressBookEntry.from_dict(raw)
            book.upsert(entry)
        return book

    def export_neighbors(self) -> dict[str, Any]:
        """Export only neighbor relations (importable edge list)."""
        edges = []
        for entry in sorted(self.nodes.values(), key=lambda e: e.node_id):
            for nb in entry.neighbors:
                edges.append(
                    {
                        "from": entry.node_id,
                        "to": nb.peer_id,
                        **{k: v for k, v in nb.to_dict().items() if k != "peer_id"},
                    }
                )
        return {"name": self.name, "version": self.version, "edges": edges}

    def import_neighbors(self, payload: dict[str, Any], *, replace: bool = False) -> int:
        """Import neighbor relations. Returns count of edges applied."""
        count = 0
        for edge in payload.get("edges", []):
            src = int(edge["from"])
            peer = int(edge["to"])
            entry = self.nodes.get(src)
            if entry is None:
                entry = AddressBookEntry(node_id=src, callsign=f"n{src}")
                self.upsert(entry)
            rel = NeighborRelation.from_dict({**edge, "peer_id": peer})
            if replace:
                entry.neighbors = [n for n in entry.neighbors if n.peer_id != peer]
            else:
                entry.neighbors = [n for n in entry.neighbors if n.peer_id != peer]
            entry.neighbors.append(rel)
            count += 1
        return count
