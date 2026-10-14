"""Seeded per-node RNG substreams for deterministic jitter."""

from __future__ import annotations

import hashlib
import random
from typing import Iterator


def derive_seed(master: int, *parts: int | str) -> int:
    h = hashlib.sha256()
    h.update(str(master).encode())
    for p in parts:
        h.update(b"\0")
        h.update(str(p).encode())
    return int.from_bytes(h.digest()[:8], "big")


class SeededRng:
    def __init__(self, master_seed: int) -> None:
        self.master = master_seed
        self._streams: dict[tuple, random.Random] = {}

    def stream(self, *parts: int | str) -> random.Random:
        key = tuple(parts)
        if key not in self._streams:
            self._streams[key] = random.Random(derive_seed(self.master, *parts))
        return self._streams[key]

    def uniform(self, *parts: int | str, low: float = 0.0, high: float = 1.0) -> float:
        return self.stream(*parts).uniform(low, high)
