"""Executable coverage for oms_sa_distribution.feature."""

from pathlib import Path

import pytest

from odmrp_sim.model.packets import PacketKind
from odmrp_sim.services.oms_sa import OmsSaConfigError
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

FEATURE = Path(__file__).resolve().parents[1] / "features" / "oms_sa_distribution.feature"
OMS_SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "oms-sa-mesh.yaml"
OVERLAY = Path(__file__).resolve().parents[4] / "scenarios" / "overlay-mesh.yaml"


def _count_jq(eng: SimulationEngine) -> int:
    n = 0
    for ev in eng.bus.ring:
        if ev.kind != "tx":
            continue
        pkt = (ev.payload or {}).get("packet") or {}
        if pkt.get("kind") == "JOIN_QUERY" or pkt.get("join_query"):
            n += 1
    return n


def test_subsequent_position_reports_are_pure_data():
    """Scenario: Subsequent position reports are pure DATA"""
    assert FEATURE.is_file()
    eng = SimulationEngine()
    load_scenario(eng, OVERLAY)
    eng.run_until(2.0)
    eng.oms_sa.configure(
        {"group": "oms.sa", "production": False, "platform_ids": {"0": "plt-0", "3": "plt-3", "5": "plt-5"}}
    )
    for nid in (0, 3, 5):
        eng.join(nid, "oms.sa")
    eng.oms_sa.publish_status(0)
    eng.run_until(eng.scheduler.now + 1.0)
    assert next(s for s in eng.hosts[0].get_state().sessions if s.group == "oms.sa").mesh_established

    # Capture next originate packets via node impl
    host = eng.hosts[0]
    before_tx = _count_jq(eng)
    eng.oms_sa.publish_position(0)
    eng.run_until(eng.scheduler.now + 0.2)
    assert _count_jq(eng) == before_tx

    # Last DATA tx from 0 should be pure DATA
    data_txs = [
        ev
        for ev in eng.bus.ring
        if ev.kind == "tx"
        and ev.node == 0
        and ((ev.payload or {}).get("packet") or {}).get("kind") == "DATA"
        and ((ev.payload or {}).get("packet") or {}).get("group") == "oms.sa"
    ]
    assert data_txs
    assert data_txs[-1].payload["packet"].get("join_query") is None


def test_mesh_refresh_still_emits_join_query_on_interval():
    """Scenario: Mesh refresh still emits Join Query on interval"""
    eng = SimulationEngine()
    load_scenario(eng, OVERLAY)
    eng.run_until(2.0)
    eng.oms_sa.configure(
        {"group": "oms.sa", "production": False, "platform_ids": {"0": "plt-0", "3": "plt-3", "5": "plt-5"}}
    )
    for nid in (0, 3, 5):
        eng.join(nid, "oms.sa")
    eng.oms_sa.publish_status(0)
    eng.run_until(eng.scheduler.now + 1.0)
    jq_before = _count_jq(eng)
    eng.oms_sa.publish_position(0)
    eng.run_until(eng.scheduler.now + eng.params.route_refresh_interval + 0.3)
    assert _count_jq(eng) > jq_before


def test_multi_source_status_delivery_without_re_originate():
    """Scenario: Multi-source status delivery without re-originate"""
    eng = SimulationEngine()
    load_scenario(eng, OMS_SCENARIO)
    eng.run_until(8.0)
    jq = _count_jq(eng)
    for nid in sorted(eng.oms_sa.active):
        eng.oms_sa.publish_position(nid)
    eng.run_until(eng.scheduler.now + 0.5)
    assert _count_jq(eng) == jq
    snap = eng.oms_sa.snapshot(3)
    assert len(snap) >= 2


def test_reject_unsafe_production_rates():
    """Scenario: Reject unsafe production rates"""
    eng = SimulationEngine()
    with pytest.raises(OmsSaConfigError):
        eng.oms_sa.configure(
            {"status_period_s": 0.2, "position_period_s": 5.0, "production": True},
            validate=True,
        )
