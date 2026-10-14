#!/usr/bin/env python3
"""Generate GNS3 scale lab adjacency + project skeleton + appliance stubs.

Usage:
  python3 scripts/gen_gns3_scale.py --n 8 --seed 42
  python3 scripts/gen_gns3_scale.py --all
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GNS3 = ROOT / "gns3"


def layout_8() -> dict[int, tuple[float, float]]:
    # Two diamonds sharing a source corridor
    return {
        0: (0, 0),
        1: (100, 60),
        2: (100, -60),
        3: (200, 60),
        4: (200, -60),
        5: (300, 0),
        6: (400, 40),
        7: (400, -40),
    }


def layout_16() -> dict[int, tuple[float, float]]:
    pos = {}
    i = 0
    for y in range(4):
        for x in range(4):
            pos[i] = (x * 120.0, y * 120.0)
            i += 1
    return pos


def layout_32() -> dict[int, tuple[float, float]]:
    # 4 clusters of 7 + 4 gateways
    pos: dict[int, tuple[float, float]] = {}
    nid = 0
    centers = [(0, 0), (400, 0), (0, 400), (400, 400)]
    for cx, cy in centers:
        for k in range(7):
            ang = 2 * math.pi * k / 7
            pos[nid] = (cx + 80 * math.cos(ang), cy + 80 * math.sin(ang))
            nid += 1
    for i, (cx, cy) in enumerate(centers):
        pos[nid] = (cx + 140, cy + 140)
        nid += 1
    return pos


def layout_64() -> dict[int, tuple[float, float]]:
    rings = [8, 16, 24, 16]
    pos: dict[int, tuple[float, float]] = {}
    nid = 0
    for ri, count in enumerate(rings):
        radius = 80 + ri * 90
        for k in range(count):
            ang = 2 * math.pi * k / count
            pos[nid] = (radius * math.cos(ang), radius * math.sin(ang))
            nid += 1
    return pos


def layout_128(seed: int) -> dict[int, tuple[float, float]]:
    rng = random.Random(seed)
    pos = {}
    for i in range(128):
        pos[i] = (rng.uniform(0, 1200), rng.uniform(0, 1200))
    return pos


def unit_disk(pos: dict[int, tuple[float, float]], range_: float) -> dict[int, list[int]]:
    neigh: dict[int, list[int]] = {i: [] for i in pos}
    ids = list(pos)
    for i, a in enumerate(ids):
        ax, ay = pos[a]
        for b in ids[i + 1 :]:
            bx, by = pos[b]
            if math.hypot(ax - bx, ay - by) <= range_:
                neigh[a].append(b)
                neigh[b].append(a)
    return {k: sorted(v) for k, v in neigh.items()}


LAYOUTS = {
    8: ("diamonds", layout_8, 130.0),
    16: ("grid4x4", layout_16, 130.0),
    32: ("clusters", layout_32, 150.0),
    64: ("rings", layout_64, 140.0),
    128: ("unitdisk", None, 160.0),
}


def write_appliance(name: str, image: str, impl: str) -> None:
    path = GNS3 / "appliances" / f"{name}.gns3a"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": name,
        "category": "guest",
        "description": f"ODMRP neighbour-UDP agent ({impl}) — local Docker image",
        "vendor_name": "odmrp-python-prototype",
        "vendor_url": "https://github.com/mowgli42/odmrp-python-prototype",
        "product_name": name,
        "registry_version": 3,
        "status": "experimental",
        "maintainer": "mowgli42",
        "usage": "Import after `docker build` of odmrp/node-*:local. Agent impairment off; set delay on GNS3 links.",
        "docker": {
            "adapters": 1,
            "image": image,
            "console_type": "telnet",
            "extra_hosts": [],
            "environment": [f"ODMRP_IMPL={impl}", "ODMRP_UNTIL=3600"],
        },
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


def generate(n: int, seed: int) -> Path:
    kind, layout_fn, range_ = LAYOUTS[n]
    if n == 128:
        pos = layout_128(seed)
    else:
        pos = layout_fn()  # type: ignore[operator]
    neigh = unit_disk(pos, range_)
    out = GNS3 / "projects" / f"scale-{n:02d}"
    out.mkdir(parents=True, exist_ok=True)
    adjacency = {
        "name": f"scale-{n:02d}",
        "layout": kind,
        "seed": seed,
        "range": range_,
        "dataplane": "neighbour_udp",
        "peers": "static",
        "params": {"jq_jitter": 0.0, "hop_delay": 0.0, "jr_delay": 0.0},
        "link_presets": {
            "baseline_ms": 0,
            "wan_ms": "5-20",
            "optional_loss": "1%",
            "note": "Apply in GNS3 link settings; agents keep impairment off.",
        },
        "expect": {
            "fg_size_band": [max(1, n // 8), max(2, n // 2)],
            "delivery_ratio_min": 0.9,
        },
        "nodes": [
            {
                "id": i,
                "x": pos[i][0],
                "y": pos[i][1],
                "impl": ["python", "java"][i % 2],
                "peers": neigh[i],
            }
            for i in sorted(pos)
        ],
    }
    (out / "adjacency.yaml").write_text(yaml.safe_dump(adjacency, sort_keys=False))
    # Minimal GNS3 project skeleton (importable after appliances registered)
    project = {
        "name": f"odmrp-scale-{n:02d}",
        "type": "topology",
        "revision": 9,
        "version": "2.2.0",
        "zoom": 100,
        "scene_width": 2000,
        "scene_height": 2000,
        "nodes": [
            {
                "node_id": str(i),
                "name": f"n{i}",
                "x": int(pos[i][0]),
                "y": int(pos[i][1]),
                "symbol": ":/symbols/docker_guest.svg",
                "node_type": "docker",
                "properties": {
                    "image": "odmrp/node-python:local" if i % 2 == 0 else "odmrp/node-java:local"
                },
            }
            for i in sorted(pos)
        ],
        "links": [],
    }
    # Add undirected links from adjacency
    seen = set()
    for a, peers in neigh.items():
        for b in peers:
            edge = tuple(sorted((a, b)))
            if edge in seen:
                continue
            seen.add(edge)
            project["links"].append(
                {
                    "nodes": [
                        {"node_id": str(edge[0]), "adapter_number": 0, "port_number": 0},
                        {"node_id": str(edge[1]), "adapter_number": 0, "port_number": 0},
                    ]
                }
            )
    (out / "project.gns3").write_text(json.dumps(project, indent=2) + "\n")
    (out / "README.md").write_text(
        f"# ODMRP scale-{n:02d} ({kind})\n\n"
        f"- Nodes: {n}, range={range_}, seed={seed}\n"
        f"- Dataplane: neighbour UDP, static peers (`adjacency.yaml`)\n"
        f"- Agent impairment: off — set delay/loss on GNS3 links\n"
        f"- Mixed images: even=python, odd=java\n\n"
        f"Import appliances from `gns3/appliances/`, then open `project.gns3`.\n"
    )
    print(f"wrote {out} links={len(project['links'])}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, choices=sorted(LAYOUTS), help="node count")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--all", action="store_true")
    p.add_argument("--appliances", action="store_true", help="also write .gns3a files")
    args = p.parse_args()
    if args.appliances or args.all:
        write_appliance("odmrp-node-python", "odmrp/node-python:local", "python")
        write_appliance("odmrp-node-java", "odmrp/node-java:local", "java")
        write_appliance("odmrp-node-rust-stub", "odmrp/node-rust:local", "fake")
        write_appliance("odmrp-node-cpp-stub", "odmrp/node-cpp:local", "fake")
    if args.all:
        for n in LAYOUTS:
            generate(n, args.seed)
    elif args.n:
        generate(args.n, args.seed)
    else:
        p.error("provide --n or --all")


if __name__ == "__main__":
    main()
