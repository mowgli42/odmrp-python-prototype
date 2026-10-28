"""OMS-aligned data plan for overlay ODMRP messaging and file products.

Maps ODMRP control/data onto messaging envelopes and uses ProductMetadata +
ProductLocation (open-arsenal OMS style) for staged file transfers. Node IDs
and tunnel endpoints are referenced from the address book — no native IPv4
multicast.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from odmrp_sim.model.packets import GroupId, NodeId

OdmrpMessageKind = Literal[
    "join_query",
    "join_reply",
    "data_text",
    "data_product",
    "membership_update",
    "neighbor_recommend",
    "data_plan_fragment",
]


@dataclass
class ProductLocation:
    """Where a product lives (OMS ProductLocation analogue)."""

    uri: str
    mime_type: str = "application/octet-stream"
    expires_at: str | None = None  # ISO-8601 wall clock or sim annotation
    staging_node: NodeId | None = None
    tunnel_endpoint: str | None = None  # resolved from address book when set
    size_bytes: int | None = None
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProductLocation:
        return cls(
            uri=str(d["uri"]),
            mime_type=str(d.get("mime_type", "application/octet-stream")),
            expires_at=d.get("expires_at"),
            staging_node=int(d["staging_node"]) if d.get("staging_node") is not None else None,
            tunnel_endpoint=d.get("tunnel_endpoint"),
            size_bytes=int(d["size_bytes"]) if d.get("size_bytes") is not None else None,
            sha256=d.get("sha256"),
        )


@dataclass
class ProductMetadata:
    """OMS-style product descriptor for overlay file transfers."""

    product_id: str
    product_type: str = "file"
    title: str = ""
    source_node: NodeId | None = None
    group: GroupId | None = None
    classification: str | None = None
    created_at: str | None = None
    location: ProductLocation | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_type": self.product_type,
            "title": self.title,
            "source_node": self.source_node,
            "group": self.group,
            "classification": self.classification,
            "created_at": self.created_at,
            "location": self.location.to_dict() if self.location else None,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProductMetadata:
        loc = d.get("location")
        return cls(
            product_id=str(d["product_id"]),
            product_type=str(d.get("product_type", "file")),
            title=str(d.get("title", "")),
            source_node=int(d["source_node"]) if d.get("source_node") is not None else None,
            group=str(d["group"]) if d.get("group") is not None else None,
            classification=d.get("classification"),
            created_at=d.get("created_at"),
            location=ProductLocation.from_dict(loc) if loc else None,
            extra=dict(d.get("extra") or {}),
        )


@dataclass
class DataPlanMessage:
    """One messaging entry: short text or product pointer over ODMRP data path."""

    message_id: str
    kind: OdmrpMessageKind
    group: GroupId
    source_node: NodeId
    body: str | None = None
    product: ProductMetadata | None = None
    # Address-book references for underlay resolution
    source_endpoint: str | None = None
    intended_members: list[NodeId] = field(default_factory=list)
    at: float = 0.0  # sim time to inject

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "kind": self.kind,
            "group": self.group,
            "source_node": self.source_node,
            "body": self.body,
            "product": self.product.to_dict() if self.product else None,
            "source_endpoint": self.source_endpoint,
            "intended_members": list(self.intended_members),
            "at": self.at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DataPlanMessage:
        prod = d.get("product")
        return cls(
            message_id=str(d["message_id"]),
            kind=str(d["kind"]),  # type: ignore[arg-type]
            group=str(d["group"]),
            source_node=int(d["source_node"]),
            body=d.get("body"),
            product=ProductMetadata.from_dict(prod) if prod else None,
            source_endpoint=d.get("source_endpoint"),
            intended_members=[int(x) for x in d.get("intended_members", [])],
            at=float(d.get("at", 0.0)),
        )


@dataclass
class DataPlan:
    """OMS-aligned plan: short messages + file products for an overlay scenario."""

    name: str
    group: GroupId = "demo"
    address_book: str = ""  # fixture path or book name
    messages: list[DataPlanMessage] = field(default_factory=list)
    products: list[ProductMetadata] = field(default_factory=list)
    description: str = ""
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "group": self.group,
            "address_book": self.address_book,
            "messages": [m.to_dict() for m in self.messages],
            "products": [p.to_dict() for p in self.products],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DataPlan:
        return cls(
            name=str(d.get("name", "unnamed")),
            version=str(d.get("version", "1.0")),
            description=str(d.get("description", "")),
            group=str(d.get("group", "demo")),
            address_book=str(d.get("address_book", "")),
            messages=[DataPlanMessage.from_dict(m) for m in d.get("messages", [])],
            products=[ProductMetadata.from_dict(p) for p in d.get("products", [])],
        )
