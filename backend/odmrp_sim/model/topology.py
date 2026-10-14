"""Unit-disk topology with symmetric neighbour computation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from odmrp_sim.model.packets import NodeId
from odmrp_sim.model.state import Position


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

    def distance(self, a: NodeId, b: NodeId) -> float:
        pa, pb = self.nodes[a].pos, self.nodes[b].pos
        return math.hypot(pa.x - pb.x, pa.y - pb.y)

    def _linked(self, a: TopoNode, b: TopoNode) -> bool:
        d = math.hypot(a.pos.x - b.pos.x, a.pos.y - b.pos.y)
        return d <= min(a.range, b.range)

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
