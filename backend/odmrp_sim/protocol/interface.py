"""ODMRPNode Protocol — ADR-005."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from odmrp_sim.model.packets import GroupId, NodeId, Packet
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import NodeState


@runtime_checkable
class ODMRPNode(Protocol):
    def configure(self, node_id: NodeId, params: ProtocolParams, rng_seed: int) -> None: ...

    def set_membership(self, group: GroupId, member: bool, now: float) -> list[Packet]: ...

    def originate(self, group: GroupId, payload: bytes, now: float) -> list[Packet]: ...

    def receive(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]: ...

    def advance(self, now: float) -> list[Packet]: ...

    def next_timer(self) -> float | None: ...

    def get_state(self) -> NodeState: ...
