"""Localhost neighbour-UDP basic-mesh smoke (no Docker)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import yaml

from odmrp_sim.dataplane.neighbour_udp import AgentConfig, NeighbourUdpAgent

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = ROOT / "scenarios" / "basic-mesh.yaml"


def _build_configs(base_port: int = 19000) -> list[AgentConfig]:
    data = yaml.safe_load(SCENARIO.read_text())
    import math

    nodes = {int(n["id"]): (float(n["x"]), float(n["y"])) for n in data["nodes"]}
    range_ = float(data.get("range", 130))
    neigh: dict[int, list[int]] = {}
    for a, (x, y) in nodes.items():
        neigh[a] = sorted(
            b
            for b, (u, v) in nodes.items()
            if a != b and math.hypot(x - u, y - v) <= range_ + 1e-9
        )
    scripts: dict[int, list] = {i: [] for i in nodes}
    for step in data.get("script") or []:
        s = dict(step)
        nid = int(s.pop("node"))
        if s.get("op") == "text":
            s["message_id"] = "udp-local-msg"
        scripts[nid].append(s)
    params = dict(data.get("params") or {})
    params["jq_jitter"] = 0.0
    params["hop_delay"] = 0.0
    cfgs = []
    for nid, (x, y) in nodes.items():
        peers = {
            p: {"host": "127.0.0.1", "port": base_port + p} for p in neigh[nid]
        }
        cfgs.append(
            AgentConfig.from_dict(
                {
                    "node_id": nid,
                    "impl": "python",
                    "listen": f"127.0.0.1:{base_port + nid}",
                    "pos": {"x": x, "y": y},
                    "range": range_,
                    "rng_seed": 42 + nid,
                    "params": params,
                    "peers": peers,
                    "script": scripts[nid],
                    "agent_loss": 0.0,
                    "agent_delay": 0.0,
                }
            )
        )
    return cfgs


def test_neighbour_udp_basic_mesh_delivers():
    cfgs = _build_configs()
    agents = [NeighbourUdpAgent(c) for c in cfgs]
    threads = [
        threading.Thread(target=a.run, kwargs={"until": 3.0}, daemon=True) for a in agents
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    try:
        delivered = sorted(
            a.cfg.node_id
            for a in agents
            if any(i.body == "ODMRP works" for i in a.node.get_state().inbox)
        )
        fg = sorted(
            a.cfg.node_id
            for a in agents
            if "demo" in a.node.get_state().forwarding_groups
        )
        assert delivered == [3, 5], f"delivered={delivered}"
        # Wall-clock UDP can form either diamond path (or both); require a
        # non-empty FG among intermediates, not the exact discrete-event set.
        assert fg and set(fg).issubset({1, 2, 3, 4}), f"fg={fg}"
    finally:
        for a in agents:
            a.close()
