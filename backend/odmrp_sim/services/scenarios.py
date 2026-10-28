"""Load YAML scenario fixtures into a SimulationEngine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.super_node import SuperNodePush
from odmrp_sim.services.address_book_svc import apply_super_node_push, load_address_book
from odmrp_sim.services.data_plan_svc import load_data_plan, resolve_endpoints
from odmrp_sim.services.mobility import arm_waypoint_mobility
from odmrp_sim.sim.engine import NodeImplName, SimulationEngine

REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_command(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw.split()
    return [str(x) for x in raw]


def _resolve_log(raw: Any, node_id: int) -> Path | None:
    if raw is None:
        return None
    path = Path(str(raw))
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


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
        nid = int(n["id"])
        impl_raw = n.get("impl")
        impl: NodeImplName | None = str(impl_raw) if impl_raw else None  # type: ignore[assignment]
        command = _resolve_command(n.get("command"))
        log = _resolve_log(n.get("log"), nid)
        engine.add_node(
            float(n["x"]),
            float(n["y"]),
            n.get("range"),
            node_id=nid,
            impl=impl,
            command=command,
            log=log,
        )

    # Overlay: address book + optional super-node push / data plan (before script)
    overlay = data.get("overlay") or {}
    if overlay:
        _apply_overlay(engine, overlay)

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
        elif op == "move":
            engine.move_node(int(step["node"]), float(step["x"]), float(step["y"]))
        elif op == "file":
            # Reserved for future file-transfer demos; ignore safely for now.
            continue
        else:
            raise ValueError(f"unknown script op: {op}")

    mobility = data.get("mobility")
    if mobility:
        arm_waypoint_mobility(engine, mobility)

    engine.bus.emit(engine.scheduler.now, -1, "sim", op="load", seed=seed, scenario=engine.scenario)
    return data


def _apply_overlay(engine: SimulationEngine, overlay: dict[str, Any]) -> None:
    mode = str(overlay.get("mode", "hybrid"))
    book_path = overlay.get("address_book")
    if book_path:
        book = load_address_book(book_path)
        engine.bind_address_book(book, mode=mode)  # type: ignore[arg-type]
    push_path = overlay.get("super_node_push")
    if push_path and engine.address_book is not None:
        import json

        path = Path(push_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        raw = json.loads(path.read_text(encoding="utf-8"))
        push = SuperNodePush.from_dict(raw)
        summary = apply_super_node_push(engine.address_book, push, now=engine.scheduler.now)
        engine.super_node_policy = push.policy
        engine._rebind_neighbors()
        engine.bus.emit(
            engine.scheduler.now,
            push.from_node,
            "overlay",
            op="super_node_push",
            **summary,
        )
    plan_path = overlay.get("data_plan")
    if plan_path:
        plan = load_data_plan(plan_path)
        if engine.address_book is not None:
            plan = resolve_endpoints(plan, engine.address_book)
        engine.bind_data_plan(plan)


def list_scenarios(scenarios_dir: Path | str) -> list[dict[str, Any]]:
    """Return metadata for each YAML scenario in the directory."""
    root = Path(scenarios_dir)
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except Exception:
            data = {}
        nodes = data.get("nodes") or []
        out.append(
            {
                "name": data.get("name", path.stem),
                "file": path.name,
                "nodes": len(nodes),
                "description": data.get("description", ""),
                "has_mobility": bool(data.get("mobility")),
                "has_overlay": bool(data.get("overlay")),
                "native_nodes": sum(
                    1 for n in nodes if str(n.get("impl", "python")) in ("native", "external", "java")
                ),
            }
        )
    return out
