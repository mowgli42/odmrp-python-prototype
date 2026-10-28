"""Thin JREAP-A / mock SA endpoint behind ProductLocation URI.

Swappable: ``MockSaSource`` for deterministic tests; ``TcpJreapEndpoint`` for a
real TCP listener that emits the same mock framing. A later real JREAP-A
source can implement ``SaByteSource`` without touching the feed relay.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol


PRODUCT_TYPE_JREAP = "Link16-JREAP-A"


class SaByteSource(Protocol):
    """Byte source for one SA/JREAP product feed."""

    @property
    def uri(self) -> str: ...

    def read(self, max_bytes: int = 256) -> bytes: ...

    def close(self) -> None: ...


def mock_jreap_frame(seq: int, *, track_id: int = 1) -> bytes:
    """Minimal mock JREAP-A-ish frame: magic + seq + track + payload."""
    payload = f"SA track={track_id} seq={seq}".encode("ascii")
    # !4s I H H + payload  — easy to parse / swap for real framing later
    header = struct.pack("!4sIHH", b"JREA", seq & 0xFFFFFFFF, track_id & 0xFFFF, len(payload))
    return header + payload


@dataclass
class MockSaSource:
    """In-process deterministic SA stream (no sockets)."""

    product_type: str = PRODUCT_TYPE_JREAP
    host: str = "127.0.0.1"
    port: int = 0  # 0 = in-process only
    _seq: int = 0
    _closed: bool = False
    frames_emitted: int = 0

    @property
    def uri(self) -> str:
        if self.port:
            return f"tcp://{self.host}:{self.port}/{self.product_type}"
        return f"mock://{self.product_type}"

    def read(self, max_bytes: int = 256) -> bytes:
        if self._closed:
            return b""
        self._seq += 1
        frame = mock_jreap_frame(self._seq)
        self.frames_emitted += 1
        return frame[:max_bytes] if max_bytes < len(frame) else frame

    def close(self) -> None:
        self._closed = True


@dataclass
class TcpJreapEndpoint:
    """Thin TCP listener that writes mock SA frames to each client.

    Gateway opens one client connection; relays must not open another.
    """

    product_type: str = PRODUCT_TYPE_JREAP
    host: str = "127.0.0.1"
    port: int = 0  # 0 → ephemeral
    interval_s: float = 0.05
    _sock: socket.socket | None = field(default=None, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    clients: int = 0

    @property
    def uri(self) -> str:
        return f"tcp://{self.host}:{self.port}/{self.product_type}"

    def start(self) -> str:
        if self._sock is not None:
            return self.uri
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        srv.settimeout(0.5)
        self.host, self.port = srv.getsockname()[:2]
        self._sock = srv
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="jreap-endpoint", daemon=True)
        self._thread.start()
        return self.uri

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.clients += 1
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn: socket.socket) -> None:
        seq = 0
        try:
            conn.settimeout(1.0)
            while not self._stop.is_set():
                seq += 1
                frame = mock_jreap_frame(seq)
                try:
                    conn.sendall(frame)
                except OSError:
                    break
                time.sleep(self.interval_s)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


@dataclass
class TcpSaClient:
    """Client side of the thin endpoint — only the gateway should use this."""

    uri: str
    _sock: socket.socket | None = field(default=None, init=False, repr=False)
    _buf: bytes = field(default=b"", init=False, repr=False)
    opened: bool = False

    def connect(self) -> None:
        # tcp://host:port/ProductType
        assert self.uri.startswith("tcp://"), self.uri
        rest = self.uri[len("tcp://") :]
        hostport, _, _prod = rest.partition("/")
        host, _, port_s = hostport.partition(":")
        sock = socket.create_connection((host, int(port_s)), timeout=2.0)
        sock.settimeout(0.2)
        self._sock = sock
        self.opened = True

    def read(self, max_bytes: int = 256) -> bytes:
        if self._sock is None:
            return b""
        try:
            chunk = self._sock.recv(max_bytes)
        except socket.timeout:
            return b""
        except OSError:
            return b""
        return chunk

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
