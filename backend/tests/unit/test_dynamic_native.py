"""Dynamic mesh layout + native process nodes with log monitoring."""

from pathlib import Path

from odmrp_sim.services.scenarios import list_scenarios, load_scenario
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = ROOT / "scenarios"
DYNAMIC = SCENARIOS / "dynamic-mesh.yaml"


def test_list_scenarios_includes_dynamic_mesh():
    names = {s["name"] for s in list_scenarios(SCENARIOS)}
    assert "basic-mesh" in names
    assert "dynamic-mesh" in names
    dyn = next(s for s in list_scenarios(SCENARIOS) if s["name"] == "dynamic-mesh")
    assert dyn["nodes"] == 16
    assert dyn["has_mobility"] is True
    assert dyn["native_nodes"] == 2


def test_dynamic_mesh_forms_and_delivers():
    eng = SimulationEngine()
    data = load_scenario(eng, DYNAMIC)
    eng.run_until(eng.scheduler.now + 0.5)

    assert len(eng.hosts) == 16
    native_ids = sorted(i for i, h in eng.hosts.items() if h.impl_name == "native")
    assert native_ids == data["expect"]["native_nodes"]

    delivered = sorted(
        {
            ev.node
            for ev in eng.bus.ring
            if ev.kind == "deliver" and ev.payload.get("group") == "demo"
        }
    )
    assert len(delivered) >= data["expect"]["delivered_to_min"], f"delivered={delivered}"

    # Native monitor logs should exist after configure/traffic
    for nid in native_ids:
        host = eng.hosts[nid]
        assert host.log_path is not None
        assert host.log_path.is_file(), host.log_path
        text = host.log_path.read_text(encoding="utf-8")
        assert "configure" in text or "→" in text
        # Close processes cleanly
        from odmrp_sim.protocol.external_node import ExternalProcessNode

        if isinstance(host.impl, ExternalProcessNode):
            host.impl.close()


def test_scripted_move_and_mobility_armed():
    eng = SimulationEngine()
    load_scenario(eng, DYNAMIC)
    # Script restores node 1 to the grid after the corridor break.
    pos = eng.hosts[1].pos
    assert abs(pos.x - 120) < 1e-6 and abs(pos.y - 0) < 1e-6
    # Waypoint mobility should have been armed during load.
    assert any(e.kind == "sim" and e.payload.get("op") == "mobility" for e in eng.bus.ring)
    # Advance past the first mobility tick — movers leave their spawn points.
    t0 = eng.scheduler.now
    eng.run_until(t0 + 1.0)
    moved = eng.hosts[4].pos
    assert abs(moved.x - 0) > 1e-3 or abs(moved.y - 120) > 1e-3
    for h in eng.hosts.values():
        from odmrp_sim.protocol.external_node import ExternalProcessNode

        if isinstance(h.impl, ExternalProcessNode):
            h.impl.close()


def test_move_op_on_basic_style_fixture(tmp_path: Path):
    yaml_path = tmp_path / "tiny.yaml"
    yaml_path.write_text(
        """
name: tiny
seed: 1
range: 130
nodes:
  - { id: 0, x: 0, y: 0 }
  - { id: 1, x: 100, y: 0 }
script:
  - { at: 0.5, op: move, node: 1, x: 200, y: 50 }
""",
        encoding="utf-8",
    )
    eng = SimulationEngine()
    load_scenario(eng, yaml_path)
    assert eng.hosts[1].pos.x == 200
    assert eng.hosts[1].pos.y == 50
