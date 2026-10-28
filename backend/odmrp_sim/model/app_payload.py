"""Application payload encoding for text messages and file chunks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

AppKind = Literal["text", "chunk", "product_meta", "product_loc", "sa_chunk"]


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
        }
        header = json.dumps(meta, separators=(",", ":")).encode("utf-8")
        if self.kind in ("chunk", "sa_chunk") and self.data is not None:
            # length-prefixed header + raw bytes
            return len(header).to_bytes(4, "big") + header + self.data
        return header

    @classmethod
    def decode(cls, raw: bytes) -> AppPayload:
        if len(raw) >= 4:
            # Heuristic: if first 4 bytes look like a length and rest is JSON+data
            n = int.from_bytes(raw[:4], "big")
            if 2 <= n <= len(raw) - 4 and raw[4:5] == b"{":
                meta = json.loads(raw[4 : 4 + n].decode("utf-8"))
                data = raw[4 + n :]
                kind = meta["kind"]
                return cls(
                    kind=kind,
                    message_id=meta["message_id"],
                    body=meta.get("body"),
                    transfer_id=meta.get("transfer_id"),
                    index=meta.get("index"),
                    total=meta.get("total"),
                    name=meta.get("name"),
                    sha256=meta.get("sha256"),
                    data=data if kind in ("chunk", "sa_chunk") else None,
                    product=meta.get("product"),
                )
        meta = json.loads(raw.decode("utf-8"))
        return cls(
            kind=meta["kind"],
            message_id=meta["message_id"],
            body=meta.get("body"),
            transfer_id=meta.get("transfer_id"),
            index=meta.get("index"),
            total=meta.get("total"),
            name=meta.get("name"),
            sha256=meta.get("sha256"),
            product=meta.get("product"),
        )



    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("data", None)
        return d
