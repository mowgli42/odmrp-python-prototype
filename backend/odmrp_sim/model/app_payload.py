"""Application payload encoding for text, chunks, products, and OMS SA reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AppKind = Literal[
    "text",
    "chunk",
    "product_meta",
    "product_loc",
    "sa_chunk",
    "oms_status",
    "oms_position",
]

OMS_KINDS = frozenset({"oms_status", "oms_position"})


@dataclass
class AppPayload:
    kind: AppKind
    message_id: str
    body: str | None = None
    transfer_id: str | None = None
    index: int | None = None
    total: int | None = None
    name: str | None = None
    sha256: str | None = None
    data: bytes | None = None  # chunk / SA stream bytes (not JSON-encoded into body)
    # OMS announcement envelope (JSON object as dict / string body fallback)
    product: dict[str, Any] | None = None
    # OMS SA peer reports (ADR-008) — compact mesh fields, not full UCI XML
    platform_id: str | None = None
    generated_at: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    heading: float | None = None
    readiness: str | None = None
    fuel_percent: float | None = None
    weapons_remaining: int | None = None
    active_task_count: int | None = None
    subsystems: dict[str, str] = field(default_factory=dict)

    def encode(self) -> bytes:
        meta = {
            "kind": self.kind,
            "message_id": self.message_id,
            "body": self.body,
            "transfer_id": self.transfer_id,
            "index": self.index,
            "total": self.total,
            "name": self.name,
            "sha256": self.sha256,
            "product": self.product,
            "platform_id": self.platform_id,
            "generated_at": self.generated_at,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "heading": self.heading,
            "readiness": self.readiness,
            "fuel_percent": self.fuel_percent,
            "weapons_remaining": self.weapons_remaining,
            "active_task_count": self.active_task_count,
            "subsystems": self.subsystems or None,
        }
        # Drop nulls for compact mesh frames
        meta = {k: v for k, v in meta.items() if v is not None}
        header = json.dumps(meta, separators=(",", ":")).encode("utf-8")
        if self.kind in ("chunk", "sa_chunk") and self.data is not None:
            return len(header).to_bytes(4, "big") + header + self.data
        return header

    @classmethod
    def decode(cls, raw: bytes) -> AppPayload:
        if len(raw) >= 4:
            n = int.from_bytes(raw[:4], "big")
            if 2 <= n <= len(raw) - 4 and raw[4:5] == b"{":
                meta = json.loads(raw[4 : 4 + n].decode("utf-8"))
                data = raw[4 + n :]
                kind = meta["kind"]
                return cls._from_meta(meta, data=data if kind in ("chunk", "sa_chunk") else None)
        meta = json.loads(raw.decode("utf-8"))
        return cls._from_meta(meta)

    @classmethod
    def _from_meta(cls, meta: dict[str, Any], *, data: bytes | None = None) -> AppPayload:
        subs = meta.get("subsystems") or {}
        return cls(
            kind=meta["kind"],
            message_id=meta["message_id"],
            body=meta.get("body"),
            transfer_id=meta.get("transfer_id"),
            index=meta.get("index"),
            total=meta.get("total"),
            name=meta.get("name"),
            sha256=meta.get("sha256"),
            data=data,
            product=meta.get("product"),
            platform_id=meta.get("platform_id"),
            generated_at=meta.get("generated_at"),
            latitude=_opt_float(meta.get("latitude")),
            longitude=_opt_float(meta.get("longitude")),
            altitude=_opt_float(meta.get("altitude")),
            heading=_opt_float(meta.get("heading")),
            readiness=meta.get("readiness"),
            fuel_percent=_opt_float(meta.get("fuel_percent")),
            weapons_remaining=_opt_int(meta.get("weapons_remaining")),
            active_task_count=_opt_int(meta.get("active_task_count")),
            subsystems={str(k): str(v) for k, v in subs.items()} if isinstance(subs, dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("data", None)
        return d


def _opt_float(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


def _opt_int(v: Any) -> int | None:
    if v is None:
        return None
    return int(v)


def make_oms_status(
    *,
    message_id: str,
    platform_id: str,
    generated_at: str,
    readiness: str = "GREEN",
    fuel_percent: float = 100.0,
    weapons_remaining: int = 0,
    active_task_count: int = 0,
    subsystems: dict[str, str] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> AppPayload:
    return AppPayload(
        kind="oms_status",
        message_id=message_id,
        platform_id=platform_id,
        generated_at=generated_at,
        readiness=readiness,
        fuel_percent=fuel_percent,
        weapons_remaining=weapons_remaining,
        active_task_count=active_task_count,
        subsystems=dict(subsystems or {}),
        latitude=latitude,
        longitude=longitude,
    )


def make_oms_position(
    *,
    message_id: str,
    platform_id: str,
    generated_at: str,
    latitude: float,
    longitude: float,
    altitude: float | None = None,
    heading: float | None = None,
) -> AppPayload:
    return AppPayload(
        kind="oms_position",
        message_id=message_id,
        platform_id=platform_id,
        generated_at=generated_at,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        heading=heading,
    )
