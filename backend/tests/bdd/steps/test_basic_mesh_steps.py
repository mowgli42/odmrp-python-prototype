from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

scenarios("../features/basic_mesh.feature")

SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "basic-mesh.yaml"


@pytest.fixture
def ctx():
    return {}


@given("the basic-mesh scenario is loaded")
def load_basic(ctx):
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    ctx["eng"] = eng


@when("the simulation settles")
def settle(ctx):
    eng = ctx["eng"]
    eng.run_until(eng.scheduler.now + 0.5)


@then('the forwarding group for "demo" is nodes 1 and 3')
def check_fg(ctx):
    eng = ctx["eng"]
    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    assert fg == [1, 3]


@then('nodes 3 and 5 have delivered "ODMRP works"')
def check_deliver(ctx):
    eng = ctx["eng"]
    for rid in (3, 5):
        inbox = eng.hosts[rid].get_state().inbox
        assert any(i.body == "ODMRP works" for i in inbox)
