"""Executable coverage for markov_links.feature."""

from pathlib import Path

from odmrp_sim.services.link_model import arm_markov_links
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

FEATURE = Path(__file__).resolve().parents[1] / "features" / "markov_links.feature"
SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "markov-mesh.yaml"


def test_markov_link_model_flaps_geometric_neighbors_on_an_interval():
    """Scenario: Markov link model flaps geometric neighbors on an interval"""
    assert FEATURE.is_file()
    eng = SimulationEngine(seed=1)
    eng.topology.default_range = 100
    eng.add_node(0, 0, node_id=0)
    eng.add_node(40, 0, node_id=1)
    assert eng.topology.neighbors_of(0) == {1}

    arm_markov_links(
        eng,
        {
            "type": "markov",
            "interval": 1.0,
            "seed": 1,
            "initial": "up",
            "p_keep_up": 0.0,
            "p_down_on_reeval": 1.0,
            "p_keep_down": 0.0,
            "p_up_on_reeval": 1.0,
        },
    )
    eng.run_until(1.0)
    assert eng.topology.neighbors_of(0) == set()
    eng.run_until(2.0)
    assert eng.topology.neighbors_of(0) == {1}


def test_markov_mesh_scenario_arms_the_link_model_at_load():
    """Scenario: markov-mesh scenario arms the link model at load"""
    assert FEATURE.is_file()
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    assert any(e.kind == "sim" and e.payload.get("op") == "link_model" for e in eng.bus.ring)
    assert any(e.kind == "link_model" for e in eng.scheduler._heap)
