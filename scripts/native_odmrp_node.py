#!/usr/bin/env python3
"""NDJSON stdio ODMRP node for `impl: native` scenario entries.

Wraps the in-process Python reference so native nodes are always available
without a separate language toolchain. Logs every request/reply line to stderr
(and to ODMRP_NATIVE_LOG when set) for file monitoring.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

# Allow running from repo root or scripts/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from odmrp_sim.model.params import ProtocolParams  # noqa: E402
from odmrp_sim.protocol.python_node import PythonODMRPNode  # noqa: E402
from odmrp_sim.protocol.wire import packet_from_wire, packet_to_wire  # noqa: E402


def _log_path() -> Path | None:
    raw = os.environ.get("ODMRP_NATIVE_LOG")
    return Path(raw) if raw else None


def _tee(line: str, logf) -> None:
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
    if logf is not None:
        logf.write(line + "\n")
        logf.flush()


def main() -> int:
    node = PythonODMRPNode()
    log_path = _log_path()
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logf = log_path.open("a", encoding="utf-8")
    else:
        logf = None

    try:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            _tee(f"← {line}", logf)
            req = json.loads(line)
            req_id = req.get("id")
            op = req.get("op")
            try:
                resp: dict = {"id": req_id, "ok": True}
                if op == "configure":
                    params = ProtocolParams.from_dict(req.get("params") or {})
                    node.configure(int(req["node_id"]), params, int(req.get("rng_seed", 0)))
                elif op == "set_membership":
                    pkts = node.set_membership(str(req["group"]), bool(req["member"]), float(req["now"]))
                    resp["packets"] = [packet_to_wire(p) for p in pkts]
                elif op == "originate":
                    payload = base64.b64decode(req.get("payload_b64") or "")
                    pkts = node.originate(str(req["group"]), payload, float(req["now"]))
                    resp["packets"] = [packet_to_wire(p) for p in pkts]
                elif op == "receive":
                    pkt = packet_from_wire(req["packet"])
                    prev = int(req.get("previous_hop", req.get("prev_hop", -1)))
                    pkts = node.receive(pkt, prev, float(req["now"]))
                    resp["packets"] = [packet_to_wire(p) for p in pkts]
                elif op == "advance":
                    pkts = node.advance(float(req["now"]))
                    resp["packets"] = [packet_to_wire(p) for p in pkts]
                elif op == "next_timer":
                    resp["at"] = node.next_timer()
                elif op == "get_state":
                    resp["state"] = node.get_state().to_dict()
                elif op == "shutdown":
                    out = json.dumps(resp, separators=(",", ":"))
                    _tee(f"→ {out}", logf)
                    print(out, flush=True)
                    return 0
                else:
                    resp = {"id": req_id, "ok": False, "error": f"unknown op: {op}"}
            except Exception as exc:  # noqa: BLE001 — surface to host
                resp = {"id": req_id, "ok": False, "error": str(exc)}

            out = json.dumps(resp, separators=(",", ":"))
            _tee(f"→ {out}", logf)
            print(out, flush=True)
    finally:
        if logf is not None:
            logf.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
