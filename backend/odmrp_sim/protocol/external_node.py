"""ExternalProcessNode — ODMRPNode over NDJSON stdio (roadmap odmrp-dn0)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from odmrp_sim.model.packets import GroupId, NodeId, Packet
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import NodeState, Position
from odmrp_sim.protocol.wire import packet_from_wire, packet_to_wire, params_to_wire, state_from_wire

# Default jar relative to repo root (parent of backend/)
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JAVA_JAR = _REPO_ROOT / "java-node" / "dist" / "odmrp-java-node.jar"
DEFAULT_JAVA_BIN = os.environ.get("JAVA_HOME", str(Path.home() / "tools" / "jdk")) + "/bin/java"


@dataclass
class ExternalProcessNode:
    """Spawn a child process and forward ADR-005 ops as NDJSON requests."""

    command: Sequence[str]
    node_id: NodeId = -1
    params: ProtocolParams = field(default_factory=ProtocolParams)
    pos: Position = field(default_factory=lambda: Position(0.0, 0.0))
    range: float = 130.0
    _proc: subprocess.Popen[str] | None = field(default=None, repr=False)
    _next_id: int = 1
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _cached_next_timer: float | None = None

    @classmethod
    def java(
        cls,
        jar: Path | str | None = None,
        java_bin: str | None = None,
    ) -> ExternalProcessNode:
        jbin = java_bin or (
            DEFAULT_JAVA_BIN if Path(DEFAULT_JAVA_BIN).exists() else "java"
        )
        jpath = Path(jar) if jar else DEFAULT_JAVA_JAR
        if not jpath.is_file():
            raise FileNotFoundError(
                f"Java node jar not found at {jpath}. Run java-node/build.sh first."
            )
        return cls(command=[jbin, "-jar", str(jpath)])

    def _ensure(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            list(self.command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def _rpc(self, op: str, **fields) -> dict:
        with self._lock:
            self._ensure()
            assert self._proc is not None and self._proc.stdin and self._proc.stdout
            req_id = self._next_id
            self._next_id += 1
            msg = {"op": op, "id": req_id, **fields}
            self._proc.stdin.write(json.dumps(msg, separators=(",", ":")) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
            if not line:
                err = self._proc.stderr.read() if self._proc.stderr else ""
                raise RuntimeError(f"external node died on {op}: {err}")
            resp = json.loads(line)
            if resp.get("id") != req_id:
                raise RuntimeError(f"id mismatch: sent {req_id} got {resp.get('id')}")
            if not resp.get("ok", False):
                raise RuntimeError(resp.get("error", "external node error"))
            if "next_timer" in resp:
                self._cached_next_timer = resp["next_timer"]
            elif "at" in resp:
                self._cached_next_timer = resp["at"]
            return resp

    def _packets_from(self, resp: dict) -> list[Packet]:
        raw = resp.get("packets")
        if raw is None:
            raw = resp.get("tx") or []
        return [packet_from_wire(p) for p in raw]

    def configure(self, node_id: NodeId, params: ProtocolParams, rng_seed: int) -> None:
        self.node_id = node_id
        self.params = params
        self._rpc(
            "configure",
            node_id=node_id,
            params=params_to_wire(params),
            rng_seed=int(rng_seed),
        )

    def set_membership(self, group: GroupId, member: bool, now: float) -> list[Packet]:
        resp = self._rpc("set_membership", group=group, member=bool(member), now=float(now))
        return self._packets_from(resp)

    def originate(self, group: GroupId, payload: bytes, now: float) -> list[Packet]:
        import base64

        resp = self._rpc(
            "originate",
            group=group,
            payload_b64=base64.b64encode(payload).decode("ascii"),
            now=float(now),
        )
        return self._packets_from(resp)

    def receive(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]:
        resp = self._rpc(
            "receive",
            packet=packet_to_wire(packet),
            previous_hop=int(previous_hop),
            prev_hop=int(previous_hop),
            now=float(now),
        )
        return self._packets_from(resp)

    def advance(self, now: float) -> list[Packet]:
        resp = self._rpc("advance", now=float(now))
        return self._packets_from(resp)

    def next_timer(self) -> float | None:
        resp = self._rpc("next_timer")
        at = resp.get("at", resp.get("next_timer"))
        return float(at) if at is not None else None

    def get_state(self) -> NodeState:
        resp = self._rpc("get_state")
        st = state_from_wire(resp["state"])
        st.pos = self.pos
        st.range = self.range
        return st

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.poll() is None:
                self._rpc("shutdown")
        except Exception:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
