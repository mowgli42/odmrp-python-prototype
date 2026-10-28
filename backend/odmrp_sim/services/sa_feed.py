"""JREAP-A / SA feed: interest → DataPlan mint → stream relay with local consume.

Does not change ODMRP JQ/JR/FG/dup-cache. Stream chunks ride neighbor-send
(unicast over selected tunnels). A node that already receives or forwards a
product never opens a second connection to the ProductLocation endpoint.
"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from odmrp_sim.model.app_payload import AppPayload
from odmrp_sim.model.data_plan import ProductLocation, ProductMetadata
from odmrp_sim.model.packets import GroupId, NodeId, Packet, PacketKind
from odmrp_sim.services.jreap_endpoint import (
    PRODUCT_TYPE_JREAP,
    MockSaSource,
    SaByteSource,
    TcpJreapEndpoint,
    TcpSaClient,
)

if TYPE_CHECKING:
    from odmrp_sim.sim.engine import SimulationEngine

ConsumerCb = Callable[[NodeId, str, bytes, dict[str, Any]], None]


@dataclass
class ProductInterest:
    node_id: NodeId
    product_type: str = PRODUCT_TYPE_JREAP
    group: GroupId = "demo"
    t: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "product_type": self.product_type,
            "group": self.group,
            "t": self.t,
        }


@dataclass
class ProductFeedRecord:
    """Per-node per-product stream state (consume-while-forward)."""

    product_id: str
    product_type: str
    group: GroupId
    upstream_tunnel: NodeId | None = None
    consuming: bool = False
    forwarding: bool = False
    downstream_tunnels: list[NodeId] = field(default_factory=list)
    endpoint_uri: str | None = None
    opened_endpoint: bool = False  # True only if this node opened the thin endpoint
    bytes_consumed: int = 0
    chunks_rx: int = 0
    chunks_tx: int = 0
    interested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_type": self.product_type,
            "group": self.group,
            "upstream_tunnel": self.upstream_tunnel,
            "consuming": self.consuming,
            "forwarding": self.forwarding,
            "downstream_tunnels": list(self.downstream_tunnels),
            "endpoint_uri": self.endpoint_uri,
            "opened_endpoint": self.opened_endpoint,
            "bytes_consumed": self.bytes_consumed,
            "chunks_rx": self.chunks_rx,
            "chunks_tx": self.chunks_tx,
            "interested": self.interested,
        }


class SaFeedService:
    """Interest registry + gateway mint + overlay stream relay."""

    def __init__(self, engine: SimulationEngine) -> None:
        self.engine = engine
        self.interests: dict[tuple[NodeId, str], ProductInterest] = {}
        # node_id -> product_id -> record
        self.records: dict[NodeId, dict[str, ProductFeedRecord]] = {}
        self.consumers: list[ConsumerCb] = []
        self.endpoint: TcpJreapEndpoint | None = None
        self._source: SaByteSource | None = None
        self._tcp_client: TcpSaClient | None = None
        self._use_tcp: bool = False
        self._seq: int = 80_000
        self._active_product: ProductMetadata | None = None
        self._pump_count: int = 0
        self.last_mint: dict[str, Any] | None = None

    # --- consumers / status -------------------------------------------------

    def add_consumer(self, cb: ConsumerCb) -> None:
        self.consumers.append(cb)

    def status(self) -> dict[str, Any]:
        return {
            "interests": [i.to_dict() for i in self.interests.values()],
            "records": {
                str(nid): {pid: r.to_dict() for pid, r in recs.items()}
                for nid, recs in self.records.items()
            },
            "endpoint_uri": self._source.uri if self._source else None,
            "endpoint_clients": self.endpoint.clients if self.endpoint else 0,
            "active_product": self._active_product.to_dict() if self._active_product else None,
            "last_mint": self.last_mint,
            "pump_count": self._pump_count,
            "tcp_client_opened": bool(self._tcp_client and self._tcp_client.opened),
        }

    def record_for(self, node_id: NodeId, product_id: str) -> ProductFeedRecord | None:
        return self.records.get(node_id, {}).get(product_id)

    def ensure_endpoint(self, *, use_tcp: bool = False) -> SaByteSource:
        """Start mock source (in-process or TCP). Idempotent."""
        if self._source is not None and (not use_tcp or self._use_tcp == use_tcp):
            return self._source
        self._use_tcp = use_tcp
        if use_tcp:
            self.endpoint = TcpJreapEndpoint()
            uri = self.endpoint.start()
            client = TcpSaClient(uri=uri)
            client.connect()
            self._tcp_client = client
            # Wrap client as SaByteSource
            self._source = _ClientSource(client, uri)
        else:
            self._source = MockSaSource()
        return self._source

    def close_endpoint(self) -> None:
        if self._tcp_client is not None:
            self._tcp_client.close()
            self._tcp_client = None
        if self.endpoint is not None:
            self.endpoint.stop()
            self.endpoint = None
        if self._source is not None:
            self._source.close()
            self._source = None

    # --- interest -----------------------------------------------------------

    def express_interest(
        self,
        node_id: NodeId,
        product_type: str = PRODUCT_TYPE_JREAP,
        *,
        group: GroupId = "demo",
    ) -> dict[str, Any]:
        """Node signals interest. Does not create tunnels or change FG."""
        now = self.engine.scheduler.now
        key = (int(node_id), product_type)
        interest = ProductInterest(node_id=int(node_id), product_type=product_type, group=group, t=now)
        self.interests[key] = interest
        self.engine.bus.emit(
            now,
            node_id,
            "sa_feed",
            op="interest",
            product_type=product_type,
            group=group,
        )
        # Gateway evaluates DataPlan and may mint ProductLocation
        mint = self.engine.gateway.handle_interest(interest)
        return {"interest": interest.to_dict(), "mint": mint}

    def revoke_interest(self, node_id: NodeId, product_type: str = PRODUCT_TYPE_JREAP) -> None:
        self.interests.pop((int(node_id), product_type), None)
        # Tear down leaf subscription records for this node
        for pid, rec in list(self.records.get(int(node_id), {}).items()):
            if rec.product_type == product_type and not rec.forwarding:
                self._teardown_leaf(int(node_id), pid)

    def interested_nodes(self, product_type: str) -> set[NodeId]:
        return {i.node_id for i in self.interests.values() if i.product_type == product_type}

    # --- mint / announce (called from gateway) ------------------------------

    def on_minted(
        self,
        product: ProductMetadata,
        destinations: list[NodeId],
        *,
        announce_via_fg: bool = True,
    ) -> dict[str, Any]:
        """After gateway mints location: register feed records and announce."""
        self._active_product = product
        source = self.ensure_endpoint(use_tcp=self._use_tcp)
        assert product.location is not None
        product.location.uri = source.uri
        product.location.mime_type = "application/x-jreap-a"
        gw = self.engine.gateway_id

        # Gateway is the only node that opens the endpoint
        gw_rec = ProductFeedRecord(
            product_id=product.product_id,
            product_type=product.product_type,
            group=str(product.group or "demo"),
            upstream_tunnel=None,
            consuming=True,  # gateway may also log locally
            forwarding=True,
            downstream_tunnels=[],
            endpoint_uri=source.uri,
            opened_endpoint=True,
            interested=False,
        )
        self.records.setdefault(gw, {})[product.product_id] = gw_rec

        for dest in destinations:
            interested = dest in self.interested_nodes(product.product_type)
            self.records.setdefault(int(dest), {})[product.product_id] = ProductFeedRecord(
                product_id=product.product_id,
                product_type=product.product_type,
                group=str(product.group or "demo"),
                consuming=interested,
                forwarding=False,
                endpoint_uri=source.uri,
                opened_endpoint=False,
                interested=interested,
            )

        # Wire downstream: gateway → connected peers that help reach destinations
        gw_rec.downstream_tunnels = self._gateway_downstream(destinations)
        self._wire_forwarders(product, destinations)

        result = self.engine.gateway.disseminate_product(
            product, destinations_override=destinations, use_fg_mesh=announce_via_fg
        )
        self.last_mint = {
            "product_id": product.product_id,
            "uri": source.uri,
            "destinations": list(destinations),
            "downstream": list(gw_rec.downstream_tunnels),
            "announce": result.to_dict(),
        }
        self.engine.bus.emit(
            self.engine.scheduler.now,
            gw,
            "sa_feed",
            op="mint",
            **self.last_mint,
        )
        return self.last_mint

    def _gateway_downstream(self, destinations: list[NodeId]) -> list[NodeId]:
        connected = set(self.engine.gateway.monitor.connected)
        dest_set = {int(d) for d in destinations}
        # Prefer direct tunnels to destinations; else all connected peers (relays)
        direct = sorted(connected & dest_set)
        if direct:
            return direct
        return sorted(connected)

    def _wire_forwarders(self, product: ProductMetadata, destinations: list[NodeId]) -> None:
        """Mark FG members that sit on the path as forwarding + consuming."""
        dest_set = {int(d) for d in destinations}
        group = str(product.group or "demo")
        for nid, host in self.engine.hosts.items():
            if nid == self.engine.gateway_id or nid in dest_set:
                continue
            st = host.get_state()
            is_fg = group in st.forwarding_groups
            if not is_fg:
                continue
            # FG forwarder for this SA product: consume locally, never open endpoint
            peers = self._active_peers(nid)
            downstream = [p for p in peers if p in dest_set or self._peer_leads_to(p, dest_set)]
            if not downstream:
                # still forward toward any dest-adjacent peer
                downstream = [p for p in peers if p != self.engine.gateway_id]
            rec = ProductFeedRecord(
                product_id=product.product_id,
                product_type=product.product_type,
                group=group,
                consuming=True,  # forwarder always consumes
                forwarding=True,
                downstream_tunnels=sorted(set(downstream)),
                endpoint_uri=product.location.uri if product.location else None,
                opened_endpoint=False,
                interested=nid in self.interested_nodes(product.product_type),
            )
            self.records.setdefault(int(nid), {})[product.product_id] = rec

    def _peer_leads_to(self, peer: NodeId, dest_set: set[NodeId]) -> bool:
        book = self.engine.address_book
        if book is None:
            return False
        entry = book.get(peer)
        if entry is None:
            return False
        return bool(dest_set & set(entry.neighbor_ids(self.engine.scheduler.now)))

    def _active_peers(self, node_id: NodeId) -> list[NodeId]:
        hops = self.engine.medium.sender.current_hops(node_id, now=self.engine.scheduler.now)
        return [h.peer_id for h in hops]

    # --- stream pump / relay ------------------------------------------------

    def pump(self, n_chunks: int = 1) -> list[dict[str, Any]]:
        """Read from the thin endpoint (gateway only) and relay over tunnels."""
        if self._active_product is None or self._source is None:
            return []
        product = self._active_product
        out = []
        for _ in range(n_chunks):
            data = self._source.read()
            if not data:
                break
            self._pump_count += 1
            info = self._emit_chunk(self.engine.gateway_id, product, data, upstream=None)
            out.append(info)
        return out

    def _emit_chunk(
        self,
        from_node: NodeId,
        product: ProductMetadata,
        data: bytes,
        *,
        upstream: NodeId | None,
    ) -> dict[str, Any]:
        rec = self.records.get(from_node, {}).get(product.product_id)
        if rec is None:
            return {"skipped": True, "reason": "no_record"}
        # Local consume
        if rec.consuming or rec.interested or rec.forwarding:
            self._consume(from_node, product.product_id, data, rec)
        downstream = list(rec.downstream_tunnels)
        if upstream is not None:
            downstream = [d for d in downstream if d != upstream]
        if not rec.forwarding or not downstream:
            return {
                "from": from_node,
                "consumed": rec.consuming,
                "forwarded_to": [],
                "bytes": len(data),
            }
        self._seq += 1
        payload = AppPayload(
            kind="sa_chunk",
            message_id=f"sa-{product.product_id}-{self._seq}",
            transfer_id=product.product_id,
            index=self._seq,
            name=product.product_type,
            product={"product_id": product.product_id, "product_type": product.product_type},
            data=data,
        ).encode()
        pkt = Packet(
            kind=PacketKind.DATA,
            source=self.engine.gateway_id,
            group=str(product.group or "demo"),
            seq=self._seq,
            previous_hop=from_node,
            ttl=1,  # hop-by-hop relay via SaFeedService, not ODMRP FG flood
            payload=payload,
        )
        hops = self.engine.medium.neighbor_send_to(
            from_node, pkt, downstream, self.engine.scheduler.now
        )
        rec.chunks_tx += 1
        self.engine.bus.emit(
            self.engine.scheduler.now,
            from_node,
            "sa_feed",
            op="forward",
            product_id=product.product_id,
            peers=[h.peer_id for h in hops],
            bytes=len(data),
        )
        return {
            "from": from_node,
            "consumed": True,
            "forwarded_to": [h.peer_id for h in hops],
            "bytes": len(data),
        }

    def _consume(self, node_id: NodeId, product_id: str, data: bytes, rec: ProductFeedRecord) -> None:
        rec.consuming = True
        rec.bytes_consumed += len(data)
        rec.chunks_rx += 1
        meta = {"product_id": product_id, "product_type": rec.product_type, "group": rec.group}
        for cb in self.consumers:
            cb(node_id, product_id, data, meta)
        self.engine.bus.emit(
            self.engine.scheduler.now,
            node_id,
            "sa_feed",
            op="consume",
            product_id=product_id,
            bytes=len(data),
            forwarding=rec.forwarding,
            opened_endpoint=rec.opened_endpoint,
        )

    def handle_packet(self, node_id: NodeId, packet: Packet, previous_hop: NodeId, now: float) -> bool:
        """Intercept sa_chunk / JREAP product_loc. Returns True if fully handled."""
        if not packet.payload:
            return False
        try:
            app = AppPayload.decode(packet.payload)
        except Exception:
            return False
        if app.kind == "sa_chunk":
            return self._on_sa_chunk(node_id, packet, app, previous_hop, now)
        if app.kind in ("product_meta", "product_loc") and app.product:
            ptype = (app.product.get("product_type")
                     or (app.product.get("location") and "Link16-JREAP-A")
                     or "")
            # product_loc embeds product_id + location only
            if app.kind == "product_loc":
                pid = str(app.product.get("product_id") or "")
                recs = self.records.get(node_id, {})
                if pid in recs or any(r.product_type == PRODUCT_TYPE_JREAP for r in recs.values()):
                    self.engine.bus.emit(
                        now,
                        node_id,
                        "sa_feed",
                        op="announce_rx",
                        announce_kind=app.kind,
                        product_id=pid,
                    )
                    # Do not open endpoint — stream arrives via overlay
                    return False  # still allow inbox delivery via ODMRP if member
            if ptype == PRODUCT_TYPE_JREAP or app.product.get("product_type") == PRODUCT_TYPE_JREAP:
                self.engine.bus.emit(
                    now,
                    node_id,
                    "sa_feed",
                    op="announce_rx",
                    announce_kind=app.kind,
                    product_id=app.product.get("product_id"),
                )
        return False

    def _on_sa_chunk(
        self,
        node_id: NodeId,
        packet: Packet,
        app: AppPayload,
        previous_hop: NodeId,
        now: float,
    ) -> bool:
        product_id = str(
            (app.product or {}).get("product_id")
            or app.transfer_id
            or (self._active_product.product_id if self._active_product else "")
        )
        if not product_id or self._active_product is None:
            return True
        product = self._active_product
        rec = self.records.get(node_id, {}).get(product_id)
        if rec is None:
            # Opportunistic: if FG for group, become forwarder-consumer without new TCP
            host = self.engine.hosts.get(node_id)
            is_fg = False
            if host is not None:
                is_fg = product.group in host.get_state().forwarding_groups if product.group else False
            interested = node_id in self.interested_nodes(product.product_type)
            if not (is_fg or interested):
                return True
            peers = [h.peer_id for h in self.engine.medium.sender.current_hops(node_id, now=now)]
            downstream = [p for p in peers if p != previous_hop]
            rec = ProductFeedRecord(
                product_id=product_id,
                product_type=product.product_type,
                group=str(product.group or "demo"),
                upstream_tunnel=previous_hop,
                consuming=True,
                forwarding=is_fg,
                downstream_tunnels=downstream if is_fg else [],
                endpoint_uri=product.location.uri if product.location else None,
                opened_endpoint=False,
                interested=interested,
            )
            self.records.setdefault(node_id, {})[product_id] = rec
        else:
            rec.upstream_tunnel = previous_hop
            # Never open a second endpoint connection
            assert rec.opened_endpoint is False or node_id == self.engine.gateway_id

        data = app.data or b""
        self._emit_chunk(node_id, product, data, upstream=previous_hop)
        return True  # do not also run ODMRP FG rebroadcast for sa_chunk

    # --- prune / teardown ---------------------------------------------------

    def on_destinations_pruned(self, removed: list[NodeId], product_type: str = PRODUCT_TYPE_JREAP) -> None:
        """Stop minting/leaf streams for pruned destinations; keep relay paths."""
        for nid in removed:
            self.revoke_interest(nid, product_type)
            for pid, rec in list(self.records.get(int(nid), {}).items()):
                if rec.product_type == product_type and not rec.forwarding:
                    self._teardown_leaf(int(nid), pid)
            # Drop pruned node from everyone else's downstream lists
            for _nid, recs in self.records.items():
                for rec in recs.values():
                    if int(nid) in rec.downstream_tunnels:
                        rec.downstream_tunnels = [d for d in rec.downstream_tunnels if d != int(nid)]
        self.engine.bus.emit(
            self.engine.scheduler.now,
            self.engine.gateway_id,
            "sa_feed",
            op="prune_subs",
            removed=list(removed),
            product_type=product_type,
        )

    def _teardown_leaf(self, node_id: NodeId, product_id: str) -> None:
        recs = self.records.get(node_id)
        if not recs or product_id not in recs:
            return
        rec = recs.pop(product_id)
        self.engine.bus.emit(
            self.engine.scheduler.now,
            node_id,
            "sa_feed",
            op="teardown",
            product_id=product_id,
            was_forwarding=rec.forwarding,
        )


@dataclass
class _ClientSource:
    client: TcpSaClient
    _uri: str

    @property
    def uri(self) -> str:
        return self._uri

    def read(self, max_bytes: int = 256) -> bytes:
        return self.client.read(max_bytes)

    def close(self) -> None:
        self.client.close()
