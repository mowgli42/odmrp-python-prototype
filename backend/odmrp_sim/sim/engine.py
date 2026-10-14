"""SimulationEngine — discrete-event MANET host for ODMRP nodes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from odmrp_sim.events.bus import EventBus
from odmrp_sim.model.packets import GroupId, NodeId, reset_packet_ids
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import Position
from odmrp_sim.model.topology import Topology
from odmrp_sim.protocol.external_node import ExternalProcessNode
from odmrp_sim.protocol.interface import ODMRPNode
from odmrp_sim.protocol.python_node import PythonODMRPNode
from odmrp_sim.sim.medium import Medium
from odmrp_sim.sim.node_host import NodeHost
from odmrp_sim.sim.rng import SeededRng, derive_seed
from odmrp_sim.sim.scheduler import Event, Scheduler

NodeImplName = Literal["python", "java", "external"]


class SimMode(str, Enum):
    PAUSED = "paused"
    RUNNING = "running"


@dataclass
class SimulationEngine:
    params: ProtocolParams = field(default_factory=ProtocolParams)
    seed: int = 42
    scenario: str | None = None
    mode: SimMode = SimMode.PAUSED
    speed: float = 1.0
    # Default implementation for new nodes; per-node override via node_impls / add_node(impl=...).
    default_impl: NodeImplName = "python"
    node_impls: dict[NodeId, NodeImplName] = field(default_factory=dict)
    java_jar: Path | None = None
    java_bin: str | None = None
    external_command: Sequence[str] | None = None
    node_factory: Callable[[NodeId], ODMRPNode] | None = None

    def __post_init__(self) -> None:
        self.topology = Topology(default_range=130.0)
        self.scheduler = Scheduler()
        self.bus = EventBus()
        self.rng = SeededRng(self.seed)
        self.hosts: dict[NodeId, NodeHost] = {}
        self._next_id = 0
        self.medium = Medium(
            self.topology,
            self.scheduler,
            self.bus,
            self.params,
            self.rng,
            on_deliver=self._on_deliver,
        )
        self.topology.on_change(self._on_topo)

    def reset(self, *, seed: int | None = None, params: ProtocolParams | None = None) -> None:
        if seed is not None:
            self.seed = seed
        if params is not None:
            self.params = params
        self.mode = SimMode.PAUSED
        self.speed = 1.0
        self.scenario = None
        for host in list(self.hosts.values()):
            impl = host.impl
            if isinstance(impl, ExternalProcessNode):
                impl.close()
        self.topology.clear()
        self.hosts.clear()
        self.scheduler.reset()
        self.bus.reset()
        self.rng = SeededRng(self.seed)
        self.medium = Medium(
            self.topology,
            self.scheduler,
            self.bus,
            self.params,
            self.rng,
            on_deliver=self._on_deliver,
        )
        self.topology.on_change(self._on_topo)
        self._next_id = 0
        reset_packet_ids()
        self.bus.emit(0.0, -1, "sim", op="reset", seed=self.seed)

    def set_node_impls(self, mapping: Mapping[NodeId, NodeImplName]) -> None:
        self.node_impls = dict(mapping)

    def _make_impl(self, node_id: NodeId, impl_name: NodeImplName | None = None) -> ODMRPNode:
        if self.node_factory is not None:
            return self.node_factory(node_id)
        name: NodeImplName = impl_name or self.node_impls.get(node_id, self.default_impl)
        if name == "python":
            return PythonODMRPNode()
        if name == "java":
            return ExternalProcessNode.java(jar=self.java_jar, java_bin=self.java_bin)
        if name == "external":
            if not self.external_command:
                raise ValueError("external_command required when impl=external")
            return ExternalProcessNode(command=list(self.external_command))
        raise ValueError(f"unknown node impl: {name}")

    def add_node(
        self,
        x: float,
        y: float,
        range_: float | None = None,
        node_id: NodeId | None = None,
        *,
        impl: NodeImplName | None = None,
    ) -> NodeId:
        nid = self._next_id if node_id is None else node_id
        self._next_id = max(self._next_id, nid + 1)
        r = self.topology.default_range if range_ is None else range_
        self.topology.add(nid, x, y, r)
        node_impl = self._make_impl(nid, impl)
        host = NodeHost(
            nid,
            node_impl,
            self.params,
            self.bus,
            self.medium,
            derive_seed(self.seed, "node", nid),
            Position(x, y),
            r,
        )
        self.hosts[nid] = host
        return nid

    def remove_node(self, node_id: NodeId) -> None:
        host = self.hosts.pop(node_id, None)
        if host is not None and isinstance(host.impl, ExternalProcessNode):
            host.impl.close()
        self.topology.remove(node_id)

    def move_node(self, node_id: NodeId, x: float, y: float) -> None:
        self.topology.move(node_id, x, y)
        host = self.hosts[node_id]
        host.pos = Position(x, y)
        if isinstance(host.impl, (PythonODMRPNode, ExternalProcessNode)):
            host.impl.pos = host.pos

    def join(self, node_id: NodeId, group: GroupId) -> None:
        self.hosts[node_id].set_membership(group, True, self.scheduler.now)

    def leave(self, node_id: NodeId, group: GroupId) -> None:
        self.hosts[node_id].set_membership(group, False, self.scheduler.now)

    def originate(self, node_id: NodeId, group: GroupId, payload: bytes) -> None:
        self.hosts[node_id].originate(group, payload, self.scheduler.now)
        self._arm_node_timers(node_id)

    def step(self, dt: float) -> int:
        """Advance simulation by dt seconds. Returns events handled."""
        if dt < 0:
            raise ValueError("dt must be >= 0")
        target = self.scheduler.now + dt
        return self.run_until(target)

    def run_until(self, until: float) -> int:
        # Keep advancing node timers + scheduled deliveries until `until`
        n = 0
        guard = 0
        while guard < 100_000:
            guard += 1
            # Schedule host advances at next timer if needed
            next_t = self._next_global_timer()
            peek = self.scheduler.peek()
            peek_t = peek.t if peek else None

            candidates = [t for t in (next_t, peek_t, until) if t is not None]
            if not candidates:
                self.scheduler.now = until
                break
            slice_t = min(candidates)
            if slice_t > until + 1e-12:
                self.scheduler.now = until
                break

            # Fire node advances at slice_t if timers due
            if next_t is not None and next_t <= slice_t + 1e-12:
                for hid, host in self.hosts.items():
                    nt = host.next_timer()
                    if nt is not None and nt <= slice_t + 1e-12:
                        host.advance(slice_t)
                        self._arm_node_timers(hid)

            handled = self.scheduler.run_until(slice_t, self._handle_event)
            n += handled
            if abs(self.scheduler.now - until) < 1e-9:
                break
            if peek_t is None and (next_t is None or next_t > until):
                self.scheduler.now = until
                break
        self.bus.emit(self.scheduler.now, -1, "sim", op="step", seed=self.seed)
        return n

    def snapshot(self) -> dict[str, Any]:
        return {
            "sim": {
                "t": self.scheduler.now,
                "mode": self.mode.value,
                "speed": self.speed,
                "seed": self.seed,
                "scenario": self.scenario,
            },
            "params": self.params.to_dict(),
            "topology": self.topology.to_dict(),
            "nodes": {str(i): h.get_state().to_dict() for i, h in self.hosts.items()},
            "last_seq": self.bus.last_seq,
        }

    def _on_deliver(self, node: NodeId, packet, previous_hop: NodeId, t: float) -> None:
        host = self.hosts.get(node)
        if host is None:
            return
        host.on_receive(packet, previous_hop, t)
        self._arm_node_timers(node)

    def _handle_event(self, ev: Event) -> None:
        # Delivery callbacks already ran via Event.callback
        return

    def _on_topo(self, payload: dict) -> None:
        self.bus.emit(self.scheduler.now, payload.get("a", -1), "topology", **payload)

    def _next_global_timer(self) -> float | None:
        times = [h.next_timer() for h in self.hosts.values()]
        times = [t for t in times if t is not None]
        return min(times) if times else None

    def _arm_node_timers(self, node_id: NodeId) -> None:
        # Timers are pulled via next_timer(); no explicit scheduler entries needed.
        return
