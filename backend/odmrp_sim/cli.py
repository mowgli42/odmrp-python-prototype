"""Headless scenario runner — writes a JSONL trace."""

from __future__ import annotations

import argparse
from pathlib import Path

from odmrp_sim.services.messaging import MessagingService
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Run an ODMRP scenario headless")
    p.add_argument("scenario", nargs="?", default="basic-mesh")
    p.add_argument("--settle", type=float, default=0.5)
    p.add_argument("--trace", type=Path, default=Path("traces/run.jsonl"))
    args = p.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    path = root / "scenarios" / f"{args.scenario}.yaml"
    eng = SimulationEngine()
    msg = MessagingService(eng)
    eng.bus.open_file(args.trace)
    load_scenario(eng, path, msg)
    eng.run_until(eng.scheduler.now + args.settle)
    eng.bus.close_file()

    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    delivered = sorted(
        {e.node for e in eng.bus.ring if e.kind == "deliver"}
    )
    print(f"t={eng.scheduler.now:.3f} FG={fg} delivered={delivered} trace={args.trace}")


if __name__ == "__main__":
    main()
