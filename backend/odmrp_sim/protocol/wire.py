"""NDJSON wire helpers: Packet ↔ dict with payload_b64."""

from __future__ import annotations

import base64
from typing import Any

from odmrp_sim.model.packets import (
    JoinQueryHeader,
    JoinReplyEntry,
    Packet,
    PacketKind,
    next_packet_id,
)
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import (
    FGEntry,
    InboxItem,
    NodeState,
    Position,
    RouteEntry,
    SourceSession,
)


def packet_to_wire(packet: Packet) -> dict[str, Any]:
    d = packet.to_dict()
    if packet.kind in (PacketKind.JOIN_QUERY, PacketKind.DATA):
        d["payload_b64"] = base64.b64encode(packet.payload or b"").decode("ascii")
    return d


def packet_from_wire(d: dict[str, Any]) -> Packet:
    kind = PacketKind(d["kind"])
    entries = [JoinReplyEntry.from_dict(e) for e in d.get("entries", [])]
    payload = b""
    if "payload_b64" in d and d["payload_b64"] is not None:
        payload = base64.b64decode(d["payload_b64"])
    elif isinstance(d.get("payload"), (bytes, bytearray)):
        payload = bytes(d["payload"])
    return Packet(
        id=int(d.get("id", next_packet_id())),
        kind=kind,
        source=int(d["source"]),
        group=str(d["group"]),
        seq=int(d["seq"]),
        previous_hop=int(d["previous_hop"]),
        ttl=int(d.get("ttl", 32)),
        hop_count=int(d.get("hop_count", 0)),
        join_query=JoinQueryHeader.from_dict(d.get("join_query")),
        payload=payload,
        ack_request=bool(d.get("ack_request", False)),
        from_fg_node=bool(d.get("from_fg_node", False)),
        entries=entries,
    )


def state_from_wire(d: dict[str, Any]) -> NodeState:
    pos = d.get("pos") or {"x": 0.0, "y": 0.0}
    routes = {
        int(k): RouteEntry(
            next_hop=int(v["next_hop"]),
            seq=int(v["seq"]),
            expires_at=float(v["expires_at"]),
        )
        for k, v in (d.get("routes") or {}).items()
    }
    fgs: dict[str, FGEntry] = {}
    for g, v in (d.get("forwarding_groups") or {}).items():
        fgs[str(g)] = FGEntry(
            expires_at=float(v["expires_at"]),
            refreshed_by=set(int(x) for x in v.get("refreshed_by", [])),
            last_refresh=float(v.get("last_refresh", 0.0)),
        )
    sessions = [
        SourceSession(
            group=str(s["group"]),
            next_seq=int(s.get("next_seq", 1)),
            last_data_at=float(s.get("last_data_at", 0.0)),
            next_refresh_at=s.get("next_refresh_at"),
            mesh_established=bool(s.get("mesh_established", False)),
        )
        for s in d.get("sessions", [])
    ]
    inbox = [
        InboxItem(
            message_id=str(i["message_id"]),
            group=str(i["group"]),
            source=int(i["source"]),
            app_kind=str(i["app_kind"]),
            body=i.get("body"),
            transfer_id=i.get("transfer_id"),
            index=i.get("index"),
            total=i.get("total"),
            t=float(i.get("t", 0.0)),
        )
        for i in d.get("inbox", [])
    ]
    return NodeState(
        id=int(d["id"]),
        pos=Position(float(pos.get("x", 0.0)), float(pos.get("y", 0.0))),
        range=float(d.get("range", 130.0)),
        members=set(str(g) for g in d.get("members", [])),
        routes=routes,
        forwarding_groups=fgs,
        last_seq_by_source={int(k): int(v) for k, v in (d.get("last_seq_by_source") or {}).items()},
        message_cache_size=int(d.get("message_cache_size", 0)),
        sessions=sessions,
        inbox=inbox,
    )


def params_to_wire(params: ProtocolParams) -> dict[str, Any]:
    return params.to_dict()
