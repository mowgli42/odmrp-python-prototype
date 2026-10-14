"""Text and file messaging over ODMRP."""

from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from odmrp_sim.model.app_payload import AppPayload
from odmrp_sim.model.packets import GroupId, NodeId

if TYPE_CHECKING:
    from odmrp_sim.sim.engine import SimulationEngine


@dataclass
class TransferState:
    transfer_id: str
    name: str
    sha256: str
    total: int
    source: NodeId
    group: GroupId
    chunks: dict[int, bytes] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return len(self.chunks) == self.total

    def missing(self) -> list[int]:
        return [i for i in range(self.total) if i not in self.chunks]

    def assemble(self) -> bytes:
        return b"".join(self.chunks[i] for i in range(self.total))


class MessagingService:
    def __init__(self, engine: SimulationEngine) -> None:
        self.engine = engine
        # node -> transfer_id -> TransferState
        self.transfers: dict[NodeId, dict[str, TransferState]] = {}
        self.messages: dict[str, dict] = {}

    def send_text(self, source: NodeId, group: GroupId, text: str) -> str:
        message_id = str(uuid.uuid4())
        payload = AppPayload(kind="text", message_id=message_id, body=text).encode()
        self.messages[message_id] = {
            "message_id": message_id,
            "source": source,
            "group": group,
            "text": text,
            "t": self.engine.scheduler.now,
        }
        self.engine.originate(source, group, payload)
        return message_id

    def send_file(self, source: NodeId, group: GroupId, name: str, data: bytes) -> dict:
        transfer_id = str(uuid.uuid4())
        chunk_size = self.engine.params.chunk_size
        total = max(1, math.ceil(len(data) / chunk_size))
        digest = hashlib.sha256(data).hexdigest()
        for i in range(total):
            chunk = data[i * chunk_size : (i + 1) * chunk_size]
            message_id = f"{transfer_id}:{i}"
            payload = AppPayload(
                kind="chunk",
                message_id=message_id,
                transfer_id=transfer_id,
                index=i,
                total=total,
                name=name,
                sha256=digest if i == 0 else None,
                data=chunk,
            ).encode()
            self.engine.originate(source, group, payload)
        return {"transfer_id": transfer_id, "total": total, "sha256": digest, "name": name}

    def ingest_inbox(self) -> None:
        """Scan node inboxes for chunks and assemble transfers."""
        for nid, host in self.engine.hosts.items():
            st = host.get_state()
            bucket = self.transfers.setdefault(nid, {})
            for item in st.inbox:
                if item.app_kind != "chunk" or not item.transfer_id:
                    continue
                # Need raw chunk bytes — re-decode from... we only stored metadata in inbox.
                # For prototype, transfers are tracked via deliver events; reassembly uses a side channel.
                # See TransferAssembler hooked from API layer.
                _ = bucket

    def delivery_report(self, message_id: str) -> dict:
        delivered: list[int] = []
        for ev in self.engine.bus.ring:
            if ev.kind == "deliver" and ev.payload.get("message_id") == message_id:
                delivered.append(ev.node)
        # Paths: reconstruct from tx/rx of the originating seq — simplified
        meta = self.messages.get(message_id, {})
        return {
            "message_id": message_id,
            "source": meta.get("source"),
            "group": meta.get("group"),
            "delivered_to": sorted(set(delivered)),
            "paths": [],  # filled by delivery_report service when needed
        }
