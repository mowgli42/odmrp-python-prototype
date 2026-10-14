#!/usr/bin/env python3
"""Emit neighbour-UDP agent configs for scenarios/basic-mesh.yaml."""

from __future__ import annotations

import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "basic-mesh.yaml"
OUT = ROOT / "docker" / "compose" / "basic-mesh-mixed" / "configs"

# Mixed assignment matching java-reference mixed test
IMPL = {0: "python", 1: "java", 2: "python", 3: "java", 4: "python", 5: "java"}
HOST = {i: f"10.32.0.{10 + i}" for i in range(6)}


def neighbors(nodes: dict[int, tuple[float, float]], range_: float) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for a, (x, y) in nodes.items():
        nbs = []
        for b, (u, v) in nodes.items():
            if a == b:
                continue
            if math.hypot(x - u, y - v) <= range_ + 1e-9:
                nbs.append(b)
        out[a] = sorted(nbs)
    return out


def main() -> None:
    data = yaml.safe_load(SCENARIO.read_text())
    range_ = float(data.get("range", 130))
    params = dict(data.get("params") or {})
    # GNS3 / compose agents: lab owns impairment; force agent-side delay/jitter off
    params["jq_jitter"] = 0.0
    params["hop_delay"] = 0.0
    params.setdefault("jr_delay", 0.0)
    nodes = {int(n["id"]): (float(n["x"]), float(n["y"])) for n in data["nodes"]}
    neigh = neighbors(nodes, range_)
    script_by_node: dict[int, list] = {i: [] for i in nodes}
    for step in data.get("script") or []:
        nid = int(step["node"])
        op = dict(step)
        op.pop("node", None)
        # Joins must run immediately on the local clock so membership is set
        # before a source's delayed text arrives (container start skew).
        if op.get("op") == "join":
            op["at"] = 0.0
        else:
            op["at"] = float(op.get("at", 0)) + 3.0
        if op.get("op") == "text":
            op["message_id"] = "basic-mesh-msg"
        script_by_node[nid].append(op)

    OUT.mkdir(parents=True, exist_ok=True)
    for nid, (x, y) in nodes.items():
        peers = {
            str(p): f"{HOST[p]}:9000" for p in neigh[nid]
        }
        cfg = {
            "node_id": nid,
            "impl": IMPL[nid],
            "listen": "0.0.0.0:9000",
            "pos": {"x": x, "y": y},
            "range": range_,
            "rng_seed": int(data.get("seed", 42)) + nid * 1009,
            "params": params,
            "peers": peers,
            "script": script_by_node[nid],
            "trace": f"/traces/node-{nid}.jsonl",
            "agent_loss": 0.0,
            "agent_delay": 0.0,
            "dataplane": "neighbour_udp",
        }
        if IMPL[nid] == "java":
            cfg["java_jar"] = "/opt/odmrp/odmrp-java-node.jar"
        (OUT / f"node-{nid}.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
        print(f"wrote node-{nid}.yaml peers={list(peers)}")


if __name__ == "__main__":
    main()
