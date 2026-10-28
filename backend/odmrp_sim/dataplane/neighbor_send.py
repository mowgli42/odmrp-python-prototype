"""Neighbor-send primitive — RF topology or logical tunnel peers.

Same call site for simulated radio (unit-disk Topology) and overlay tunnels
(AddressBook neighbor sets). No native IPv4 multicast/broadcast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from odmrp_sim.model.packets import NodeId

if TYPE_CHECKING:
    from odmrp_sim.model.address_book import AddressBook
    from odmrp_sim.model.topology import Topology


class NeighborProvider(Protocol):
    def neighbors_of(self, node_id: NodeId, *, now: float = 0.0) -> list[NodeId]: ...


class TopologyNeighborProvider:
    """Classic unit-disk radio adjacency."""

    def __init__(self, topology: Topology) -> None:
        self.topology = topology

    def neighbors_of(self, node_id: NodeId, *, now: float = 0.0) -> list[NodeId]:
        return sorted(self.topology.neighbors_of(node_id))


class AddressBookNeighborProvider:
    """Logical IPsec-tunnel peers from the address book."""

    def __init__(self, book: AddressBook) -> None:
        self.book = book

    def neighbors_of(self, node_id: NodeId, *, now: float = 0.0) -> list[NodeId]:
        entry = self.book.get(node_id)
        if entry is None:
            return []
        return sorted(entry.neighbor_ids(now))


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
