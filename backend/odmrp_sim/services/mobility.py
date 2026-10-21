"""Lightweight waypoint mobility scheduled on the discrete-event clock."""

from __future__ import annotations

import math
import random
from typing import Any

from odmrp_sim.sim.engine import SimulationEngine
from odmrp_sim.sim.scheduler import Event


def arm_waypoint_mobility(engine: SimulationEngine, cfg: dict[str, Any]) -> None:
    """Schedule repeating random-waypoint moves for selected nodes.

    Expected cfg keys:
      nodes: list[int]          — movers (default: all nodes)
      interval: float           — seconds between move decisions (default 1.0)
      speed: float              — units/sec toward waypoint (default 25)
      bounds: [xmin,ymin,xmax,ymax]
      seed: int                 — optional RNG seed (falls back to engine.seed)
    """
    if not cfg:
        return
    nodes = [int(n) for n in cfg.get("nodes") or list(engine.hosts)]
    if not nodes:
        return
    interval = float(cfg.get("interval", 1.0))
    speed = float(cfg.get("speed", 25.0))
    bounds = cfg.get("bounds") or [0.0, 0.0, 480.0, 480.0]
    xmin, ymin, xmax, ymax = (float(v) for v in bounds)
    rng = random.Random(int(cfg.get("seed", engine.seed + 17)))
    targets: dict[int, tuple[float, float]] = {}

    def _pick(nid: int) -> tuple[float, float]:
        return (rng.uniform(xmin, xmax), rng.uniform(ymin, ymax))

    def _step(_ev: Event) -> None:
        now = engine.scheduler.now
        for nid in nodes:
            if nid not in engine.hosts:
                continue
            host = engine.hosts[nid]
            tx, ty = targets.get(nid) or _pick(nid)
            targets[nid] = (tx, ty)
            dx, dy = tx - host.pos.x, ty - host.pos.y
            dist = math.hypot(dx, dy)
            if dist < 1.0:
                targets[nid] = _pick(nid)
                continue
            step = min(speed * interval, dist)
            nx = host.pos.x + dx / dist * step
            ny = host.pos.y + dy / dist * step
            engine.move_node(nid, nx, ny)
        # Re-arm
        engine.scheduler.schedule(
            now + interval,
            "mobility",
            node=-1,
            payload={"model": "waypoint"},
            callback=_step,
        )

    first = engine.scheduler.now + interval
    engine.scheduler.schedule(
        first,
        "mobility",
        node=-1,
        payload={"model": "waypoint"},
        callback=_step,
    )
    engine.bus.emit(
        engine.scheduler.now,
        -1,
        "sim",
        op="mobility",
        model="waypoint",
        nodes=nodes,
        interval=interval,
        speed=speed,
    )
