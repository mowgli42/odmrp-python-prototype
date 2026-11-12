"""Scenario load schedules script ops; Play/step executes them; Reset restores t=0."""

from pathlib import Path

from odmrp_sim.services.scenarios import load_scenario, script_horizon
from odmrp_sim.sim.engine import SimMode, SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = ROOT / "scenarios" / "basic-mesh.yaml"


def test_load_scenario_schedules_without_advancing_time():
    eng = SimulationEngine()
    data = load_scenario(eng, SCENARIO)
    assert eng.scheduler.now == 0.0
    assert eng.mode == SimMode.PAUSED
    assert eng.scenario == "basic-mesh"
    script_n = len(data.get("script") or [])
    pending = sum(1 for e in eng.scheduler._heap if e.kind == "script")
    assert pending == script_n
    # Joins not applied yet
    assert "demo" not in eng.hosts[3].get_state().members
    assert not any(e.kind == "deliver" for e in eng.bus.ring)


def test_run_until_executes_script_progressively():
    eng = SimulationEngine()
    data = load_scenario(eng, SCENARIO)
    eng.run_until(0.05)
    assert "demo" in eng.hosts[3].get_state().members
    assert "demo" in eng.hosts[5].get_state().members
    assert not any(e.kind == "deliver" for e in eng.bus.ring)

    eng.run_until(script_horizon(data) + 0.5)
    delivered = sorted(
        {
            e.node
            for e in eng.bus.ring
            if e.kind == "deliver" and e.payload.get("group") == "demo"
        }
    )
    assert delivered == data["expect"]["delivered_to"]


def test_reload_restores_t0_paused():
    eng = SimulationEngine()
    data = load_scenario(eng, SCENARIO)
    eng.run_until(script_horizon(data) + 0.5)
    assert eng.scheduler.now > 1.0

    load_scenario(eng, SCENARIO)
    assert eng.scheduler.now == 0.0
    assert eng.mode == SimMode.PAUSED
    assert "demo" not in eng.hosts[3].get_state().members
    assert sum(1 for e in eng.scheduler._heap if e.kind == "script") >= 1
