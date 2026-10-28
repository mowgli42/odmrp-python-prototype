"""Super-node overlay policy and recommendation payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from odmrp_sim.model.address_book import NeighborRelation
from odmrp_sim.model.data_plan import DataPlanMessage, ProductMetadata
from odmrp_sim.model.packets import GroupId, NodeId

Preference = Literal["geo", "capability", "priority", "mixed"]


@dataclass
class SuperNodePolicy:
    """Knobs ordinary nodes use when applying super-node recommendations."""

    max_neighbors: int = 4
    preference: Preference = "mixed"
    refresh_interval: float = 5.0
    prefer_super_peers: bool = True
    prefer_staging_capable: bool = True
    soft_state_ttl: float = 15.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> SuperNodePolicy:
        if not d:
            return cls()
        return cls(
            max_neighbors=int(d.get("max_neighbors", 4)),
            preference=str(d.get("preference", "mixed")),  # type: ignore[arg-type]
            refresh_interval=float(d.get("refresh_interval", 5.0)),
            prefer_super_peers=bool(d.get("prefer_super_peers", True)),
            prefer_staging_capable=bool(d.get("prefer_staging_capable", True)),
            soft_state_ttl=float(d.get("soft_state_ttl", 15.0)),
        )


@dataclass
class MembershipUpdate:
    group: GroupId
    members: list[NodeId]
    op: Literal["set", "add", "remove"] = "set"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MembershipUpdate:
        return cls(
            group=str(d["group"]),
            members=[int(x) for x in d.get("members", [])],
            op=str(d.get("op", "set")),  # type: ignore[arg-type]
        )


@dataclass
class SuperNodePush:
    """Bundle pushed by a super node to ordinary peers."""

    from_node: NodeId
    at: float = 0.0
    neighbor_recommendations: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # keyed by target node_id (str) → list of NeighborRelation dicts
    membership: list[MembershipUpdate] = field(default_factory=list)
    data_plan_fragments: list[DataPlanMessage] = field(default_factory=list)
    staging_products: list[ProductMetadata] = field(default_factory=list)
    policy: SuperNodePolicy = field(default_factory=SuperNodePolicy)

    def recommendations_for(self, node_id: NodeId) -> list[NeighborRelation]:
        raw = self.neighbor_recommendations.get(str(node_id), [])
        return [NeighborRelation.from_dict(r) for r in raw]

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "at": self.at,
            "neighbor_recommendations": self.neighbor_recommendations,
            "membership": [m.to_dict() for m in self.membership],
            "data_plan_fragments": [m.to_dict() for m in self.data_plan_fragments],
            "staging_products": [p.to_dict() for p in self.staging_products],
            "policy": self.policy.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SuperNodePush:
        return cls(
            from_node=int(d["from_node"]),
            at=float(d.get("at", 0.0)),
            neighbor_recommendations={
                str(k): list(v) for k, v in (d.get("neighbor_recommendations") or {}).items()
            },
            membership=[MembershipUpdate.from_dict(m) for m in d.get("membership", [])],
            data_plan_fragments=[
                DataPlanMessage.from_dict(m) for m in d.get("data_plan_fragments", [])
            ],
            staging_products=[ProductMetadata.from_dict(p) for p in d.get("staging_products", [])],
            policy=SuperNodePolicy.from_dict(d.get("policy")),
        )
