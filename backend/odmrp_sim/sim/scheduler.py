"""Discrete-event scheduler ordered by (t, seq, node)."""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(order=True)
class Event:
    t: float
    seq: int
    node: int
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)
    callback: Callable[["Event"], None] | None = field(default=None, compare=False, repr=False)


class Scheduler:
    def __init__(self) -> None:
        self._heap: list[Event] = []
        self._seq = itertools.count(0)
        self.now: float = 0.0

    def reset(self) -> None:
        self._heap.clear()
        self._seq = itertools.count(0)
        self.now = 0.0

    def schedule(
        self,
        t: float,
        kind: str,
        *,
        node: int = -1,
        payload: dict[str, Any] | None = None,
        callback: Callable[[Event], None] | None = None,
    ) -> Event:
        if t < self.now:
            t = self.now
        ev = Event(
            t=t,
            seq=next(self._seq),
            node=node,
            kind=kind,
            payload=payload or {},
            callback=callback,
        )
        heapq.heappush(self._heap, ev)
        return ev

    def peek(self) -> Event | None:
        return self._heap[0] if self._heap else None

    def pop(self) -> Event | None:
        if not self._heap:
            return None
        ev = heapq.heappop(self._heap)
        self.now = ev.t
        return ev

    def __len__(self) -> int:
        return len(self._heap)

    def run_until(self, until: float, handler: Callable[[Event], None]) -> int:
        """Pop and handle events with t <= until. Returns count handled."""
        n = 0
        while self._heap and self._heap[0].t <= until + 1e-12:
            ev = self.pop()
            assert ev is not None
            if ev.callback:
                ev.callback(ev)
            handler(ev)
            n += 1
        self.now = max(self.now, until)
        return n
