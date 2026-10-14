"""Protocol and simulation parameters (ADR-003 fg_scope)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Literal


FgScope = Literal["group", "source_group"]


@dataclass
class ProtocolParams:
    route_refresh_interval: float = 3.0
    fg_timeout: float = 9.0
    route_timeout: float = 9.0
    source_idle_timeout: float = 3.0
    join_query_ttl: int = 32
    jq_jitter: float = 0.010
    jr_delay: float = 0.025
    hop_delay: float = 0.001
    message_cache_size: int = 1024
    fg_scope: FgScope = "group"
    chunk_size: int = 1024

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ProtocolParams:
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
