"""Markov RF link model — nested stay/re-eval transitions."""

from pathlib import Path

from odmrp_sim.model.topology import Topology
from odmrp_sim.services.link_model import arm_markov_links
from odmrp_sim.services.scenarios import list_scenarios, load_scenario, script_horizon
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = ROOT / "scenarios"
MARKOV = SCENARIOS / "markov-mesh.yaml"


def test_topology_disable_enable_emits_and_filters_neighbors():
    t = Topology(default_range=100)
    t.add(0, 0, 0)
    t.add(1, 50, 0)
    assert t.neighbors_of(0) == {1}
    assert t.geometric_pairs() == [(0, 1)]

    events: list[dict] = []
    t.on_change(lambda p: events.append(p))
    assert t.disable_link(0, 1) is True
    assert t.neighbors_of(0) == set()
    assert t.geometric_pairs() == [(0, 1)]
    assert any(e.get("op") == "link_down" for e in events)

    events.clear()
    assert t.enable_link(0, 1) is True
    assert t.neighbors_of(0) == {1}
    assert any(e.get("op") == "link_up" for e in events)


def test_markov_tick_flips_links_deterministically():
    eng = SimulationEngine(seed=7)
    eng.topology.default_range = 100
    eng.add_node(0, 0, node_id=0)
    eng.add_node(50, 0, node_id=1)
    assert eng.topology.links() == [[0, 1]]

    arm_markov_links(
        eng,
        {
            "type": "markov",
            "interval": 1.0,
            "seed": 99,
            "initial": "up",
            "p_keep_up": 0.0,  # always re-eval when UP
            "p_down_on_reeval": 1.0,  # always drop on re-eval
            "p_keep_down": 0.0,
            "p_up_on_reeval": 1.0,  # always restore on re-eval
        },
    )
    assert any(e.kind == "sim" and e.payload.get("op") == "link_model" for e in eng.bus.ring)
    assert eng.topology.links() == [[0, 1]]

    eng.run_until(1.0)
    assert eng.topology.links() == []  # forced down
    eng.run_until(2.0)
    assert eng.topology.links() == [[0, 1]]  # restored


def test_markov_mesh_scenario_arms_and_churns():
    eng = SimulationEngine()
    data = load_scenario(eng, MARKOV)
    assert data["link_model"]["type"] == "markov"
    assert any(e.kind == "sim" and e.payload.get("op") == "link_model" for e in eng.bus.ring)
    assert any(e.kind == "link_model" for e in eng.scheduler._heap)

    listed = {s["name"]: s for s in list_scenarios(SCENARIOS)}
    assert listed["markov-mesh"]["has_link_model"] is True

    # Advance through several ticks — expect at least one link_model_tick event.
    eng.run_until(3.5)
    ticks = [
        e
        for e in eng.bus.ring
        if e.kind == "topology" and e.payload.get("op") == "link_model_tick"
    ]
    assert len(ticks) >= 3

    # Scripted delivery still possible under churn for this seed.
    eng.run_until(script_horizon(data) + 0.5)
    delivered = {
        e.node
        for e in eng.bus.ring
        if e.kind == "deliver" and e.payload.get("group") == "demo"
    }
    assert len(delivered) >= data["expect"]["delivered_to_min"]


def test_identical_markov_traces_for_same_seed():
    def _trace():
        eng = SimulationEngine()
        load_scenario(eng, MARKOV)
        eng.run_until(5.0)
        return [
            (
                round(e.t, 6),
                e.payload.get("op"),
                e.payload.get("a"),
                e.payload.get("b"),
                e.payload.get("up"),
                e.payload.get("down"),
                e.payload.get("flips"),
            )
            for e in eng.bus.ring
            if e.kind == "topology"
            and e.payload.get("op") in {"link_up", "link_down", "link_model_tick"}
        ]

    assert _trace() == _trace()
