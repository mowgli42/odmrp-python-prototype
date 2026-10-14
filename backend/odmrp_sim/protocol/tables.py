"""Message cache (duplicate detection) and helpers."""

from __future__ import annotations

from collections import OrderedDict

from odmrp_sim.model.packets import NodeId
from odmrp_sim.protocol import seqnum


class MessageCache:
    def __init__(self, capacity: int = 1024) -> None:
        self.capacity = capacity
        self._store: OrderedDict[tuple[NodeId, int], float] = OrderedDict()

    def __len__(self) -> int:
        return len(self._store)

    def contains(self, source: NodeId, seq: int) -> bool:
        return (source, seqnum.normalize(seq)) in self._store

    def add(self, source: NodeId, seq: int, now: float) -> None:
        key = (source, seqnum.normalize(seq))
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = now
            return
        self._store[key] = now
        while len(self._store) > self.capacity:
            self._store.popitem(last=False)
