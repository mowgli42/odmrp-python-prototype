"""RFC 1982 serial-number arithmetic for uint32 sequence numbers (ADR-001)."""

from __future__ import annotations

MOD = 1 << 32
HALF = 1 << 31


def normalize(n: int) -> int:
    return n % MOD


def compare(a: int, b: int) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b (serial)."""
    a, b = normalize(a), normalize(b)
    if a == b:
        return 0
    diff = (a - b) % MOD
    if diff == 0:
        return 0
    if diff < HALF:
        return 1  # a is fresher / greater
    return -1


def is_fresher(new: int, old: int) -> bool:
    return compare(new, old) > 0


def is_duplicate(a: int, b: int) -> bool:
    return normalize(a) == normalize(b)


def next_seq(n: int) -> int:
    return normalize(n + 1)
