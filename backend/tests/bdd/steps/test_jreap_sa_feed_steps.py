"""Executable coverage for jreap_sa_feed.feature."""

from pathlib import Path

from odmrp_sim.services.jreap_endpoint import PRODUCT_TYPE_JREAP
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

FEATURE = Path(__file__).resolve().parents[1] / "features" / "jreap_sa_feed.feature"
SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "overlay-mesh.yaml"


def _settled():
    assert FEATURE.is_file()
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    assert fg, "expected FG mesh after settle"
    eng.gateway.tick()
    return eng


def test_interest_leads_to_productlocation_and_mock_sa_stream():
    """Scenario: Interest leads to ProductLocation and mock SA stream"""
    eng = _settled()
    result = eng.sa_feed.express_interest(3, PRODUCT_TYPE_JREAP, group="demo")
    assert result["mint"]["authorized"] is True
    mint = result["mint"]["mint"]
    assert mint["uri"]
    assert "Link16-JREAP-A" in mint["uri"] or mint["uri"].startswith("mock://")
    assert 3 in mint["destinations"]

    eng.run_until(eng.scheduler.now + 0.05)
    pumped = eng.sa_feed.pump(n_chunks=3)
    eng.run_until(eng.scheduler.now + 0.1)
    assert pumped

    rec3 = eng.sa_feed.record_for(3, "prod-link16-jreap-a")
    assert rec3 is not None
    assert rec3.bytes_consumed > 0
    assert rec3.opened_endpoint is False

    gw_rec = eng.sa_feed.record_for(eng.gateway_id, "prod-link16-jreap-a")
    assert gw_rec is not None and gw_rec.opened_endpoint is True
    # No non-gateway node opened the endpoint
    for nid, recs in eng.sa_feed.records.items():
        if nid == eng.gateway_id:
            continue
        for rec in recs.values():
            assert rec.opened_endpoint is False


def test_forwarder_consumes_without_a_second_connection():
    """Scenario: Forwarder consumes without a second connection"""
    eng = _settled()
    eng.sa_feed.express_interest(3, PRODUCT_TYPE_JREAP, group="demo")
    eng.run_until(eng.scheduler.now + 0.05)

    eng.sa_feed.pump(n_chunks=4)
    eng.run_until(eng.scheduler.now + 0.15)

    rec1 = eng.sa_feed.record_for(1, "prod-link16-jreap-a")
    assert rec1 is not None
    assert rec1.forwarding is True
    assert rec1.consuming is True
    assert rec1.bytes_consumed > 0
    assert rec1.opened_endpoint is False
    assert 3 in rec1.downstream_tunnels or rec1.chunks_tx > 0

    rec3 = eng.sa_feed.record_for(3, "prod-link16-jreap-a")
    assert rec3 is not None and rec3.bytes_consumed > 0
