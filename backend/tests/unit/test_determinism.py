from pathlib import Path

from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

SCENARIO = Path(__file__).resolve().parents[3] / "scenarios" / "basic-mesh.yaml"


def _run():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    events = [
        (e.t, e.kind, e.node, {k: v for k, v in e.payload.items() if k != "packet"})
        for e in eng.bus.ring
        if e.kind in {"tx", "rx", "state.fg", "deliver", "drop"}
    ]
    # Strip packet ids from tx for stability — compare kinds + neighbors instead
    compact = []
    for t, kind, node, payload in events:
        if kind == "tx":
            compact.append((round(t, 6), kind, node, tuple(payload.get("neighbors", []))))
        elif kind == "rx":
            compact.append((round(t, 6), kind, node, payload.get("from"), payload.get("pkind")))
        elif kind == "deliver":
            compact.append((round(t, 6), kind, node, payload.get("group")))
        elif kind == "state.fg":
            compact.append((round(t, 6), kind, node, payload.get("op"), payload.get("group")))
        else:
            compact.append((round(t, 6), kind, node, payload.get("reason")))
    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    return compact, fg


def test_identical_traces_across_runs():
    a, fg_a = _run()
    b, fg_b = _run()
    assert fg_a == fg_b == [1, 3]
    assert a == b
