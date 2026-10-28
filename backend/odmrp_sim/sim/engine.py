"""SimulationEngine — discrete-event MANET host for ODMRP nodes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from odmrp_sim.dataplane.neighbor_send import (
    AddressBookNeighborProvider,
    HybridNeighborProvider,
    TopologyNeighborProvider,
)
from odmrp_sim.events.bus import EventBus
from odmrp_sim.model.address_book import AddressBook
from odmrp_sim.model.data_plan import DataPlan
from odmrp_sim.model.packets import GroupId, NodeId, reset_packet_ids
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import Position
from odmrp_sim.model.super_node import SuperNodePolicy
from odmrp_sim.model.topology import Topology
from odmrp_sim.protocol.external_node import ExternalProcessNode
from odmrp_sim.protocol.interface import ODMRPNode
from odmrp_sim.protocol.python_node import PythonODMRPNode
from odmrp_sim.sim.medium import Medium
from odmrp_sim.sim.node_host import NodeHost
from odmrp_sim.sim.rng import SeededRng, derive_seed
from odmrp_sim.sim.scheduler import Event, Scheduler

NodeImplName = Literal["python", "java", "external", "native"]
OverlayMode = Literal["radio", "tunnel", "hybrid"]


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
    # Per-node native/external launch config from scenario YAML.
    node_commands: dict[NodeId, list[str]] = field(default_factory=dict)
    node_logs: dict[NodeId, Path] = field(default_factory=dict)
    java_jar: Path | None = None
    java_bin: str | None = None
    external_command: Sequence[str] | None = None
    node_factory: Callable[[NodeId], ODMRPNode] | None = None
    overlay_mode: OverlayMode = "hybrid"
    address_book: AddressBook | None = None
    data_plan: DataPlan | None = None
    super_node_policy: SuperNodePolicy = field(default_factory=SuperNodePolicy)
    gateway_id: NodeId = 0

    def __post_init__(self) -> None:
        from odmrp_sim.services.gateway import GatewayService

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
        self._rebind_neighbors()
        self.gateway = GatewayService(self, gateway_id=self.gateway_id)

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
        self.node_impls.clear()
        self.node_commands.clear()
        self.node_logs.clear()
        self.address_book = None
        self.data_plan = None
        self.medium = Medium(
            self.topology,
            self.scheduler,
            self.bus,
            self.params,
            self.rng,
            on_deliver=self._on_deliver,
        )
        self.topology.on_change(self._on_topo)
        self._rebind_neighbors()
        from odmrp_sim.services.gateway import GatewayService

        self.gateway = GatewayService(self, gateway_id=self.gateway_id)
        self._next_id = 0
        reset_packet_ids()
        self.bus.emit(0.0, -1, "sim", op="reset", seed=self.seed)

    def _rebind_neighbors(self) -> None:
        if self.overlay_mode == "tunnel" and self.address_book is not None:
            self.medium.set_neighbor_provider(AddressBookNeighborProvider(self.address_book))
        elif self.overlay_mode == "hybrid" and self.address_book is not None:
            self.medium.set_neighbor_provider(
                HybridNeighborProvider(self.topology, self.address_book)
            )
        else:
            self.medium.set_neighbor_provider(TopologyNeighborProvider(self.topology))

    def bind_address_book(self, book: AddressBook, *, mode: OverlayMode | None = None) -> None:
        self.address_book = book
        if mode is not None:
            self.overlay_mode = mode
        supers = book.super_nodes()
        if supers:
            self.gateway_id = supers[0].node_id
            self.gateway.gateway_id = self.gateway_id
            self.gateway.monitor.gateway_id = self.gateway_id
        self._rebind_neighbors()
        self.gateway.tick(self.scheduler.now)
        self.bus.emit(
            self.scheduler.now,
            -1,
            "overlay",
            op="address_book",
            name=book.name,
            nodes=len(book.nodes),
            mode=self.overlay_mode,
        )

    def bind_data_plan(self, plan: DataPlan) -> None:
        self.data_plan = plan
        self.gateway.replace_data_plan(plan, reannounce=False)
        self.bus.emit(
            self.scheduler.now,
            -1,
            "overlay",
            op="data_plan",
            name=plan.name,
            messages=len(plan.messages),
            products=len(plan.products),
            dissemination=len(plan.dissemination),
        )

    def set_node_impls(self, mapping: Mapping[NodeId, NodeImplName]) -> None:
        self.node_impls = dict(mapping)

    def _make_impl(self, node_id: NodeId, impl_name: NodeImplName | None = None) -> ODMRPNode:
        if self.node_factory is not None:
            return self.node_factory(node_id)
        name: NodeImplName = impl_name or self.node_impls.get(node_id, self.default_impl)
        log_path = self.node_logs.get(node_id)
        if name == "python":
            return PythonODMRPNode()
        if name == "java":
            return ExternalProcessNode.java(
                jar=self.java_jar, java_bin=self.java_bin, log_path=log_path
            )
        if name == "native":
            cmd = self.node_commands.get(node_id)
            return ExternalProcessNode.native(command=cmd, log_path=log_path)
        if name == "external":
            cmd = self.node_commands.get(node_id) or (
                list(self.external_command) if self.external_command else None
            )
            if not cmd:
                raise ValueError("command required when impl=external")
            return ExternalProcessNode(command=list(cmd), log_path=log_path)
        raise ValueError(f"unknown node impl: {name}")

    def add_node(
        self,
        x: float,
        y: float,
        range_: float | None = None,
        node_id: NodeId | None = None,
        *,
        impl: NodeImplName | None = None,
        command: Sequence[str] | None = None,
        log: str | Path | None = None,
    ) -> NodeId:
        nid = self._next_id if node_id is None else node_id
        self._next_id = max(self._next_id, nid + 1)
        r = self.topology.default_range if range_ is None else range_
        self.topology.add(nid, x, y, r)
        resolved = impl or self.node_impls.get(nid, self.default_impl)
        if command is not None:
            self.node_commands[nid] = list(command)
        if log is not None:
            self.node_logs[nid] = Path(log)
        elif resolved in ("native", "external", "java") and nid not in self.node_logs:
            # Default monitor log for process-backed nodes.
            self.node_logs[nid] = Path("traces") / f"native-{nid}.log"
        if impl is not None:
            self.node_impls[nid] = impl
        node_impl = self._make_impl(nid, resolved)
        host = NodeHost(
            nid,
            node_impl,
            self.params,
            self.bus,
            self.medium,
            derive_seed(self.seed, "node", nid),
            Position(x, y),
            r,
            impl_name=resolved,
            log_path=self.node_logs.get(nid),
        )
        self.hosts[nid] = host
        if host.log_path is not None:
            self.bus.emit(
                self.scheduler.now,
                nid,
                "native",
                op="configured",
                impl=resolved,
                log=str(host.log_path),
                command=list(self.node_commands.get(nid, [])),
            )
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
        if until <= self.scheduler.now + 1e-12:
            return 0
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
        # Gateway monitor: soft-state tunnel changes may prune DataPlan destinations
        self.gateway.tick(self.scheduler.now)
        self.bus.emit(self.scheduler.now, -1, "sim", op="step", seed=self.seed)
        return n

    def snapshot(self) -> dict[str, Any]:
        nodes: dict[str, Any] = {}
        for i, h in self.hosts.items():
            d = h.get_state().to_dict()
            d["impl"] = h.impl_name
            if h.log_path is not None:
                d["log"] = str(h.log_path)
            nodes[str(i)] = d
        overlay: dict[str, Any] = {
            "mode": self.overlay_mode,
            "policy": self.super_node_policy.to_dict(),
        }
        if self.address_book is not None:
            overlay["address_book"] = self.address_book.to_dict()
            overlay["super_nodes"] = [e.node_id for e in self.address_book.super_nodes()]
            overlay["logical_links"] = self.address_book.logical_links(self.scheduler.now)
        if self.data_plan is not None:
            overlay["data_plan"] = {
                "name": self.data_plan.name,
                "group": self.data_plan.group,
                "messages": len(self.data_plan.messages),
                "products": len(self.data_plan.products),
                "dissemination": [r.to_dict() for r in self.data_plan.dissemination],
            }
        overlay["gateway"] = self.gateway.status()
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
            "nodes": nodes,
            "overlay": overlay,
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
