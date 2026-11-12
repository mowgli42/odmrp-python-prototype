"""Configurable Markov link-state model for RF adjacency."""

from __future__ import annotations

import random
from typing import Any

from odmrp_sim.model.packets import NodeId
from odmrp_sim.sim.engine import SimulationEngine
from odmrp_sim.sim.scheduler import Event

Pair = tuple[NodeId, NodeId]


def _clamp01(value: float, name: str) -> float:
    v = float(value)
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {v}")
    return v


def arm_markov_links(engine: SimulationEngine, cfg: dict[str, Any]) -> None:
    """Schedule a nested Markov connected/disconnected process on geometric pairs.

    Expected cfg keys (all optional except when type is present in the scenario):
      type: "markov" (required for this arming function)
      interval: float — seconds between re-evaluations (default 1.0)
      seed: int — RNG seed (default engine.seed + 31)
      initial: "up" | "down" | "random" — starting state for each candidate (default "up")
      pairs: [[a,b], ...] — optional explicit undirected candidates; default = all
               pairs currently within radio range (refreshed each tick)
      p_keep_up: float — when UP, probability of skipping re-eval (default 0.75)
      p_down_on_reeval: float — when UP and re-evaluating, P(go DOWN) (default 0.25)
      p_keep_down: float — when DOWN, probability of skipping re-eval (default 0.25)
      p_up_on_reeval: float — when DOWN and re-evaluating, P(go UP) (default 0.75)

    Nested semantics (matches the common demo state machine)::

        UP:   with p_keep_up stay UP;
              else re-eval → DOWN with p_down_on_reeval, else stay UP
        DOWN: with p_keep_down stay DOWN;
              else re-eval → UP with p_up_on_reeval, else stay DOWN

    Only pairs that are geometrically in range can be UP. Leaving radio range
    drops the Markov state; returning creates a fresh pair with ``initial``.
    """
    if not cfg:
        return
    model = str(cfg.get("type", "markov")).lower()
    if model != "markov":
        raise ValueError(f"unsupported link_model type: {model}")

    interval = float(cfg.get("interval", 1.0))
    if interval <= 0:
        raise ValueError("link_model.interval must be > 0")

    p_keep_up = _clamp01(cfg.get("p_keep_up", 0.75), "p_keep_up")
    p_down_on_reeval = _clamp01(cfg.get("p_down_on_reeval", 0.25), "p_down_on_reeval")
    p_keep_down = _clamp01(cfg.get("p_keep_down", 0.25), "p_keep_down")
    p_up_on_reeval = _clamp01(cfg.get("p_up_on_reeval", 0.75), "p_up_on_reeval")
    initial = str(cfg.get("initial", "up")).lower()
    if initial not in ("up", "down", "random"):
        raise ValueError("link_model.initial must be up|down|random")

    rng = random.Random(int(cfg.get("seed", engine.seed + 31)))
    # True = connected (UP)
    state: dict[Pair, bool] = {}

    fixed_pairs: set[Pair] | None = None
    raw_pairs = cfg.get("pairs")
    if raw_pairs is not None:
        fixed_pairs = set()
        for pair in raw_pairs:
            a, b = int(pair[0]), int(pair[1])
            if a == b:
                continue
            fixed_pairs.add((a, b) if a < b else (b, a))

    def _initial_up() -> bool:
        if initial == "up":
            return True
        if initial == "down":
            return False
        return rng.random() < 0.5

    def _transition(up: bool) -> bool:
        if up:
            if rng.random() < p_keep_up:
                return True
            # re-eval while UP
            return not (rng.random() < p_down_on_reeval)
        if rng.random() < p_keep_down:
            return False
        # re-eval while DOWN
        return rng.random() < p_up_on_reeval

    def _candidates() -> list[Pair]:
        geometric = set(engine.topology.geometric_pairs())
        if fixed_pairs is None:
            return sorted(geometric)
        # Explicit pairs that are currently in radio range
        return sorted(fixed_pairs & geometric)

    def _apply(pair: Pair, want_up: bool) -> None:
        a, b = pair
        if want_up:
            engine.topology.enable_link(a, b)
        else:
            engine.topology.disable_link(a, b)

    def _sync_new_and_gone(cands: list[Pair]) -> None:
        alive = set(cands)
        for pair in list(state):
            if pair not in alive:
                # Out of range (or removed): clear mask bookkeeping; geometry already down.
                state.pop(pair, None)
                engine.topology.enable_link(pair[0], pair[1])  # drop stale disable mask
        for pair in cands:
            if pair not in state:
                up = _initial_up()
                state[pair] = up
                _apply(pair, up)

    def _tick(_ev: Event) -> None:
        now = engine.scheduler.now
        cands = _candidates()
        _sync_new_and_gone(cands)
        flips = 0
        for pair in cands:
            before = state[pair]
            after = _transition(before)
            if after != before:
                flips += 1
            state[pair] = after
            _apply(pair, after)
        engine.bus.emit(
            now,
            -1,
            "topology",
            op="link_model_tick",
            model="markov",
            pairs=len(cands),
            up=sum(1 for v in state.values() if v),
            down=sum(1 for v in state.values() if not v),
            flips=flips,
        )
        engine.scheduler.schedule(
            now + interval,
            "link_model",
            node=-1,
            payload={"model": "markov"},
            callback=_tick,
        )

    # Prime state at arm time without advancing the clock.
    _sync_new_and_gone(_candidates())

    first = engine.scheduler.now + interval
    engine.scheduler.schedule(
        first,
        "link_model",
        node=-1,
        payload={"model": "markov"},
        callback=_tick,
    )
    engine.bus.emit(
        engine.scheduler.now,
        -1,
        "sim",
        op="link_model",
        model="markov",
        interval=interval,
        p_keep_up=p_keep_up,
        p_down_on_reeval=p_down_on_reeval,
        p_keep_down=p_keep_down,
        p_up_on_reeval=p_up_on_reeval,
        initial=initial,
        pairs=len(state),
    )
