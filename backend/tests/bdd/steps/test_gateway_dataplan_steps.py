"""Executable coverage for gateway_dataplan.feature (Gherkin source of truth)."""

from pathlib import Path

from odmrp_sim.model.data_plan import ProductMetadata
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

FEATURE = Path(__file__).resolve().parents[1] / "features" / "gateway_dataplan.feature"
SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "overlay-mesh.yaml"


def _load():
    assert FEATURE.is_file()
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    assert eng.overlay_mode == "tunnel"
    assert eng.gateway.store.get() is not None
    eng.gateway.tick()
    return eng


def test_dataplan_evaluation_announces_only_to_named_destinations():
    """Scenario: DataPlan evaluation announces only to named destinations"""
    eng = _load()
    plan = eng.gateway.store.get()
    assert plan is not None
    dests = set(plan.destinations_for("imagery", 0))
    assert dests == {1, 2}

    product = next(p for p in plan.products if p.product_id == "prod-isr-001")
    result = eng.gateway.on_product_available(product)
    eng.run_until(eng.scheduler.now + 0.05)

    assert result.matched
    assert set(result.destinations_sent) <= dests
    assert set(result.destinations_sent) <= set(eng.gateway.monitor.connected)
    assert set(result.announcements) == {"product_meta", "product_loc"}

    ann_txs = [
        e
        for e in eng.bus.ring
        if e.kind == "tx"
        and e.node == eng.gateway_id
        and e.payload.get("mode") == "unicast_over_neighbors_filtered"
    ]
    assert ann_txs
    for e in ann_txs:
        peers = set(e.payload.get("neighbors") or [])
        assert peers <= dests
        assert peers  # at least one connected destination


def test_connectivity_loss_updates_dataplan_destinations():
    """Scenario: Connectivity loss updates DataPlan destinations"""
    eng = _load()
    plan = eng.gateway.store.get()
    assert plan is not None
    assert plan.destinations_for("imagery", 0) == [1, 2]

    # Soft-disconnect peer 2 from the gateway address book
    entry = eng.address_book.nodes[0]  # type: ignore[union-attr]
    for n in entry.neighbors:
        if n.peer_id == 2:
            n.status = "down"
    sync = eng.gateway.tick()
    assert 2 in sync["removed"]
    assert any(c.get("removed") == [2] or 2 in c.get("removed", []) for c in sync["prunes"])
    assert plan.destinations_for("imagery", 0) == [1]

    product = ProductMetadata(
        product_id="prod-isr-002",
        product_type="imagery",
        title="After disconnect",
        source_node=0,
        group="demo",
    )
    result = eng.gateway.on_product_available(product)
    eng.run_until(eng.scheduler.now + 0.05)
    assert result.destinations_planned == [1]
    assert result.destinations_sent == [1]
    assert 2 not in result.destinations_sent
