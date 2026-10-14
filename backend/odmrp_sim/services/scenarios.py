"""Load YAML scenario fixtures into a SimulationEngine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.sim.engine import SimulationEngine


def load_scenario(engine: SimulationEngine, path: Path | str, messaging=None) -> dict[str, Any]:
    path = Path(path)
    data = yaml.safe_load(path.read_text())
    seed = int(data.get("seed", 42))
    params = ProtocolParams.from_dict(data.get("params"))
    engine.reset(seed=seed, params=params)
    engine.topology.default_range = float(data.get("range", 130))
    engine.scenario = data.get("name", path.stem)
    engine.medium.params = engine.params

    for n in data.get("nodes", []):
        engine.add_node(float(n["x"]), float(n["y"]), n.get("range"), node_id=int(n["id"]))

    # Schedule script ops by advancing time between them
    script = sorted(data.get("script", []), key=lambda s: float(s.get("at", 0)))
    last_t = 0.0
    for step in script:
        at = float(step.get("at", 0))
        if at > last_t:
            engine.run_until(at)
            last_t = at
        op = step["op"]
        if op == "join":
            engine.join(int(step["node"]), str(step["group"]))
        elif op == "leave":
            engine.leave(int(step["node"]), str(step["group"]))
        elif op == "text":
            if messaging is None:
                from odmrp_sim.model.app_payload import AppPayload
                import uuid

                mid = str(uuid.uuid4())
                payload = AppPayload(kind="text", message_id=mid, body=str(step["text"])).encode()
                engine.originate(int(step["node"]), str(step["group"]), payload)
            else:
                messaging.send_text(int(step["node"]), str(step["group"]), str(step["text"]))
        else:
            raise ValueError(f"unknown script op: {op}")

    engine.bus.emit(engine.scheduler.now, -1, "sim", op="load", seed=seed, scenario=engine.scenario)
    return data
