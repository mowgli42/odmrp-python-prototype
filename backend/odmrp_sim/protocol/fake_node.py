"""Minimal FakeNode for harness tests — echoes membership, drops everything else."""

from __future__ import annotations

from dataclasses import dataclass, field

from odmrp_sim.model.packets import GroupId, NodeId, Packet
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import NodeState, Position


@dataclass
class FakeNode:
    node_id: NodeId = -1
    params: ProtocolParams = field(default_factory=ProtocolParams)
    pos: Position = field(default_factory=lambda: Position(0.0, 0.0))
    range: float = 130.0
    _members: set[GroupId] = field(default_factory=set)
    _received: list[Packet] = field(default_factory=list)

    def configure(self, node_id: NodeId, params: ProtocolParams, rng_seed: int) -> None:
        self.node_id = node_id
        self.params = params

    def set_membership(self, group: GroupId, member: bool, now: float) -> list[Packet]:
        if member:
            self._members.add(group)
        else:
            self._members.discard(group)
        return []

    def originate(self, group: GroupId, payload: bytes, now: float) -> list[Packet]:
        return []

    def receive(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]:
        self._received.append(packet)
        return []

    def advance(self, now: float) -> list[Packet]:
        return []

    def next_timer(self) -> float | None:
        return None

    def get_state(self) -> NodeState:
        return NodeState(
            id=self.node_id,
            pos=self.pos,
            range=self.range,
            members=set(self._members),
        )
