"""FastAPI application — REST + WebSocket for the ODMRP simulator."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from odmrp_sim.api.schemas import (
    GroupJoin,
    MessageSend,
    NetworkCreate,
    NodeSpec,
    ParamsBody,
    PositionUpdate,
    SpeedBody,
    StepBody,
)
from odmrp_sim.api.session import SCENARIOS, session
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.services.scenarios import list_scenarios, load_scenario
from odmrp_sim.sim.engine import SimMode

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await session.pause()


app = FastAPI(title="ODMRP Simulator", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _problem(status: int, title: str, detail: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
        media_type="application/problem+json",
    )


def _host_dict(host) -> dict[str, Any]:
    data = host.get_state().to_dict()
    data["impl"] = host.impl_name
    if host.log_path is not None:
        data["log"] = str(host.log_path)
    return data


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, Any]:
    snap = session.engine.snapshot()["sim"]
    return {"version": VERSION, **snap}


@app.post("/api/network")
async def create_network(body: NetworkCreate) -> dict[str, Any]:
    await session.pause()
    params = ProtocolParams.from_dict(body.params)
    session.engine.reset(seed=body.seed, params=params)
    session.engine.topology.default_range = body.range
    session.messaging = __import__(
        "odmrp_sim.services.messaging", fromlist=["MessagingService"]
    ).MessagingService(session.engine)
    for n in body.nodes:
        session.engine.add_node(n.x, n.y, n.range, node_id=n.id)
    session.engine.bus.emit(0.0, -1, "sim", op="load", seed=body.seed, scenario=None)
    return session.engine.snapshot()


@app.get("/api/scenarios")
def get_scenarios() -> dict[str, Any]:
    return {"scenarios": list_scenarios(SCENARIOS)}


@app.post("/api/network/scenario")
async def load_network_scenario(name: str = "basic-mesh") -> dict[str, Any]:
    await session.pause()
    path = SCENARIOS / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(404, f"scenario not found: {name}")
    async with session._lock:
        load_scenario(session.engine, path, session.messaging)
        session.engine.run_until(session.engine.scheduler.now + 0.5)
    return session.engine.snapshot()


@app.get("/api/network")
def get_network() -> dict[str, Any]:
    return session.engine.snapshot()


@app.post("/api/nodes")
def add_node(body: NodeSpec) -> dict[str, int]:
    nid = session.engine.add_node(body.x, body.y, body.range, node_id=body.id)
    return {"id": nid}


@app.delete("/api/nodes/{node_id}")
def remove_node(node_id: int) -> dict[str, str]:
    if node_id not in session.engine.hosts:
        raise HTTPException(404, "node not found")
    session.engine.remove_node(node_id)
    return {"status": "ok"}


@app.put("/api/nodes/{node_id}/position")
def move_node(node_id: int, body: PositionUpdate) -> dict[str, str]:
    if node_id not in session.engine.hosts:
        raise HTTPException(404, "node not found")
    session.engine.move_node(node_id, body.x, body.y)
    return {"status": "ok"}


@app.get("/api/nodes/{node_id}")
def get_node(node_id: int) -> dict[str, Any]:
    host = session.engine.hosts.get(node_id)
    if host is None:
        raise HTTPException(404, "node not found")
    return _host_dict(host)


@app.get("/api/nodes/{node_id}/log")
def get_node_log(node_id: int, tail: int = 80) -> dict[str, Any]:
    """Return the monitor log for a native/external process node."""
    host = session.engine.hosts.get(node_id)
    if host is None:
        raise HTTPException(404, "node not found")
    if host.log_path is None:
        raise HTTPException(404, "node has no log file")
    path = Path(host.log_path)
    if not path.is_file():
        return {
            "node": node_id,
            "path": str(path),
            "impl": host.impl_name,
            "lines": [],
            "exists": False,
        }
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(500, f"cannot read log: {exc}") from exc
    lines = text.splitlines()
    n = max(1, min(int(tail), 2000))
    return {
        "node": node_id,
        "path": str(path),
        "impl": host.impl_name,
        "lines": lines[-n:],
        "exists": True,
        "total_lines": len(lines),
    }


@app.post("/api/nodes/{node_id}/groups")
def join_group(node_id: int, body: GroupJoin) -> dict[str, str]:
    if node_id not in session.engine.hosts:
        raise HTTPException(404, "node not found")
    session.engine.join(node_id, body.group)
    return {"status": "ok"}


@app.delete("/api/nodes/{node_id}/groups/{group}")
def leave_group(node_id: int, group: str) -> dict[str, str]:
    if node_id not in session.engine.hosts:
        raise HTTPException(404, "node not found")
    session.engine.leave(node_id, group)
    return {"status": "ok"}


@app.post("/api/messages")
def send_message(body: MessageSend) -> dict[str, str]:
    if body.source not in session.engine.hosts:
        raise HTTPException(404, "source not found")
    mid = session.messaging.send_text(body.source, body.group, body.text)
    # Settle a bit so JR returns for interactive use
    session.engine.run_until(session.engine.scheduler.now + 0.2)
    return {"message_id": mid}


@app.post("/api/files")
async def send_file(
    source: int = Form(...),
    group: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if source not in session.engine.hosts:
        raise HTTPException(404, "source not found")
    data = await file.read()
    if len(data) > 1_048_576:
        raise HTTPException(413, "file too large (max 1 MiB)")
    result = session.messaging.send_file(source, group, file.filename or "file.bin", data)
    session.engine.run_until(session.engine.scheduler.now + 0.5)
    return result


@app.get("/api/messages/{message_id}/report")
def message_report(message_id: str) -> dict[str, Any]:
    return session.messaging.delivery_report(message_id)


@app.get("/api/params")
def get_params() -> dict[str, Any]:
    return session.engine.params.to_dict()


@app.put("/api/params")
async def put_params(body: ParamsBody) -> dict[str, Any]:
    await session.pause()
    session.set_params(ProtocolParams.from_dict(body.params))
    return session.engine.params.to_dict()


@app.post("/api/sim/run")
async def sim_run() -> dict[str, str]:
    await session.run()
    return {"status": "running"}


@app.post("/api/sim/pause")
async def sim_pause() -> dict[str, str]:
    await session.pause()
    return {"status": "paused"}


@app.post("/api/sim/reset")
async def sim_reset() -> dict[str, Any]:
    await session.reset()
    return session.engine.snapshot()


@app.post("/api/sim/step")
async def sim_step(body: StepBody) -> dict[str, Any]:
    if session.engine.mode == SimMode.RUNNING:
        return _problem(409, "Conflict", "step only allowed while paused")
    return await session.step(body.dt)


@app.put("/api/sim/speed")
def sim_speed(body: SpeedBody) -> dict[str, float]:
    session.engine.speed = body.multiplier
    return {"multiplier": session.engine.speed}


@app.get("/api/trace")
def get_trace(after_seq: int = 0, kinds: str | None = None, node: int | None = None, limit: int = 1000):
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    return {"events": session.engine.bus.after(after_seq, kinds=kind_list, node=node, limit=limit)}


@app.get("/api/trace/download")
def download_trace() -> Response:
    lines = [json.dumps(e, separators=(",", ":")) for e in session.engine.bus.all_dicts()]
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, after_seq: int = 0):
    await ws.accept()
    session.ws_clients.add(ws)
    last = after_seq
    try:
        snap = session.engine.snapshot()
        await ws.send_json({"type": "snapshot", **snap})
        # Replay ring after after_seq
        replay = session.engine.bus.after(after_seq, limit=5000)
        if replay:
            await ws.send_json({"type": "events", "events": replay})
            last = replay[-1]["seq"]
        while True:
            await asyncio.sleep(0.05)
            events = session.engine.bus.after(last, limit=500)
            if events:
                await ws.send_json({"type": "events", "events": events})
                last = events[-1]["seq"]
                # Push node state for any state.* events
                touched = {e["node"] for e in events if e["kind"].startswith("state.") and e["node"] >= 0}
                for nid in touched:
                    host = session.engine.hosts.get(nid)
                    if host:
                        await ws.send_json({"type": "node", "id": nid, "state": _host_dict(host)})
                if any(e["kind"] == "sim" for e in events):
                    await ws.send_json({"type": "sim", "sim": session.engine.snapshot()["sim"]})
                # Push topology after moves so the UI animates without an extra REST round-trip
                if any(e["kind"] == "topology" for e in events):
                    snap = session.engine.snapshot()
                    await ws.send_json(
                        {
                            "type": "topology",
                            "topology": snap["topology"],
                            "nodes": snap["nodes"],
                            "sim": snap["sim"],
                        }
                    )
            # Detect client disconnect via receive with timeout
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=0.001)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        session.ws_clients.discard(ws)


def main() -> None:
    import uvicorn

    uvicorn.run("odmrp_sim.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
