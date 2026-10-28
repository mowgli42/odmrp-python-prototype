"""Neighbor-send primitive — unicast over each current logical neighbor.

ODMRP Join Query / Join Reply / FG data forwarding call only this boundary.
"Broadcast to neighbors" means: loop the current neighbor set and unicast the
same packet once per active peer (IPsec tunnel endpoint). No native IPv4
multicast or link-layer broadcast.

The same ODMRP logic can later bind this to simulated radio (unit-disk peers)
or real tunnels (address-book peers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol

from odmrp_sim.model.packets import NodeId, Packet

if TYPE_CHECKING:
    from odmrp_sim.events.bus import EventBus
    from odmrp_sim.model.address_book import AddressBook
    from odmrp_sim.model.params import ProtocolParams
    from odmrp_sim.model.topology import Topology
    from odmrp_sim.sim.rng import SeededRng
    from odmrp_sim.sim.scheduler import Scheduler


@dataclass(frozen=True)
class UnicastHop:
    """One unicast send over a current tunnel (or radio peer)."""

    peer_id: NodeId
    tunnel_endpoint: str | None = None  # e.g. ipsec://10.8.0.2:500


class NeighborProvider(Protocol):
    def neighbors_of(self, node_id: NodeId, *, now: float = 0.0) -> list[NodeId]: ...

    def hops_of(self, node_id: NodeId, *, now: float = 0.0) -> list[UnicastHop]:
        """Optional rich hops with tunnel endpoints; default = peer ids only."""
        ...


class TopologyNeighborProvider:
    """Classic unit-disk radio adjacency (still unicast-per-peer at this layer)."""

    def __init__(self, topology: Topology) -> None:
        self.topology = topology

    def neighbors_of(self, node_id: NodeId, *, now: float = 0.0) -> list[NodeId]:
        return sorted(self.topology.neighbors_of(node_id))

    def hops_of(self, node_id: NodeId, *, now: float = 0.0) -> list[UnicastHop]:
        return [UnicastHop(peer_id=n) for n in self.neighbors_of(node_id, now=now)]


class AddressBookNeighborProvider:
    """Logical IPsec-tunnel peers from the address book (soft-state)."""

    def __init__(self, book: AddressBook) -> None:
        self.book = book

    def neighbors_of(self, node_id: NodeId, *, now: float = 0.0) -> list[NodeId]:
        entry = self.book.get(node_id)
        if entry is None:
            return []
        return sorted(entry.neighbor_ids(now))

    def hops_of(self, node_id: NodeId, *, now: float = 0.0) -> list[UnicastHop]:
        entry = self.book.get(node_id)
        if entry is None:
            return []
        hops = [
            UnicastHop(peer_id=n.peer_id, tunnel_endpoint=n.tunnel_endpoint)
            for n in entry.active_neighbors(now)
        ]
        hops.sort(key=lambda h: h.peer_id)
        return hops


class HybridNeighborProvider:
    """Prefer logical neighbors when present; fall back to RF topology."""

    def __init__(self, topology: Topology, book: AddressBook | None = None) -> None:
        self.topology = TopologyNeighborProvider(topology)
        self.book = AddressBookNeighborProvider(book) if book is not None else None

    def neighbors_of(self, node_id: NodeId, *, now: float = 0.0) -> list[NodeId]:
        if self.book is not None:
            logical = self.book.neighbors_of(node_id, now=now)
            if logical:
                return logical
        return self.topology.neighbors_of(node_id, now=now)

    def hops_of(self, node_id: NodeId, *, now: float = 0.0) -> list[UnicastHop]:
        if self.book is not None:
            hops = self.book.hops_of(node_id, now=now)
            if hops:
                return hops
        return self.topology.hops_of(node_id, now=now)


class NeighborSender:
    """Unicast-over-current-tunnels sender used by ODMRP TX.

    Calling ``neighbor_send`` is the only way ODMRP control/data leave a node.
    Implementation = for each active hop in the current neighbor set, schedule
    one unicast delivery (sim) / one tunnel send (real dataplane later).
    """

    def __init__(
        self,
        provider: NeighborProvider,
        scheduler: Scheduler,
        bus: EventBus,
        params: ProtocolParams,
        rng: SeededRng,
        on_deliver: Callable[[NodeId, Packet, NodeId, float], None],
    ) -> None:
        self.provider = provider
        self.scheduler = scheduler
        self.bus = bus
        self.params = params
        self.rng = rng
        self.on_deliver = on_deliver
        self._tx_counter = 0

    def set_provider(self, provider: NeighborProvider) -> None:
        self.provider = provider

    def current_hops(self, sender: NodeId, *, now: float) -> list[UnicastHop]:
        if hasattr(self.provider, "hops_of"):
            return list(self.provider.hops_of(sender, now=now))  # type: ignore[attr-defined]
        return [UnicastHop(peer_id=n) for n in self.provider.neighbors_of(sender, now=now)]

    def neighbor_send(self, sender: NodeId, packet: Packet, now: float) -> list[UnicastHop]:
        """Unicast ``packet`` once over every active tunnel/peer in the current set.

        Returns the hop list that was used (empty if isolated).
        """
        hops = self.current_hops(sender, now=now)
        neighbors = [h.peer_id for h in hops]
        self.bus.emit(
            now,
            sender,
            "tx",
            packet=packet.to_dict(),
            neighbors=neighbors,
            unicasts=[
                {"peer_id": h.peer_id, "tunnel_endpoint": h.tunnel_endpoint}
                for h in hops
            ],
            mode="unicast_over_neighbors",
        )
        for hop in hops:
            self._tx_counter += 1
            jitter = self.rng.uniform(
                sender, "jq", self._tx_counter, low=0.0, high=self.params.jq_jitter
            )
            delay = self.params.hop_delay + jitter
            arrive = now + delay
            peer = hop.peer_id
            endpoint = hop.tunnel_endpoint

            def _cb(ev, _nb=peer, _pkt=packet, _sender=sender, _ep=endpoint):  # noqa: B023
                t = ev.t
                self.bus.emit(
                    t,
                    _nb,
                    "rx",
                    packet_id=_pkt.id,
                    **{"from": _sender, "pkind": _pkt.kind.value, "tunnel_endpoint": _ep},
                )
                self.on_deliver(_nb, _pkt, _sender, t)

            self.scheduler.schedule(
                arrive,
                "deliver",
                node=peer,
                payload={
                    "packet_id": packet.id,
                    "from": sender,
                    "tunnel_endpoint": endpoint,
                    "unicast": True,
                },
                callback=_cb,
            )
        return hops
