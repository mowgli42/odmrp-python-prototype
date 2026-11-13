"""OMS peer SA distribution — status 1/20 Hz + position 1/5 Hz (ADR-008).

Publisher emits compact oms_status / oms_position AppPayloads. After
mesh_established, PythonODMRPNode.originate sends pure DATA (no JQ flood).
Consumers track latest report per platform_id with freshness / stale rules.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from odmrp_sim.model.app_payload import (
    OMS_KINDS,
    AppPayload,
    make_oms_position,
    make_oms_status,
)
from odmrp_sim.model.packets import GroupId, NodeId, PacketKind

if TYPE_CHECKING:
    from odmrp_sim.sim.engine import SimulationEngine


class OmsSaConfigError(ValueError):
    """Unsafe or invalid OMS SA configuration."""


@dataclass
class OmsSaConfig:
    group: GroupId = "oms.sa"
    status_period_s: float = 20.0
    position_period_s: float = 5.0
    production: bool = True
    # node_id -> phase offset seconds
    status_phase_s: dict[NodeId, float] = field(default_factory=dict)
    position_phase_s: dict[NodeId, float] = field(default_factory=dict)
    # node_id -> platform_id (default: str(node_id))
    platform_ids: dict[NodeId, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.production and (self.status_period_s < 1.0 or self.position_period_s < 1.0):
            raise OmsSaConfigError(
                "production OMS SA rejects status_period_s or position_period_s below 1.0"
            )
        if self.status_period_s <= 0 or self.position_period_s <= 0:
            raise OmsSaConfigError("OMS SA periods must be positive")

    def platform_id_for(self, node_id: NodeId) -> str:
        return self.platform_ids.get(int(node_id), str(int(node_id)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "status_period_s": self.status_period_s,
            "position_period_s": self.position_period_s,
            "production": self.production,
            "status_phase_s": {str(k): v for k, v in self.status_phase_s.items()},
            "position_phase_s": {str(k): v for k, v in self.position_phase_s.items()},
            "platform_ids": {str(k): v for k, v in self.platform_ids.items()},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> OmsSaConfig:
        if not d:
            return cls()
        return cls(
            group=str(d.get("group", "oms.sa")),
            status_period_s=float(d.get("status_period_s", 20.0)),
            position_period_s=float(d.get("position_period_s", 5.0)),
            production=bool(d.get("production", True)),
            status_phase_s={int(k): float(v) for k, v in (d.get("status_phase_s") or {}).items()},
            position_phase_s={int(k): float(v) for k, v in (d.get("position_phase_s") or {}).items()},
            platform_ids={int(k): str(v) for k, v in (d.get("platform_ids") or {}).items()},
        )


@dataclass
class PeerStatus:
    platform_id: str
    generated_at: str
    readiness: str = "GREEN"
    fuel_percent: float = 0.0
    weapons_remaining: int = 0
    active_task_count: int = 0
    subsystems: dict[str, str] = field(default_factory=dict)
    latitude: float | None = None
    longitude: float | None = None
    received_at: float = 0.0
    stale: bool = False
    source_node: NodeId | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeerPosition:
    platform_id: str
    generated_at: str
    latitude: float
    longitude: float
    altitude: float | None = None
    heading: float | None = None
    received_at: float = 0.0
    stale: bool = False
    source_node: NodeId | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeerView:
    status: PeerStatus | None = None
    position: PeerPosition | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.to_dict() if self.status else None,
            "position": self.position.to_dict() if self.position else None,
        }


class OmsSaService:
    """Per-engine OMS SA publisher + consumer + metrics."""

    def __init__(self, engine: SimulationEngine) -> None:
        self.engine = engine
        self.config = OmsSaConfig()
        self.active: set[NodeId] = set()
        # consumer_node -> platform_id -> PeerView
        self.views: dict[NodeId, dict[str, PeerView]] = {}
        self._armed = False
        self._status_count = 0
        self._position_count = 0
        self._rejected_foreign = 0
        self._last_error: str | None = None

    def configure(self, cfg: OmsSaConfig | dict[str, Any], *, validate: bool = True) -> OmsSaConfig:
        self.config = cfg if isinstance(cfg, OmsSaConfig) else OmsSaConfig.from_dict(cfg)
        if validate:
            try:
                self.config.validate()
            except OmsSaConfigError as e:
                self._last_error = str(e)
                raise
        self._last_error = None
        return self.config

    def platform_id_for(self, node_id: NodeId) -> str:
        return self.config.platform_id_for(node_id)

    def activate(self, node_ids: list[NodeId] | set[NodeId] | None = None) -> dict[str, Any]:
        """Mark nodes as active OMS peers, join group, arm timers."""
        self.config.validate()
        if node_ids is None:
            node_ids = list(self.engine.hosts.keys())
        for nid in node_ids:
            nid = int(nid)
            self.active.add(nid)
            self.engine.join(nid, self.config.group)
            self.views.setdefault(nid, {})
        self._arm_timers()
        return {"active": sorted(self.active), "group": self.config.group, "config": self.config.to_dict()}

    def _arm_timers(self) -> None:
        """Schedule first status/position fires; reschedule on each fire."""
        now = self.engine.scheduler.now
        for nid in sorted(self.active):
            self._schedule_kind(nid, "status", now + float(self.config.status_phase_s.get(nid, 0.0)))
            self._schedule_kind(nid, "position", now + float(self.config.position_phase_s.get(nid, 0.0)))
        self._armed = True

    def _schedule_kind(self, node_id: NodeId, kind: str, at: float) -> None:
        if at < self.engine.scheduler.now:
            at = self.engine.scheduler.now

        def _cb(ev, nid=node_id, k=kind) -> None:
            self._on_timer(nid, k)

        self.engine.scheduler.schedule(
            float(at),
            f"oms_sa.{kind}",
            node=int(node_id),
            payload={"kind": kind, "node": int(node_id)},
            callback=_cb,
        )

    def _on_timer(self, node_id: NodeId, kind: str) -> None:
        if node_id not in self.active:
            return
        now = self.engine.scheduler.now
        if kind == "status":
            self.publish_status(node_id)
            self._schedule_kind(node_id, "status", now + self.config.status_period_s)
        else:
            self.publish_position(node_id)
            self._schedule_kind(node_id, "position", now + self.config.position_period_s)

    def publish_status(self, node_id: NodeId, **overrides: Any) -> str:
        pid = self.platform_id_for(node_id)
        host = self.engine.hosts[node_id]
        mid = str(uuid.uuid4())
        generated_at = f"t={self.engine.scheduler.now:.3f}"
        app = make_oms_status(
            message_id=mid,
            platform_id=pid,
            generated_at=overrides.get("generated_at", generated_at),
            readiness=str(overrides.get("readiness", "GREEN")),
            fuel_percent=float(overrides.get("fuel_percent", 100.0)),
            weapons_remaining=int(overrides.get("weapons_remaining", 0)),
            active_task_count=int(overrides.get("active_task_count", 0)),
            subsystems=overrides.get("subsystems"),
            latitude=overrides.get("latitude", host.pos.x),
            longitude=overrides.get("longitude", host.pos.y),
        )
        self._originate_guarded(node_id, app)
        self._status_count += 1
        return mid

    def publish_position(self, node_id: NodeId, **overrides: Any) -> str:
        pid = self.platform_id_for(node_id)
        host = self.engine.hosts[node_id]
        mid = str(uuid.uuid4())
        generated_at = f"t={self.engine.scheduler.now:.3f}"
        app = make_oms_position(
            message_id=mid,
            platform_id=pid,
            generated_at=overrides.get("generated_at", generated_at),
            latitude=float(overrides.get("latitude", host.pos.x)),
            longitude=float(overrides.get("longitude", host.pos.y)),
            altitude=overrides.get("altitude"),
            heading=overrides.get("heading"),
        )
        self._originate_guarded(node_id, app)
        self._position_count += 1
        return mid

    def _originate_guarded(self, node_id: NodeId, app: AppPayload) -> None:
        local_pid = self.platform_id_for(node_id)
        if app.platform_id is None or app.platform_id != local_pid:
            self._rejected_foreign += 1
            raise OmsSaConfigError(
                f"refuse originate: platform_id {app.platform_id!r} != local {local_pid!r}"
            )
        if app.kind not in OMS_KINDS:
            raise OmsSaConfigError(f"unsupported OMS kind {app.kind}")
        self.engine.originate(node_id, self.config.group, app.encode())

    def ingest_inbox(self) -> int:
        """Pull new OMS inbox items into consumer views. Returns items applied."""
        n = 0
        now = self.engine.scheduler.now
        for nid, host in self.engine.hosts.items():
            for item in host.get_state().inbox:
                if item.app_kind not in OMS_KINDS:
                    continue
                # Re-decode from... inbox may lack full fields; scan via message_id match in bus
                # Prefer platform_id on inbox when present; else skip decode-less items
                if not item.platform_id:
                    continue
                if self._apply_inbox_item(nid, item, now):
                    n += 1
        self._refresh_stale(now)
        return n

    def on_deliver(
        self,
        consumer: NodeId,
        *,
        app_kind: str,
        platform_id: str | None,
        source: NodeId,
        payload: AppPayload | None = None,
        now: float | None = None,
    ) -> None:
        if app_kind not in OMS_KINDS or not platform_id:
            return
        t = self.engine.scheduler.now if now is None else now
        view = self.views.setdefault(int(consumer), {}).setdefault(platform_id, PeerView())
        if app_kind == "oms_status":
            gen = payload.generated_at if payload else f"t={t:.3f}"
            if view.status and _ts_older(gen, view.status.generated_at):
                return
            view.status = PeerStatus(
                platform_id=platform_id,
                generated_at=gen or "",
                readiness=(payload.readiness if payload and payload.readiness else "GREEN"),
                fuel_percent=float(payload.fuel_percent) if payload and payload.fuel_percent is not None else 0.0,
                weapons_remaining=int(payload.weapons_remaining or 0) if payload else 0,
                active_task_count=int(payload.active_task_count or 0) if payload else 0,
                subsystems=dict(payload.subsystems) if payload else {},
                latitude=payload.latitude if payload else None,
                longitude=payload.longitude if payload else None,
                received_at=t,
                stale=False,
                source_node=int(source),
            )
        else:
            if payload is None or payload.latitude is None or payload.longitude is None:
                return
            gen = payload.generated_at or f"t={t:.3f}"
            if view.position and _ts_older(gen, view.position.generated_at):
                return
            view.position = PeerPosition(
                platform_id=platform_id,
                generated_at=gen,
                latitude=float(payload.latitude),
                longitude=float(payload.longitude),
                altitude=payload.altitude,
                heading=payload.heading,
                received_at=t,
                stale=False,
                source_node=int(source),
            )

    def _apply_inbox_item(self, consumer: NodeId, item: Any, now: float) -> bool:
        # Decode original payload is not stored; use inbox platform_id + kind only for presence.
        # Full field update happens via on_deliver when hooked from NodeHost.
        pid = item.platform_id
        if not pid:
            return False
        view = self.views.setdefault(int(consumer), {}).setdefault(pid, PeerView())
        if item.app_kind == "oms_status" and view.status is None:
            view.status = PeerStatus(
                platform_id=pid,
                generated_at=f"t={item.t:.3f}",
                received_at=float(item.t),
                source_node=int(item.source),
            )
            return True
        if item.app_kind == "oms_position" and view.position is None:
            view.position = PeerPosition(
                platform_id=pid,
                generated_at=f"t={item.t:.3f}",
                latitude=0.0,
                longitude=0.0,
                received_at=float(item.t),
                source_node=int(item.source),
            )
            return True
        return False

    def _refresh_stale(self, now: float) -> None:
        status_lim = 2.0 * self.config.status_period_s
        pos_lim = 2.0 * self.config.position_period_s
        for peers in self.views.values():
            for view in peers.values():
                if view.status is not None:
                    view.status.stale = (now - view.status.received_at) > status_lim
                if view.position is not None:
                    view.position.stale = (now - view.position.received_at) > pos_lim

    def snapshot(self, node_id: NodeId | None = None) -> dict[str, Any]:
        self._refresh_stale(self.engine.scheduler.now)
        if node_id is not None:
            peers = self.views.get(int(node_id), {})
            return {pid: v.to_dict() for pid, v in peers.items()}
        return {
            str(nid): {pid: v.to_dict() for pid, v in peers.items()}
            for nid, peers in self.views.items()
        }

    def metrics(self) -> dict[str, Any]:
        """Trace-derived SA health metrics (offer, amplification, drops, delivery)."""
        bus = self.engine.bus.ring
        group = self.config.group
        jq_tx = 0
        data_tx = 0
        dup_drops = 0
        not_fg_drops = 0
        delivers_status = 0
        delivers_position = 0
        cache_sizes: list[int] = []

        for ev in bus:
            kind = ev.kind
            pl = ev.payload or {}
            if kind == "tx":
                pkt = pl.get("packet") or {}
                pkt_kind = str(pkt.get("kind", ""))
                if pkt_kind == PacketKind.JOIN_QUERY.value or pkt.get("join_query"):
                    jq_tx += 1
                elif pkt_kind == PacketKind.DATA.value:
                    data_tx += 1
            elif kind == "drop":
                reason = pl.get("reason")
                if reason == "duplicate":
                    dup_drops += 1
                elif reason == "not_fg":
                    not_fg_drops += 1
            elif kind == "deliver" and pl.get("group") == group:
                ak = pl.get("app_kind")
                if ak == "oms_status":
                    delivers_status += 1
                elif ak == "oms_position":
                    delivers_position += 1

        for host in self.engine.hosts.values():
            cache_sizes.append(host.get_state().message_cache_size)

        n = max(1, len(self.active))
        offer = n * (1.0 / self.config.status_period_s + 1.0 / self.config.position_period_s)
        # Amplification proxy: DATA tx / position+status originates (when known)
        originates = self._status_count + self._position_count
        amplification = (data_tx / originates) if originates else 0.0

        expected_peer_delivers = max(0, n * (n - 1))
        # Rough delivery ratio for last round not tracked; report cumulative
        return {
            "group": group,
            "active_nodes": sorted(self.active),
            "offer_msgs_per_s": offer,
            "status_originates": self._status_count,
            "position_originates": self._position_count,
            "rejected_foreign": self._rejected_foreign,
            "jq_tx": jq_tx,
            "data_tx": data_tx,
            "tx_amplification_data_per_originate": amplification,
            "dup_drops": dup_drops,
            "not_fg_drops": not_fg_drops,
            "delivers_oms_status": delivers_status,
            "delivers_oms_position": delivers_position,
            "expected_peer_pairs": expected_peer_delivers,
            "message_cache_sizes": cache_sizes,
            "message_cache_max": max(cache_sizes) if cache_sizes else 0,
            "config": self.config.to_dict(),
            "last_error": self._last_error,
        }

    def status(self) -> dict[str, Any]:
        return {
            "active": sorted(self.active),
            "armed": self._armed,
            "config": self.config.to_dict(),
            "views": self.snapshot(),
            "metrics": self.metrics(),
        }


def _ts_older(candidate: str, current: str) -> bool:
    """Return True if candidate should lose to current (older generated_at).

    Supports ``t=<float>`` sim annotations; otherwise lexicographic ISO-ish compare.
    """
    def _key(s: str) -> tuple[int, float | str]:
        if s.startswith("t="):
            try:
                return (0, float(s[2:]))
            except ValueError:
                return (1, s)
        return (1, s)

    return _key(candidate) < _key(current)
