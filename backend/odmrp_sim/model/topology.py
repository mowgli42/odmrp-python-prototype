"""Unit-disk topology with symmetric neighbour computation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from odmrp_sim.model.packets import NodeId
from odmrp_sim.model.state import Position


def _undirected(a: NodeId, b: NodeId) -> tuple[NodeId, NodeId]:
    return (a, b) if a < b else (b, a)


@dataclass
class TopoNode:
    id: NodeId
    pos: Position
    range: float


@dataclass
class Topology:
    default_range: float = 130.0
    nodes: dict[NodeId, TopoNode] = field(default_factory=dict)
    _neighbors: dict[NodeId, set[NodeId]] = field(default_factory=dict)
    # Undirected pairs forced down by a link model (e.g. Markov) while still in range.
    _disabled: set[tuple[NodeId, NodeId]] = field(default_factory=set)
    _on_change: list[Callable[[dict], None]] = field(default_factory=list, repr=False)

    def on_change(self, cb: Callable[[dict], None]) -> None:
        self._on_change.append(cb)

    def _emit(self, payload: dict) -> None:
        for cb in self._on_change:
            cb(payload)

    def add(self, node_id: NodeId, x: float, y: float, range_: float | None = None) -> TopoNode:
        r = self.default_range if range_ is None else range_
        node = TopoNode(id=node_id, pos=Position(x, y), range=r)
        self.nodes[node_id] = node
        self._recompute()
        self._emit({"op": "add", "a": node_id, "pos": {"x": x, "y": y}})
        return node

    def remove(self, node_id: NodeId) -> None:
        if node_id not in self.nodes:
            return
        del self.nodes[node_id]
        self._disabled = {p for p in self._disabled if node_id not in p}
        self._recompute()
        self._emit({"op": "remove", "a": node_id})

    def move(self, node_id: NodeId, x: float, y: float) -> list[tuple[str, NodeId, NodeId]]:
        node = self.nodes[node_id]
        old = set(self.neighbors_of(node_id))
        node.pos = Position(x, y)
        self._recompute()
        new = set(self.neighbors_of(node_id))
        events: list[tuple[str, NodeId, NodeId]] = []
        for n in old - new:
            events.append(("link_down", node_id, n))
            self._emit({"op": "link_down", "a": node_id, "b": n})
        for n in new - old:
            events.append(("link_up", node_id, n))
            self._emit({"op": "link_up", "a": node_id, "b": n})
        self._emit({"op": "move", "a": node_id, "pos": {"x": x, "y": y}})
        return events

    def clear(self) -> None:
        self.nodes.clear()
        self._neighbors.clear()
        self._disabled.clear()

    def distance(self, a: NodeId, b: NodeId) -> float:
        pa, pb = self.nodes[a].pos, self.nodes[b].pos
        return math.hypot(pa.x - pb.x, pa.y - pb.y)

    def is_disabled(self, a: NodeId, b: NodeId) -> bool:
        return _undirected(a, b) in self._disabled

    def disable_link(self, a: NodeId, b: NodeId) -> bool:
        """Force a geometrically eligible link down. Returns True if state changed."""
        key = _undirected(a, b)
        if key in self._disabled:
            return False
        was = key[1] in self.neighbors_of(key[0])
        self._disabled.add(key)
        self._recompute()
        if was:
            self._emit({"op": "link_down", "a": key[0], "b": key[1], "reason": "link_model"})
        return True

    def enable_link(self, a: NodeId, b: NodeId) -> bool:
        """Clear a forced-down mask. Returns True if the active link set changed."""
        key = _undirected(a, b)
        if key not in self._disabled:
            return False
        self._disabled.discard(key)
        self._recompute()
        if key[0] in self.nodes and key[1] in self.nodes:
            if self._geometrically_linked(self.nodes[key[0]], self.nodes[key[1]]):
                if key[1] in self.neighbors_of(key[0]):
                    self._emit({"op": "link_up", "a": key[0], "b": key[1], "reason": "link_model"})
                    return True
        return True

    def _geometrically_linked(self, a: TopoNode, b: TopoNode) -> bool:
        d = math.hypot(a.pos.x - b.pos.x, a.pos.y - b.pos.y)
        return d <= min(a.range, b.range)

    def _linked(self, a: TopoNode, b: TopoNode) -> bool:
        if self.is_disabled(a.id, b.id):
            return False
        return self._geometrically_linked(a, b)

    def geometric_pairs(self) -> list[tuple[NodeId, NodeId]]:
        """Undirected pairs currently within radio range (ignoring link-model masks)."""
        ids = list(self.nodes)
        out: list[tuple[NodeId, NodeId]] = []
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if self._geometrically_linked(self.nodes[a], self.nodes[b]):
                    out.append(_undirected(a, b))
        out.sort()
        return out

    def _recompute(self) -> None:
        ids = list(self.nodes)
        neigh: dict[NodeId, set[NodeId]] = {i: set() for i in ids}
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if self._linked(self.nodes[a], self.nodes[b]):
                    neigh[a].add(b)
                    neigh[b].add(a)
        self._neighbors = neigh

    def neighbors_of(self, node_id: NodeId) -> set[NodeId]:
        return set(self._neighbors.get(node_id, ()))

    def links(self) -> list[list[NodeId]]:
        seen: set[tuple[NodeId, NodeId]] = set()
        out: list[list[NodeId]] = []
        for a, ns in self._neighbors.items():
            for b in ns:
                key = (a, b) if a < b else (b, a)
                if key not in seen:
                    seen.add(key)
                    out.append([key[0], key[1]])
        out.sort()
        return out

    def to_dict(self) -> dict:
        return {
            "range": self.default_range,
            "nodes": [
                {"id": n.id, "x": n.pos.x, "y": n.pos.y, "range": n.range}
                for n in sorted(self.nodes.values(), key=lambda n: n.id)
            ],
            "links": self.links(),
        }
