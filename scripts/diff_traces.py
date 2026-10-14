#!/usr/bin/env python3
"""Merge per-node JSONL traces and compare FG / delivery / compact tx against a baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_dir(path: Path) -> list[dict]:
    events: list[dict] = []
    for f in sorted(path.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    events.sort(key=lambda e: (float(e.get("t", 0)), int(e.get("node", -1)), e.get("kind", "")))
    return events


def fg_nodes(events: list[dict]) -> list[int]:
    fg: set[int] = set()
    for e in events:
        if e.get("kind") != "state.fg":
            continue
        if e.get("op") == "expire":
            fg.discard(int(e["node"]))
        elif e.get("group") == "demo" or e.get("group") is not None:
            if e.get("op") in ("set", "refresh"):
                fg.add(int(e["node"]))
    # Prefer final agent_stop fg lists when present
    stopped = {
        int(e["node"]): set(e.get("fg") or [])
        for e in events
        if e.get("kind") == "sim" and e.get("op") == "agent_stop"
    }
    if stopped:
        return sorted(n for n, groups in stopped.items() if "demo" in groups or groups)
    return sorted(fg)


def delivered(events: list[dict], group: str = "demo") -> list[int]:
    return sorted(
        {
            int(e["node"])
            for e in events
            if e.get("kind") == "deliver" and e.get("group") == group
        }
    )


def compact(events: list[dict]) -> list[tuple]:
    out = []
    for e in events:
        kind = e.get("kind")
        if kind == "tx":
            pkt = e.get("packet") or {}
            out.append(
                (
                    round(float(e.get("t", 0)), 3),
                    kind,
                    int(e["node"]),
                    pkt.get("kind"),
                    pkt.get("source"),
                    pkt.get("group"),
                    tuple(e.get("neighbors") or []),
                )
            )
        elif kind == "deliver":
            out.append((round(float(e.get("t", 0)), 3), kind, int(e["node"]), e.get("group")))
        elif kind == "state.fg":
            out.append(
                (
                    round(float(e.get("t", 0)), 3),
                    kind,
                    int(e["node"]),
                    e.get("op"),
                    e.get("group"),
                )
            )
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("traces", type=Path, help="directory of node-*.jsonl")
    p.add_argument("--baseline", type=Path, help="optional baseline trace dir")
    p.add_argument("--expect-fg", type=str, default="", help="comma-separated node ids")
    p.add_argument("--expect-delivered", type=str, default="", help="comma-separated node ids")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    events = load_dir(args.traces)
    result = {
        "fg": fg_nodes(events),
        "delivered": delivered(events),
        "events": len(events),
    }
    ok = True
    if args.expect_fg:
        expect = sorted(int(x) for x in args.expect_fg.split(",") if x.strip() != "")
        result["expect_fg"] = expect
        ok = ok and result["fg"] == expect
    if args.expect_delivered:
        expect = sorted(int(x) for x in args.expect_delivered.split(",") if x.strip() != "")
        result["expect_delivered"] = expect
        ok = ok and result["delivered"] == expect
    if args.baseline:
        base = load_dir(args.baseline)
        result["baseline_fg"] = fg_nodes(base)
        result["baseline_delivered"] = delivered(base)
        # Wall-clock traces won't be bit-identical; compare sets
        ok = ok and result["fg"] == result["baseline_fg"]
        ok = ok and result["delivered"] == result["baseline_delivered"]
    result["ok"] = ok
    if args.json:
        print(json.dumps(result))
    else:
        print(f"fg={result['fg']} delivered={result['delivered']} events={result['events']} ok={ok}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
