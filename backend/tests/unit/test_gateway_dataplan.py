"""Gateway DataPlan store, dissemination, and connected-node monitor."""

from pathlib import Path

from odmrp_sim.model.data_plan import DataPlan, DisseminationRule, ProductMetadata
from odmrp_sim.services.data_plan_svc import load_data_plan
from odmrp_sim.services.gateway import GatewayService, InMemoryDataPlanStore
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = ROOT / "scenarios" / "overlay-mesh.yaml"
PLAN = ROOT / "fixtures" / "overlay" / "data-plan.json"


def test_dataplan_destinations_for_and_store_replace():
    plan = load_data_plan(PLAN)
    assert plan.destinations_for("imagery", 0) == [1, 2]
    assert plan.destinations_for("telemetry", 0) == []
    store = InMemoryDataPlanStore()
    store.replace(plan)
    assert store.get() is plan
    other = DataPlan(
        name="alt",
        dissemination=[DisseminationRule(product_type="imagery", destinations=[1])],
    )
    store.replace(other)
    assert store.get().destinations_for("imagery") == [1]


def test_gateway_disseminate_filtered_unicast():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    gw: GatewayService = eng.gateway
    gw.tick()
    assert {1, 2} <= set(gw.monitor.connected)

    product = ProductMetadata(
        product_id="prod-x",
        product_type="imagery",
        title="X",
        source_node=0,
        group="demo",
    )
    result = gw.on_product_available(product)
    eng.run_until(eng.scheduler.now + 0.05)
    assert result.matched
    assert result.destinations_sent == [1, 2]
    assert set(result.announcements) == {"product_meta", "product_loc"}

    # Direct tunnel peers should RX announcement packets from gateway
    rx_from_gw = [
        e
        for e in eng.bus.ring
        if e.kind == "rx" and e.payload.get("from") == 0 and e.node in (1, 2)
    ]
    assert rx_from_gw

    # No filtered TX to nodes outside destination set
    for e in eng.bus.ring:
        if e.kind != "tx" or e.payload.get("mode") != "unicast_over_neighbors_filtered":
            continue
        assert set(e.payload.get("neighbors") or []) <= {1, 2}


def test_monitor_prunes_on_disconnect_then_respects_new_plan():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    gw = eng.gateway
    plan = gw.store.get()
    assert plan is not None
    gw.tick()

    for n in eng.address_book.nodes[0].neighbors:  # type: ignore[union-attr]
        if n.peer_id == 2:
            n.status = "expired"
    sync = gw.tick()
    assert sync["removed"] == [2]
    assert plan.destinations_for("imagery", 0) == [1]

    status = gw.status()
    assert status["connected"] == [1]
    assert any(e["kind"] == "prune" for e in status["monitor_events"])

    result = gw.on_product_available(
        ProductMetadata(product_id="p2", product_type="imagery", source_node=0, group="demo")
    )
    assert result.destinations_sent == [1]


def test_snapshot_exposes_gateway_status():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    snap = eng.snapshot()
    assert "gateway" in snap["overlay"]
    assert snap["overlay"]["gateway"]["gateway_id"] == 0
    assert "dissemination" in (snap["overlay"].get("data_plan") or {})
