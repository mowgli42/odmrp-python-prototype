from pathlib import Path

from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = ROOT / "scenarios" / "basic-mesh.yaml"


def test_basic_mesh_forms_fg_and_delivers():
    eng = SimulationEngine()
    data = load_scenario(eng, SCENARIO)
    # Allow flood + JR return to settle
    eng.run_until(eng.scheduler.now + 0.5)

    fg = sorted(
        nid
        for nid, host in eng.hosts.items()
        if "demo" in host.get_state().forwarding_groups
    )
    assert fg == data["expect"]["fg_nodes"], f"FG={fg}"

    delivered = sorted(
        {
            ev.node
            for ev in eng.bus.ring
            if ev.kind == "deliver" and ev.payload.get("group") == "demo"
        }
    )
    assert delivered == data["expect"]["delivered_to"], f"delivered={delivered}"

    # Receivers have inbox text
    for rid in (3, 5):
        inbox = eng.hosts[rid].get_state().inbox
        assert any(i.body == "ODMRP works" for i in inbox)
