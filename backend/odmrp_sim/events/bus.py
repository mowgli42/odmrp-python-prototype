"""In-process event bus + ring buffer for traces (ADR-006)."""

from __future__ import annotations

import itertools
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass
class TraceEvent:
    t: float
    seq: int
    node: int
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {"t": self.t, "seq": self.seq, "node": self.node, "kind": self.kind}
        d.update(self.payload)
        return d


class EventBus:
    def __init__(self, capacity: int = 50_000) -> None:
        self._seq = itertools.count(1)
        self.ring: deque[TraceEvent] = deque(maxlen=capacity)
        self._listeners: list[Callable[[TraceEvent], None]] = []
        self._file: Any = None

    def subscribe(self, cb: Callable[[TraceEvent], None]) -> None:
        self._listeners.append(cb)

    def unsubscribe(self, cb: Callable[[TraceEvent], None]) -> None:
        self._listeners = [c for c in self._listeners if c is not cb]

    def open_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", encoding="utf-8")

    def close_file(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def reset(self) -> None:
        self._seq = itertools.count(1)
        self.ring.clear()

    def emit(self, t: float, node: int, kind: str, **payload: Any) -> TraceEvent:
        ev = TraceEvent(t=t, seq=next(self._seq), node=node, kind=kind, payload=payload)
        self.ring.append(ev)
        if self._file:
            self._file.write(json.dumps(ev.to_dict(), separators=(",", ":")) + "\n")
            self._file.flush()
        for cb in list(self._listeners):
            cb(ev)
        return ev

    def after(self, after_seq: int, *, kinds: Iterable[str] | None = None, node: int | None = None, limit: int = 1000) -> list[dict]:
        kind_set = set(kinds) if kinds else None
        out: list[dict] = []
        for ev in self.ring:
            if ev.seq <= after_seq:
                continue
            if kind_set and ev.kind not in kind_set:
                continue
            if node is not None and ev.node != node:
                continue
            out.append(ev.to_dict())
            if len(out) >= limit:
                break
        return out

    @property
    def last_seq(self) -> int:
        return self.ring[-1].seq if self.ring else 0

    def all_dicts(self) -> list[dict]:
        return [e.to_dict() for e in self.ring]
