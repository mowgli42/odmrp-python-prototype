"""Executable coverage for basic_mesh.feature (Gherkin source of truth).

Mirrors pytest-bdd scenarios as plain pytest (pytest 9 + pytest-bdd 9
FixtureManager incompatibility).
"""

from pathlib import Path

from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

FEATURE = Path(__file__).resolve().parents[1] / "features" / "basic_mesh.feature"
SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "basic-mesh.yaml"


def test_source_with_data_originates_first_join_query_and_receivers_get_the_payload():
    """Scenario: Source with data originates first Join Query and receivers get the payload"""
    assert FEATURE.is_file()
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)

    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    assert fg == [1, 3]

    for rid in (3, 5):
        inbox = eng.hosts[rid].get_state().inbox
        assert any(i.body == "ODMRP works" for i in inbox)
