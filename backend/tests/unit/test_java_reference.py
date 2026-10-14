"""Differential tests: Java ODMRPNode vs Python (specs/java-reference/spec.md)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from odmrp_sim.protocol.external_node import ExternalProcessNode
from odmrp_sim.protocol.wire import packet_from_wire, packet_to_wire
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = ROOT / "scenarios" / "basic-mesh.yaml"
JAVA_NODE = ROOT / "java-node"
JAR = JAVA_NODE / "dist" / "odmrp-java-node.jar"
JAVA_BIN = os.environ.get("JAVA_HOME", str(Path.home() / "tools" / "jdk")) + "/bin/java"


def _java_available() -> bool:
    return Path(JAVA_BIN).is_file() or shutil.which("java") is not None


def _ensure_jar() -> Path:
    if JAR.is_file():
        return JAR
    if not _java_available():
        pytest.skip("JDK not available")
    subprocess.run(["bash", str(JAVA_NODE / "build.sh")], check=True, cwd=JAVA_NODE)
    assert JAR.is_file(), f"build did not produce {JAR}"
    return JAR


@pytest.fixture(scope="module")
def java_jar() -> Path:
    return _ensure_jar()


def _compact(eng: SimulationEngine):
    events = []
    for e in eng.bus.ring:
        if e.kind not in {"tx", "state.fg", "deliver"}:
            continue
        if e.kind == "tx":
            pkt = e.payload.get("packet") or {}
            events.append(
                (
                    round(e.t, 6),
                    e.kind,
                    e.node,
                    pkt.get("kind"),
                    pkt.get("source"),
                    pkt.get("group"),
                    pkt.get("seq"),
                    pkt.get("previous_hop"),
                    tuple(e.payload.get("neighbors", [])),
                )
            )
        elif e.kind == "deliver":
            events.append((round(e.t, 6), e.kind, e.node, e.payload.get("group")))
        else:
            events.append(
                (
                    round(e.t, 6),
                    e.kind,
                    e.node,
                    e.payload.get("op"),
                    e.payload.get("group"),
                )
            )
    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    delivered = sorted(
        {
            ev.node
            for ev in eng.bus.ring
            if ev.kind == "deliver" and ev.payload.get("group") == "demo"
        }
    )
    return events, fg, delivered


def _java_bin() -> str | None:
    if Path(JAVA_BIN).is_file():
        return JAVA_BIN
    return shutil.which("java")


def _run(default_impl: str, node_impls: dict | None = None, jar: Path | None = None):
    eng = SimulationEngine(
        default_impl=default_impl,
        java_jar=jar,
        java_bin=_java_bin(),
    )
    if node_impls:
        eng.set_node_impls(node_impls)
    data = load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    compact, fg, delivered = _compact(eng)
    for host in eng.hosts.values():
        if isinstance(host.impl, ExternalProcessNode):
            host.impl.close()
    return data, compact, fg, delivered


def test_java_configure_and_get_state(java_jar: Path):
    node = ExternalProcessNode.java(jar=java_jar, java_bin=JAVA_BIN if Path(JAVA_BIN).exists() else None)
    try:
        from odmrp_sim.model.params import ProtocolParams

        node.configure(4, ProtocolParams(), 42)
        st = node.get_state()
        assert st.id == 4
        assert st.members == set()
        assert st.routes == {}
        assert st.forwarding_groups == {}
    finally:
        node.close()


def test_host_spawns_java_by_command(java_jar: Path):
    eng = SimulationEngine(default_impl="java", java_jar=java_jar)
    eng.add_node(0, 0, node_id=4)
    st = eng.hosts[4].get_state()
    assert st.id == 4
    eng.hosts[4].impl.close()


def test_all_java_basic_mesh_matches_python(java_jar: Path):
    _, py_c, py_fg, py_d = _run("python")
    _, j_c, j_fg, j_d = _run("java", jar=java_jar)
    assert py_fg == j_fg == [1, 3]
    assert py_d == j_d == [3, 5]
    assert py_c == j_c


def test_mixed_python_java_basic_mesh_delivers(java_jar: Path):
    impls = {0: "python", 1: "java", 2: "python", 3: "java", 4: "python", 5: "java"}
    data, _, fg, delivered = _run("python", node_impls=impls, jar=java_jar)
    assert delivered == data["expect"]["delivered_to"]
    assert set(fg).issubset({1, 2, 3, 4})
    assert fg  # non-empty


def test_wire_packet_roundtrip_payload_b64():
    from odmrp_sim.model.app_payload import AppPayload
    from odmrp_sim.model.packets import make_data_with_jq

    payload = AppPayload(kind="text", message_id="m1", body="hi").encode()
    pkt = make_data_with_jq(source=0, group="demo", seq=1, payload=payload, ttl=32)
    wire = packet_to_wire(pkt)
    assert "payload_b64" in wire
    back = packet_from_wire(wire)
    assert back.payload == payload
    assert back.kind == pkt.kind
