"""JREAP-A interest, mint, stream relay, consume-while-forward."""

from pathlib import Path

from odmrp_sim.services.jreap_endpoint import PRODUCT_TYPE_JREAP, MockSaSource, mock_jreap_frame
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = ROOT / "scenarios" / "overlay-mesh.yaml"


def test_mock_jreap_frame_roundtrip():
    frame = mock_jreap_frame(7, track_id=2)
    assert frame.startswith(b"JREA")
    src = MockSaSource()
    a = src.read()
    b = src.read()
    assert a != b and src.frames_emitted == 2


def test_unauthorized_interest_denied():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    # Node 4 is not in Link16-JREAP-A destinations
    result = eng.sa_feed.express_interest(4, PRODUCT_TYPE_JREAP)
    assert result["mint"]["authorized"] is False
    assert eng.sa_feed._active_product is None


def test_prune_tears_down_leaf_subscription():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    eng.sa_feed.express_interest(3, PRODUCT_TYPE_JREAP)
    eng.sa_feed.pump(2)
    eng.run_until(eng.scheduler.now + 0.1)
    pid = "prod-link16-jreap-a"
    assert eng.sa_feed.record_for(3, pid) is not None

    # Remove 3 from plan destinations via monitor prune path
    plan = eng.gateway.store.get()
    assert plan is not None
    for rule in plan.dissemination:
        if rule.product_type == PRODUCT_TYPE_JREAP:
            rule.destinations = [d for d in rule.destinations if d != 3]
    eng.sa_feed.on_destinations_pruned([3])
    assert eng.sa_feed.record_for(3, pid) is None
    # Gateway / forwarder records may remain
    assert eng.sa_feed.record_for(eng.gateway_id, pid) is not None


def test_interest_stream_end_to_end():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    consumed: list[tuple[int, int]] = []

    def _cb(nid, pid, data, meta):
        consumed.append((nid, len(data)))

    eng.sa_feed.add_consumer(_cb)
    result = eng.sa_feed.express_interest(3, PRODUCT_TYPE_JREAP)
    assert result["mint"]["authorized"]
    eng.sa_feed.pump(5)
    eng.run_until(eng.scheduler.now + 0.2)
    nodes = {n for n, _ in consumed}
    assert 3 in nodes
    # Forwarder 1 also consumes
    assert 1 in nodes
    assert eng.sa_feed.record_for(1, "prod-link16-jreap-a").opened_endpoint is False
