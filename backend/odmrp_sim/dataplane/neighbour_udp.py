"""Neighbour-scoped UDP dataplane — draft-faithful flood without IP multicast.

Each agent speaks length-prefixed JSON envelopes to a static peer table
(or later Hello-learned neighbours). ODMRPNode remains the protocol brain;
this module owns sockets and wall-clock `advance`.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from odmrp_sim.model.app_payload import AppPayload
from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.model.state import Position
from odmrp_sim.protocol.external_node import ExternalProcessNode
from odmrp_sim.protocol.fake_node import FakeNode
from odmrp_sim.protocol.interface import ODMRPNode
from odmrp_sim.protocol.python_node import PythonODMRPNode
from odmrp_sim.protocol.wire import packet_from_wire, packet_to_wire

HDR = struct.Struct("!I")


@dataclass
class Peer:
    node_id: int
    host: str
    port: int


@dataclass
class AgentConfig:
    node_id: int
    impl: str = "python"
    listen_host: str = "0.0.0.0"
    listen_port: int = 9000
    peers: dict[int, Peer] = field(default_factory=dict)
    params: ProtocolParams = field(default_factory=ProtocolParams)
    rng_seed: int = 42
    pos: Position = field(default_factory=lambda: Position(0.0, 0.0))
    range: float = 130.0
    script: list[dict[str, Any]] = field(default_factory=list)
    trace_path: Path | None = None
    java_jar: str | None = None
    java_bin: str | None = None
    # Agent-side impairment (default off for GNS3 — lab owns delay/loss)
    agent_loss: float = 0.0
    agent_delay: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        peers: dict[int, Peer] = {}
        for k, v in (data.get("peers") or {}).items():
            nid = int(k)
            if isinstance(v, str):
                host, _, port_s = v.partition(":")
                peers[nid] = Peer(nid, host, int(port_s or 9000))
            else:
                peers[nid] = Peer(nid, str(v["host"]), int(v.get("port", 9000)))
        listen = data.get("listen", "0.0.0.0:9000")
        if isinstance(listen, str):
            lh, _, lp = listen.partition(":")
            listen_host, listen_port = lh or "0.0.0.0", int(lp or 9000)
        else:
            listen_host = str(listen.get("host", "0.0.0.0"))
            listen_port = int(listen.get("port", 9000))
        pos = data.get("pos") or {}
        params = ProtocolParams.from_dict(data.get("params"))
        # GNS3-bound defaults: no agent impairment unless explicitly set
        if "jq_jitter" not in (data.get("params") or {}):
            params.jq_jitter = 0.0
        if "hop_delay" not in (data.get("params") or {}):
            params.hop_delay = 0.0
        return cls(
            node_id=int(data["node_id"]),
            impl=str(data.get("impl", "python")),
            listen_host=listen_host,
            listen_port=listen_port,
            peers=peers,
            params=params,
            rng_seed=int(data.get("rng_seed", data.get("seed", 42))),
            pos=Position(float(pos.get("x", 0.0)), float(pos.get("y", 0.0))),
            range=float(data.get("range", 130.0)),
            script=list(data.get("script") or []),
            trace_path=Path(data["trace"]) if data.get("trace") else None,
            java_jar=data.get("java_jar"),
            java_bin=data.get("java_bin"),
            agent_loss=float(data.get("agent_loss", 0.0)),
            agent_delay=float(data.get("agent_delay", 0.0)),
        )


def _make_impl(cfg: AgentConfig) -> ODMRPNode:
    name = cfg.impl.lower()
    if name == "python":
        node = PythonODMRPNode()
        node.pos = cfg.pos
        node.range = cfg.range
        return node
    if name == "java":
        return ExternalProcessNode.java(jar=cfg.java_jar, java_bin=cfg.java_bin)
    if name in ("fake", "rust", "cpp", "c++"):
        # Language stubs until real ports land (issue #4)
        node = FakeNode()
        node.pos = cfg.pos
        node.range = cfg.range
        return node
    raise ValueError(f"unknown impl: {cfg.impl}")


class NeighbourUdpAgent:
    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self.node = _make_impl(cfg)
        self.node.configure(cfg.node_id, cfg.params, cfg.rng_seed)
        if isinstance(self.node, (PythonODMRPNode, ExternalProcessNode, FakeNode)):
            self.node.pos = cfg.pos
            self.node.range = cfg.range
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((cfg.listen_host, cfg.listen_port))
        self.sock.setblocking(False)
        self._t0 = time.monotonic()
        self._script_i = 0
        self._script = sorted(cfg.script, key=lambda s: float(s.get("at", 0)))
        self._trace: Any = None
        if cfg.trace_path:
            cfg.trace_path.parent.mkdir(parents=True, exist_ok=True)
            self._trace = cfg.trace_path.open("a", encoding="utf-8")

    @property
    def now(self) -> float:
        return time.monotonic() - self._t0

    def close(self) -> None:
        if self._trace:
            self._trace.close()
            self._trace = None
        self.sock.close()
        if isinstance(self.node, ExternalProcessNode):
            self.node.close()

    def _emit(self, kind: str, **payload: Any) -> None:
        if not self._trace:
            return
        rec = {"t": round(self.now, 6), "node": self.cfg.node_id, "kind": kind, **payload}
        self._trace.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self._trace.flush()

    def _send_packets(self, packets: list) -> None:
        for pkt in packets:
            if pkt.previous_hop < 0:
                pkt.previous_hop = self.cfg.node_id
            envelope = {
                "from": self.cfg.node_id,
                "packet": packet_to_wire(pkt),
            }
            raw = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
            frame = HDR.pack(len(raw)) + raw
            peers = sorted(self.cfg.peers.values(), key=lambda p: p.node_id)
            self._emit(
                "tx",
                packet=pkt.to_dict(),
                neighbors=[p.node_id for p in peers],
            )
            for peer in peers:
                if self.cfg.agent_loss > 0 and (hash((pkt.id, peer.node_id)) % 1000) / 1000.0 < self.cfg.agent_loss:
                    continue
                if self.cfg.agent_delay > 0:
                    time.sleep(self.cfg.agent_delay)
                try:
                    self.sock.sendto(frame, (peer.host, peer.port))
                except OSError as e:
                    self._emit("drop", reason=f"send:{e}", peer=peer.node_id)

    def _handle_datagram(self, data: bytes) -> None:
        if len(data) < 4:
            return
        (n,) = HDR.unpack_from(data, 0)
        if n <= 0 or 4 + n > len(data):
            # tolerate bare JSON without length prefix
            try:
                env = json.loads(data.decode("utf-8"))
            except Exception:
                return
        else:
            try:
                env = json.loads(data[4 : 4 + n].decode("utf-8"))
            except Exception:
                return
        prev = int(env.get("from", -1))
        pkt = packet_from_wire(env["packet"])
        self._emit("rx", packet_id=pkt.id, **{"from": prev, "pkind": pkt.kind.value})
        before = self.node.get_state()
        out = self.node.receive(pkt, prev, self.now)
        after = self.node.get_state()
        if len(after.inbox) > len(before.inbox):
            for item in after.inbox[len(before.inbox) :]:
                self._emit(
                    "deliver",
                    packet_id=pkt.id,
                    message_id=item.message_id,
                    group=item.group,
                    app_kind=item.app_kind,
                    body=item.body,
                )
        self._diff_state(before, after)
        self._send_packets(out)

    def _diff_state(self, before, after) -> None:
        for g, fg in after.forwarding_groups.items():
            old = before.forwarding_groups.get(g)
            if old is None:
                self._emit(
                    "state.fg",
                    group=g,
                    expires_at=fg.expires_at,
                    refreshed_by=sorted(fg.refreshed_by),
                    op="set",
                )
            elif old.expires_at != fg.expires_at:
                self._emit(
                    "state.fg",
                    group=g,
                    expires_at=fg.expires_at,
                    refreshed_by=sorted(fg.refreshed_by),
                    op="refresh",
                )
        for g in set(before.forwarding_groups) - set(after.forwarding_groups):
            self._emit("state.fg", group=g, expires_at=self.now, refreshed_by=[], op="expire")

    def _run_script(self) -> None:
        while self._script_i < len(self._script):
            step = self._script[self._script_i]
            at = float(step.get("at", 0))
            if at > self.now + 1e-9:
                break
            self._script_i += 1
            op = step["op"]
            if op == "join":
                before = self.node.get_state()
                out = self.node.set_membership(str(step["group"]), True, self.now)
                self._emit("state.member", group=step["group"], member=True)
                self._diff_state(before, self.node.get_state())
                self._send_packets(out)
            elif op == "leave":
                out = self.node.set_membership(str(step["group"]), False, self.now)
                self._emit("state.member", group=step["group"], member=False)
                self._send_packets(out)
            elif op == "text":
                import uuid

                mid = str(step.get("message_id") or uuid.uuid4())
                payload = AppPayload(
                    kind="text", message_id=mid, body=str(step["text"])
                ).encode()
                before = self.node.get_state()
                out = self.node.originate(str(step["group"]), payload, self.now)
                self._diff_state(before, self.node.get_state())
                self._send_packets(out)
            else:
                self._emit("drop", reason=f"unknown_script_op:{op}")

    def _advance_due(self) -> None:
        # Fire repeatedly so stacked timers in one wake are not skipped.
        for _ in range(32):
            nt = self.node.next_timer()
            if nt is None or nt > self.now + 1e-12:
                return
            before = self.node.get_state()
            out = self.node.advance(self.now)
            self._diff_state(before, self.node.get_state())
            self._send_packets(out)

    def run(self, until: float | None = None) -> None:
        self._emit("sim", op="agent_start", impl=self.cfg.impl)
        deadline = None if until is None else self._t0 + until
        try:
            while True:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                self._run_script()
                self._advance_due()
                timeout = 0.05
                nt = self.node.next_timer()
                if nt is not None:
                    timeout = max(0.001, min(timeout, nt - self.now))
                if self._script_i < len(self._script):
                    next_at = float(self._script[self._script_i].get("at", 0))
                    timeout = max(0.001, min(timeout, next_at - self.now))
                r, _, _ = select.select([self.sock], [], [], timeout)
                if r:
                    try:
                        data, _addr = self.sock.recvfrom(65535)
                    except BlockingIOError:
                        continue
                    self._handle_datagram(data)
        finally:
            st = self.node.get_state()
            self._emit(
                "sim",
                op="agent_stop",
                fg=sorted(st.forwarding_groups.keys()),
                members=sorted(st.members),
                inbox_len=len(st.inbox),
            )


def load_config(path: Path | str) -> AgentConfig:
    path = Path(path)
    text = path.read_text()
    if path.suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return AgentConfig.from_dict(data)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="ODMRP neighbour-UDP agent")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--until", type=float, default=None, help="wall seconds to run")
    args = p.parse_args(argv)
    # Env overrides for Docker
    cfg = load_config(args.config)
    if os.environ.get("ODMRP_IMPL"):
        cfg.impl = os.environ["ODMRP_IMPL"]
    if os.environ.get("ODMRP_NODE_ID"):
        cfg.node_id = int(os.environ["ODMRP_NODE_ID"])
    if os.environ.get("ODMRP_TRACE"):
        cfg.trace_path = Path(os.environ["ODMRP_TRACE"])
    until = args.until
    if until is None and os.environ.get("ODMRP_UNTIL"):
        until = float(os.environ["ODMRP_UNTIL"])
    agent = NeighbourUdpAgent(cfg)
    try:
        agent.run(until=until)
    finally:
        agent.close()


if __name__ == "__main__":
    main()
