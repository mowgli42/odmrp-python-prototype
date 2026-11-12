"""Executable coverage for scenario_playback.feature."""

from __future__ import annotations

from pathlib import Path

from odmrp_sim.api.session import Session
from odmrp_sim.services.scenarios import load_scenario, script_horizon
from odmrp_sim.sim.engine import SimMode, SimulationEngine

FEATURE = Path(__file__).resolve().parents[1] / "features" / "scenario_playback.feature"
SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "basic-mesh.yaml"


def _assert_feature() -> None:
    assert FEATURE.is_file(), f"missing Gherkin feature: {FEATURE}"


def _members_for(eng: SimulationEngine, group: str) -> set[int]:
    return {
        nid
        for nid, h in eng.hosts.items()
        if group in h.get_state().members
    }


def _script_ops_pending(eng: SimulationEngine) -> int:
    return sum(1 for ev in eng.scheduler._heap if ev.kind == "script")


def _load_playback() -> tuple[SimulationEngine, dict]:
    eng = SimulationEngine()
    data = load_scenario(eng, SCENARIO)
    return eng, data


def test_load_leaves_simulation_paused_at_t0_ready_to_play():
    """Scenario: Load leaves simulation paused at t=0 ready to play"""
    _assert_feature()
    eng, data = _load_playback()
    assert eng.scheduler.now == 0.0
    assert eng.mode == SimMode.PAUSED
    assert _members_for(eng, "demo") == set()
    assert not any(e.kind == "deliver" for e in eng.bus.ring)
    assert _script_ops_pending(eng) == len(data.get("script") or [])


def test_play_at_1x_executes_scripted_events_progressively():
    """Scenario: Play at 1x executes scripted events progressively"""
    _assert_feature()
    eng, data = _load_playback()
    # Simulate the session run loop at 1×: many small steps through the script.
    horizon = script_horizon(data) + 0.5
    while eng.scheduler.now < horizon - 1e-12:
        eng.step(0.020)
        # Mid-run: after joins (at 0) but before text (at 1), members exist and
        # delivery has not completed yet.
        if 0.05 < eng.scheduler.now < 0.9:
            assert 3 in _members_for(eng, "demo")
            assert 5 in _members_for(eng, "demo")
            assert not any(
                e.kind == "deliver" and e.payload.get("group") == "demo" for e in eng.bus.ring
            )

    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    assert fg == [1, 3]
    for rid in (3, 5):
        inbox = eng.hosts[rid].get_state().inbox
        assert any(i.body == "ODMRP works" for i in inbox)
    assert eng.scheduler.now > 1.0


def test_reset_restores_clean_initial_state_at_t0():
    """Scenario: Reset restores clean initial state at t=0"""
    _assert_feature()
    import asyncio
    import yaml

    async def _run() -> None:
        sess = Session()
        await sess.load_named_scenario("basic-mesh")
        data = yaml.safe_load(SCENARIO.read_text())
        # Drive past the script once (as if the user pressed Play at 1×).
        while sess.engine.scheduler.now < script_horizon(data) + 0.5:
            async with sess._lock:
                sess.engine.step(0.020)
        assert sess.engine.scheduler.now > 1.0
        assert any(e.kind == "deliver" for e in sess.engine.bus.ring)

        await sess.reset()
        eng = sess.engine
        assert eng.scheduler.now == 0.0
        assert eng.mode == SimMode.PAUSED
        assert _members_for(eng, "demo") == set()
        assert not any(e.kind == "deliver" for e in eng.bus.ring)
        assert _script_ops_pending(eng) >= 1
        # Ready to play again: one step fires the at=0 joins.
        eng.step(0.020)
        assert 3 in _members_for(eng, "demo")

    asyncio.run(_run())
