"""Neighbor-send medium: schedule deliveries to current neighbours.

Uses a NeighborProvider so the same path works for RF topology or
logical IPsec-tunnel peers (no native IPv4 multicast/broadcast).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from odmrp_sim.dataplane.neighbor_send import NeighborProvider, TopologyNeighborProvider
from odmrp_sim.model.packets import NodeId, Packet
from odmrp_sim.sim.rng import SeededRng

if TYPE_CHECKING:
    from odmrp_sim.events.bus import EventBus
    from odmrp_sim.model.params import ProtocolParams
    from odmrp_sim.model.topology import Topology
    from odmrp_sim.sim.scheduler import Scheduler


class Medium:
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
        self.neighbors = neighbors or TopologyNeighborProvider(topology)
        self._tx_counter = 0

    def set_neighbor_provider(self, provider: NeighborProvider) -> None:
        self.neighbors = provider

    def broadcast(self, sender: NodeId, packet: Packet, now: float) -> None:
        nbs = self.neighbors.neighbors_of(sender, now=now)
        neighbors = sorted(nbs)
        self.bus.emit(now, sender, "tx", packet=packet.to_dict(), neighbors=neighbors)
        for i, nb in enumerate(neighbors):
            self._tx_counter += 1
            jitter = self.rng.uniform(sender, "jq", self._tx_counter, low=0.0, high=self.params.jq_jitter)
            delay = self.params.hop_delay + jitter
            arrive = now + delay

            def _cb(ev, _nb=nb, _pkt=packet, _sender=sender):  # noqa: B023
                t = ev.t
                self.bus.emit(
                    t, _nb, "rx", **{"packet_id": _pkt.id, "from": _sender, "pkind": _pkt.kind.value}
                )
                self.on_deliver(_nb, _pkt, _sender, t)

            self.scheduler.schedule(
                arrive,
                "deliver",
                node=nb,
                payload={"packet_id": packet.id, "from": sender},
                callback=_cb,
            )
