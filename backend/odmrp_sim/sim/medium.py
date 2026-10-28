"""Neighbor-send medium: unicast over each current logical neighbor.

All ODMRP TX goes through NeighborSender.neighbor_send — never IP multicast
or link-layer broadcast. Peer set comes from NeighborProvider (RF topology
or address-book IPsec tunnels).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from odmrp_sim.dataplane.neighbor_send import (
    NeighborProvider,
    NeighborSender,
    TopologyNeighborProvider,
    UnicastHop,
)
from odmrp_sim.model.packets import NodeId, Packet
from odmrp_sim.sim.rng import SeededRng

if TYPE_CHECKING:
    from odmrp_sim.events.bus import EventBus
    from odmrp_sim.model.params import ProtocolParams
    from odmrp_sim.model.topology import Topology
    from odmrp_sim.sim.scheduler import Scheduler


class Medium:
    """Thin host-facing façade over NeighborSender (the sole TX boundary)."""

    def __init__(
        self,
        topology: Topology,
        scheduler: Scheduler,
        bus: EventBus,
        params: ProtocolParams,
        rng: SeededRng,
        on_deliver: Callable[[NodeId, Packet, NodeId, float], None],
        neighbors: NeighborProvider | None = None,
    ) -> None:
        self.topology = topology
        self.scheduler = scheduler
        self.bus = bus
        self.params = params
        self.rng = rng
        self.on_deliver = on_deliver
        provider = neighbors or TopologyNeighborProvider(topology)
        self.sender = NeighborSender(
            provider=provider,
            scheduler=scheduler,
            bus=bus,
            params=params,
            rng=rng,
            on_deliver=on_deliver,
        )

    @property
    def neighbors(self) -> NeighborProvider:
        return self.sender.provider

    def set_neighbor_provider(self, provider: NeighborProvider) -> None:
        self.sender.set_provider(provider)

    def neighbor_send(self, sender: NodeId, packet: Packet, now: float) -> list[UnicastHop]:
        """Unicast ``packet`` once over every active tunnel/peer (sole TX API)."""
        return self.sender.neighbor_send(sender, packet, now)

    def broadcast(self, sender: NodeId, packet: Packet, now: float) -> list[UnicastHop]:
        """Alias for neighbor_send — "broadcast" = unicast to each current neighbor."""
        return self.neighbor_send(sender, packet, now)
