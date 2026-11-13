"""OMS SA distribution — pure DATA after mesh, payloads, publisher/consumer, metrics."""

from pathlib import Path

import pytest

from odmrp_sim.model.app_payload import (
    AppPayload,
    make_oms_position,
    make_oms_status,
)
from odmrp_sim.model.packets import PacketKind
from odmrp_sim.protocol.python_node import PythonODMRPNode
from odmrp_sim.services.oms_sa import OmsSaConfig, OmsSaConfigError
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
OMS_SCENARIO = ROOT / "scenarios" / "oms-sa-mesh.yaml"
OVERLAY = ROOT / "scenarios" / "overlay-mesh.yaml"


def test_oms_payload_roundtrip_status_and_position():
    st = make_oms_status(
        message_id="m1",
        platform_id="plt-7",
        generated_at="t=1.0",
        readiness="YELLOW",
        fuel_percent=55.5,
        weapons_remaining=2,
        active_task_count=1,
        subsystems={"datalink": "ONLINE"},
    )
    raw = st.encode()
    back = AppPayload.decode(raw)
    assert back.kind == "oms_status"
    assert back.platform_id == "plt-7"
    assert back.readiness == "YELLOW"
    assert back.fuel_percent == 55.5
    assert back.subsystems["datalink"] == "ONLINE"

    pos = make_oms_position(
        message_id="m2",
        platform_id="plt-7",
        generated_at="t=2.0",
        latitude=12.5,
        longitude=-81.0,
        heading=90.0,
    )
    back2 = AppPayload.decode(pos.encode())
    assert back2.kind == "oms_position"
    assert back2.latitude == 12.5
    assert back2.longitude == -81.0
    assert back2.heading == 90.0


def test_foreign_platform_id_originate_rejected():
    eng = SimulationEngine()
    eng.add_node(0, 0, 130, node_id=0)
    eng.oms_sa.configure(
        {"group": "oms.sa", "production": False, "platform_ids": {"0": "plt-0"}},
        validate=True,
    )
    eng.oms_sa.activate([0])
    with pytest.raises(OmsSaConfigError, match="platform_id"):
        bad = make_oms_status(
            message_id="x",
            platform_id="plt-OTHER",
            generated_at="t=0",
        )
        eng.oms_sa._originate_guarded(0, bad)
    assert eng.oms_sa.metrics()["rejected_foreign"] >= 1


def test_production_rejects_subsecond_periods():
    eng = SimulationEngine()
    with pytest.raises(OmsSaConfigError, match="below 1.0"):
        eng.oms_sa.configure(
            {"status_period_s": 0.5, "position_period_s": 5.0, "production": True},
            validate=True,
        )


def test_originate_pure_data_after_mesh_established():
    node = PythonODMRPNode()
    node.configure(0, node.params, 1)
    # Seed a session as if JR returned; node-global seq continues from _next_seq
    from odmrp_sim.model.state import SourceSession

    node._next_seq = 5
    node._sessions["oms.sa"] = SourceSession(group="oms.sa", next_seq=5, mesh_established=True)
    pkts = node.originate("oms.sa", b'{"kind":"oms_position","message_id":"a","platform_id":"0"}', 1.0)
    assert len(pkts) == 1
    assert pkts[0].kind == PacketKind.DATA
    assert pkts[0].join_query is None
    assert pkts[0].seq == 5


def test_originate_jq_before_mesh():
    node = PythonODMRPNode()
    node.configure(0, node.params, 1)
    pkts = node.originate("oms.sa", b"hello", 0.0)
    assert pkts[0].kind == PacketKind.JOIN_QUERY
    assert pkts[0].join_query is not None


def test_refresh_still_emits_jq_while_pure_data_flows():
    eng = SimulationEngine()
    data = load_scenario(eng, OVERLAY)
    # Form classic demo mesh first
    eng.run_until(2.0)
    # Manually mark source 0 mesh established and join oms.sa peers
    eng.oms_sa.configure(
        {
            "group": "oms.sa",
            "status_period_s": 20,
            "position_period_s": 5,
            "production": False,
            "platform_ids": {"0": "plt-0", "3": "plt-3", "5": "plt-5"},
        }
    )
    for nid in (0, 3, 5):
        eng.join(nid, "oms.sa")
    # Bootstrap mesh for oms.sa from 0
    eng.oms_sa.publish_status(0)
    eng.run_until(eng.scheduler.now + 1.0)
    st0 = eng.hosts[0].get_state()
    sess = next(s for s in st0.sessions if s.group == "oms.sa")
    assert sess.mesh_established

    jq_before = _count_jq(eng)
    # Several pure DATA positions
    for _ in range(3):
        eng.oms_sa.publish_position(0)
        eng.run_until(eng.scheduler.now + 0.05)
    jq_mid = _count_jq(eng)
    assert jq_mid == jq_before  # no new JQ from pure DATA originates

    # Advance past refresh interval — expect new JQ
    eng.run_until(eng.scheduler.now + eng.params.route_refresh_interval + 0.2)
    jq_after = _count_jq(eng)
    assert jq_after > jq_mid


def test_multi_source_oms_sa_scenario_delivers_and_limits_jq():
    eng = SimulationEngine()
    data = load_scenario(eng, OMS_SCENARIO)
    assert eng.oms_sa.active == {0, 1, 2, 3, 5}
    # Formation + first position/status timers
    eng.run_until(8.0)

    # Each active publisher should have mesh_established for oms.sa
    for nid in (0, 1, 2, 3, 5):
        sess = next(
            (s for s in eng.hosts[nid].get_state().sessions if s.group == "oms.sa"),
            None,
        )
        assert sess is not None, f"node {nid} missing oms.sa session"
        assert sess.mesh_established, f"node {nid} mesh not established"

    jq_at_mesh = _count_jq(eng)
    pos_before = eng.oms_sa.metrics()["position_originates"]

    # Window of pure DATA only (no new JQ from originates)
    for nid in (0, 1, 2, 3, 5):
        eng.oms_sa.publish_position(nid)
    eng.run_until(eng.scheduler.now + 0.5)
    jq_after_burst = _count_jq(eng)
    assert jq_after_burst == jq_at_mesh, "pure DATA position burst must not Join-Query-flood"

    # Peer views: each consumer should see other platforms' positions
    for consumer in (0, 3, 5):
        snap = eng.oms_sa.snapshot(consumer)
        peer_ids = {pid for pid in snap if pid != eng.oms_sa.platform_id_for(consumer)}
        assert len(peer_ids) >= 2, f"consumer {consumer} peers={peer_ids}"

    m = eng.oms_sa.metrics()
    assert m["position_originates"] > pos_before
    assert m["delivers_oms_position"] >= 5


def test_newer_generated_at_wins_and_stale():
    eng = SimulationEngine()
    eng.add_node(0, 0, 130, node_id=0)
    eng.add_node(100, 0, 130, node_id=1)
    eng.oms_sa.configure(
        {
            "group": "oms.sa",
            "position_period_s": 5.0,
            "status_period_s": 20.0,
            "production": False,
            "platform_ids": {"0": "plt-0", "1": "plt-1"},
        }
    )
    eng.oms_sa.activate([0, 1])
    from odmrp_sim.model.app_payload import make_oms_position

    p_old = make_oms_position(
        message_id="a", platform_id="plt-0", generated_at="t=1.0", latitude=1, longitude=2
    )
    p_new = make_oms_position(
        message_id="b", platform_id="plt-0", generated_at="t=3.0", latitude=3, longitude=4
    )
    eng.oms_sa.on_deliver(1, app_kind="oms_position", platform_id="plt-0", source=0, payload=p_old, now=1.0)
    eng.oms_sa.on_deliver(1, app_kind="oms_position", platform_id="plt-0", source=0, payload=p_new, now=3.0)
    eng.oms_sa.on_deliver(1, app_kind="oms_position", platform_id="plt-0", source=0, payload=p_old, now=4.0)
    view = eng.oms_sa.views[1]["plt-0"]
    assert view.position is not None
    assert view.position.latitude == 3.0
    assert view.position.generated_at == "t=3.0"

    # Age past 2× period
    eng.scheduler.now = 3.0 + 10.0 + 0.1
    eng.oms_sa._refresh_stale(eng.scheduler.now)
    assert view.position.stale is True


def test_pure_data_not_forwarded_by_non_fg():
    eng = SimulationEngine()
    load_scenario(eng, OVERLAY)
    eng.run_until(2.0)
    # Node 4 is non-FG non-member in overlay demo
    eng.join(0, "oms.sa")
    eng.join(3, "oms.sa")
    eng.join(5, "oms.sa")
    eng.oms_sa.configure(
        {"group": "oms.sa", "production": False, "platform_ids": {"0": "plt-0"}},
        validate=True,
    )
    eng.oms_sa.publish_status(0)
    eng.run_until(eng.scheduler.now + 1.0)
    assert next(s for s in eng.hosts[0].get_state().sessions if s.group == "oms.sa").mesh_established

    drops_before = sum(1 for e in eng.bus.ring if e.kind == "drop" and e.payload.get("reason") == "not_fg")
    eng.oms_sa.publish_position(0)
    eng.run_until(eng.scheduler.now + 0.5)
    # Node 4 should not forward; may or may not see packet depending on tunnels
    st4 = eng.hosts[4].get_state()
    assert "oms.sa" not in st4.forwarding_groups


def _count_jq(eng: SimulationEngine) -> int:
    n = 0
    for ev in eng.bus.ring:
        if ev.kind != "tx":
            continue
        pkt = (ev.payload or {}).get("packet") or {}
        if pkt.get("kind") == "JOIN_QUERY" or pkt.get("join_query"):
            n += 1
    return n
