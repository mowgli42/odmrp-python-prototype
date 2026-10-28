"""Gateway (super-node) DataPlan dissemination + connected-node monitor.

Local to the gateway path — ordinary ODMRP nodes and JQ/JR/FG/dup-cache are
unchanged. Product announcements are destination-filtered unicasts over the
gateway's *currently active* tunnels (NeighborSender.neighbor_send_to).

Design choice (documented): announcements go only to
``DataPlan destinations ∩ gateway active neighbors``. Multi-hop group data
still uses classic ODMRP FG mesh; the gateway does not invent a second flood.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from odmrp_sim.model.app_payload import AppPayload
from odmrp_sim.model.data_plan import DataPlan, ProductLocation, ProductMetadata
from odmrp_sim.model.packets import NodeId, Packet, PacketKind
if TYPE_CHECKING:
    from odmrp_sim.model.address_book import AddressBook
    from odmrp_sim.services.sa_feed import ProductInterest
    from odmrp_sim.sim.engine import SimulationEngine


class DataPlanStore(Protocol):
    """Replaceable persistence seam for the active mission DataPlan."""

    def get(self) -> DataPlan | None: ...

    def replace(self, plan: DataPlan) -> DataPlan: ...


@dataclass
class InMemoryDataPlanStore:
    """Prototype store — swap for DB/file later without touching dissemination."""

    _plan: DataPlan | None = None

    def get(self) -> DataPlan | None:
        return self._plan

    def replace(self, plan: DataPlan) -> DataPlan:
        self._plan = plan
        return self._plan


@dataclass
class DisseminationResult:
    matched: bool
    product_id: str
    destinations_planned: list[NodeId]
    destinations_sent: list[NodeId]
    skipped_unconnected: list[NodeId]
    hops: list[dict[str, Any]] = field(default_factory=list)
    announcements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "product_id": self.product_id,
            "destinations_planned": list(self.destinations_planned),
            "destinations_sent": list(self.destinations_sent),
            "skipped_unconnected": list(self.skipped_unconnected),
            "hops": list(self.hops),
            "announcements": list(self.announcements),
        }


@dataclass
class MonitorEvent:
    kind: str  # connect | disconnect | prune | replace
    t: float
    nodes: list[NodeId] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "t": self.t,
            "nodes": list(self.nodes),
            "detail": dict(self.detail),
        }


class ConnectedNodeMonitor:
    """Tracks gateway active tunnels; prunes DataPlan destinations on disconnect."""

    def __init__(self, gateway_id: NodeId) -> None:
        self.gateway_id = gateway_id
        self.connected: set[NodeId] = set()
        self.events: list[MonitorEvent] = []
        self._max_events = 200

    def _push(self, ev: MonitorEvent) -> None:
        self.events.append(ev)
        if len(self.events) > self._max_events:
            self.events = self.events[-self._max_events :]

    def read_connected(self, book: AddressBook | None, now: float) -> set[NodeId]:
        if book is None:
            return set()
        entry = book.get(self.gateway_id)
        if entry is None:
            return set()
        return {int(n) for n in entry.neighbor_ids(now)}

    def sync(
        self,
        book: AddressBook | None,
        plan: DataPlan | None,
        now: float,
        *,
        prune_plan: bool = True,
    ) -> dict[str, Any]:
        current = self.read_connected(book, now)
        added = sorted(current - self.connected)
        removed = sorted(self.connected - current)
        prunes: list[dict[str, Any]] = []
        if added:
            self._push(MonitorEvent(kind="connect", t=now, nodes=added))
        if removed:
            self._push(MonitorEvent(kind="disconnect", t=now, nodes=removed))
            if prune_plan and plan is not None:
                prunes = plan.prune_destinations(current)
                if prunes:
                    self._push(
                        MonitorEvent(
                            kind="prune",
                            t=now,
                            nodes=removed,
                            detail={"changes": prunes},
                        )
                    )
        self.connected = current
        return {
            "connected": sorted(current),
            "added": added,
            "removed": removed,
            "prunes": prunes,
        }


class GatewayService:
    """Super-node DataPlan evaluation + announcement TX (gateway-local)."""

    def __init__(
        self,
        engine: SimulationEngine,
        *,
        gateway_id: NodeId = 0,
        store: DataPlanStore | None = None,
    ) -> None:
        self.engine = engine
        self.gateway_id = gateway_id
        self.store: DataPlanStore = store or InMemoryDataPlanStore()
        self.monitor = ConnectedNodeMonitor(gateway_id)
        self.last_disseminations: list[DisseminationResult] = []
        self._products: dict[str, ProductMetadata] = {}
        self._seq = 50_000

    def status(self) -> dict[str, Any]:
        plan = self.store.get()
        return {
            "gateway_id": self.gateway_id,
            "connected": sorted(self.monitor.connected),
            "data_plan": plan.to_dict() if plan else None,
            "dissemination": [r.to_dict() for r in (plan.dissemination if plan else [])],
            "products_staged": list(self._products.keys()),
            "last_disseminations": [d.to_dict() for d in self.last_disseminations[-10:]],
            "monitor_events": [e.to_dict() for e in self.monitor.events[-20:]],
            "policy": "destinations ∩ gateway active tunnels; FG mesh unchanged",
        }

    def replace_data_plan(self, plan: DataPlan, *, reannounce: bool = False) -> dict[str, Any]:
        """Load/replace active DataPlan; optionally re-announce staged products.

        Initial load does not prune multi-hop destinations — only disconnects do.
        Dissemination still sends only to destinations ∩ currently connected tunnels.
        """
        stored = self.store.replace(plan)
        self.engine.data_plan = stored
        now = self.engine.scheduler.now
        sync = self.monitor.sync(
            self.engine.address_book, stored, now, prune_plan=False
        )
        self.monitor._push(
            MonitorEvent(
                kind="replace",
                t=now,
                nodes=sorted(self.monitor.connected),
                detail={"name": stored.name, "rules": len(stored.dissemination)},
            )
        )
        self.engine.bus.emit(
            now,
            self.gateway_id,
            "gateway",
            op="data_plan_replace",
            name=stored.name,
            rules=len(stored.dissemination),
            connected=sync["connected"],
        )
        results = []
        if reannounce:
            for prod in list(self._products.values()):
                results.append(self.disseminate_product(prod).to_dict())
        return {"plan": stored.to_dict(), "sync": sync, "reannounced": results}

    def tick(self, now: float | None = None) -> dict[str, Any]:
        """Periodic / event-driven connectivity sync; prune destinations on disconnect."""
        t = self.engine.scheduler.now if now is None else now
        plan = self.store.get()
        # Prune only when peers disappeared (unreachable destinations).
        sync = self.monitor.sync(self.engine.address_book, plan, t, prune_plan=True)
        if sync["added"] or sync["removed"] or sync["prunes"]:
            self.engine.bus.emit(
                t,
                self.gateway_id,
                "gateway",
                op="monitor",
                **sync,
            )
        if sync["removed"] and hasattr(self.engine, "sa_feed"):
            # Tear down leaf JREAP subscriptions for pruned destinations
            self.engine.sa_feed.on_destinations_pruned(sync["removed"])
        return sync

    def handle_interest(self, interest: ProductInterest) -> dict[str, Any]:
        """Evaluate DataPlan for interest; mint ProductLocation only if authorized."""
        plan = self.store.get()
        if plan is None:
            return {"authorized": False, "reason": "no_data_plan"}
        allowed = set(plan.destinations_for(interest.product_type, self.gateway_id))
        # Also match rules with source=None
        allowed |= set(plan.destinations_for(interest.product_type, None))
        if interest.node_id not in allowed:
            self.engine.bus.emit(
                self.engine.scheduler.now,
                self.gateway_id,
                "gateway",
                op="interest_denied",
                node_id=interest.node_id,
                product_type=interest.product_type,
                allowed=sorted(allowed),
            )
            return {"authorized": False, "reason": "not_in_dataplan", "allowed": sorted(allowed)}

        self.tick()
        source = self.engine.sa_feed.ensure_endpoint()
        product = ProductMetadata(
            product_id=f"prod-{interest.product_type.lower()}",
            product_type=interest.product_type,
            title=f"SA feed {interest.product_type}",
            source_node=self.gateway_id,
            group=interest.group,
            location=ProductLocation(
                uri=source.uri,
                mime_type="application/x-jreap-a",
                staging_node=self.gateway_id,
            ),
        )
        staged = self.stage_product(product)
        # Destinations = authorized interested nodes still listed in the plan
        interested = self.engine.sa_feed.interested_nodes(interest.product_type)
        destinations = sorted(allowed & interested)
        if interest.node_id not in destinations:
            destinations = sorted(set(destinations) | {interest.node_id})
        mint = self.engine.sa_feed.on_minted(staged, destinations, announce_via_fg=True)
        return {"authorized": True, "destinations": destinations, "mint": mint}

    def stage_product(self, product: ProductMetadata) -> ProductMetadata:
        """Record a product available at the gateway (staging)."""
        prod = copy.deepcopy(product)
        if prod.location is None:
            book = self.engine.address_book
            endpoint = None
            if book is not None:
                entry = book.get(self.gateway_id)
                endpoint = entry.tunnel_endpoint if entry else None
            prod.location = ProductLocation(
                uri=f"gateway://{self.gateway_id}/{prod.product_id}",
                staging_node=self.gateway_id,
                tunnel_endpoint=endpoint,
            )
        elif prod.location.staging_node is None:
            prod.location.staging_node = self.gateway_id
        if prod.source_node is None:
            prod.source_node = self.gateway_id
        if prod.group is None and self.store.get() is not None:
            prod.group = self.store.get().group  # type: ignore[union-attr]
        self._products[prod.product_id] = prod
        self.engine.bus.emit(
            self.engine.scheduler.now,
            self.gateway_id,
            "gateway",
            op="product_available",
            product_id=prod.product_id,
            product_type=prod.product_type,
        )
        return prod

    def on_product_available(self, product: ProductMetadata) -> DisseminationResult:
        """Stage + evaluate DataPlan + announce toward matched destinations."""
        staged = self.stage_product(product)
        return self.disseminate_product(staged)

    def evaluate_destinations(self, product: ProductMetadata) -> list[NodeId]:
        plan = self.store.get()
        if plan is None:
            return []
        return plan.destinations_for(product.product_type, product.source_node)

    def disseminate_product(
        self,
        product: ProductMetadata,
        *,
        destinations_override: list[NodeId] | None = None,
        use_fg_mesh: bool = False,
    ) -> DisseminationResult:
        """Create ProductMetadata + ProductLocation announcements; unicast to destinations.

        Default: ``neighbor_send_to`` over destinations ∩ active tunnels (ttl=1).
        When ``use_fg_mesh`` is True (JREAP-A path): ``neighbor_send`` to all current
        tunnels with ttl>1 so current FG members may forward — ODMRP FG rules unchanged.
        """
        self.tick()
        planned = (
            list(destinations_override)
            if destinations_override is not None
            else self.evaluate_destinations(product)
        )
        connected = set(self.monitor.connected)
        send_to = sorted(set(planned) & connected) if not use_fg_mesh else sorted(connected)
        skipped = sorted(set(planned) - connected)
        result = DisseminationResult(
            matched=bool(planned),
            product_id=product.product_id,
            destinations_planned=list(planned),
            destinations_sent=list(send_to),
            skipped_unconnected=skipped,
        )
        if not planned:
            self.engine.bus.emit(
                self.engine.scheduler.now,
                self.gateway_id,
                "gateway",
                op="disseminate_skip",
                reason="no_match",
                product_id=product.product_id,
                product_type=product.product_type,
            )
            self.last_disseminations.append(result)
            return result
        if not send_to:
            self.engine.bus.emit(
                self.engine.scheduler.now,
                self.gateway_id,
                "gateway",
                op="disseminate_skip",
                reason="none_connected",
                product_id=product.product_id,
                destinations_planned=planned,
            )
            self.last_disseminations.append(result)
            return result

        group = product.group or (self.store.get().group if self.store.get() else "demo")
        meta_id = f"ann-meta-{product.product_id}-{uuid.uuid4().hex[:8]}"
        loc_id = f"ann-loc-{product.product_id}-{uuid.uuid4().hex[:8]}"
        meta_payload = AppPayload(
            kind="product_meta",
            message_id=meta_id,
            product=product.to_dict(),
            body=product.title or product.product_id,
        ).encode()
        loc_dict = product.location.to_dict() if product.location else {}
        loc_payload = AppPayload(
            kind="product_loc",
            message_id=loc_id,
            product={
                "product_id": product.product_id,
                "product_type": product.product_type,
                "location": loc_dict,
            },
            body=loc_dict.get("uri"),
        ).encode()

        hops_all: list[dict[str, Any]] = []
        ttl = 8 if use_fg_mesh else 1
        for kind_label, payload in (("product_meta", meta_payload), ("product_loc", loc_payload)):
            self._seq += 1
            pkt = Packet(
                kind=PacketKind.DATA,
                source=self.gateway_id,
                group=str(group),
                seq=self._seq,
                previous_hop=self.gateway_id,
                ttl=ttl,
                payload=payload,
            )
            if use_fg_mesh:
                hops = self.engine.medium.neighbor_send(
                    self.gateway_id, pkt, self.engine.scheduler.now
                )
            else:
                hops = self.engine.medium.neighbor_send_to(
                    self.gateway_id, pkt, send_to, self.engine.scheduler.now
                )
            hops_all.extend(
                {"peer_id": h.peer_id, "tunnel_endpoint": h.tunnel_endpoint, "kind": kind_label}
                for h in hops
            )
            result.announcements.append(kind_label)

        result.hops = hops_all
        self.engine.bus.emit(
            self.engine.scheduler.now,
            self.gateway_id,
            "gateway",
            op="disseminate",
            use_fg_mesh=use_fg_mesh,
            **result.to_dict(),
        )
        self.last_disseminations.append(result)
        if len(self.last_disseminations) > 50:
            self.last_disseminations = self.last_disseminations[-50:]
        return result
