# Design

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                     Svelte Frontend                      │
│  (nodes graph, FG highlights, traffic animation, controls) │
└─────────────────────────┬─────────────────────────────┘
                           │ WebSocket + REST
┌─────────────────────────▼─────────────────────────────┐
│                  FastAPI Backend                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Simulation  │  │  Node Manager│  │  Trace / Event  │  │
│  │ Engine      │  │              │  │  Bus            │  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘  │
│         │                │                   │           │
│         └───────────────┬──────────────────┘           │
│                          │                               │
│              ┌───────────▼───────────┐                   │
│              │   Per-Node ODMRP      │                   │
│              │   State Machines      │                   │
│              │   (Python reference)  │                   │
│              └──────────────────────┘                   │
└────────────────────────────────────────────────────────────┘
```

## Key Decisions

### Single-process simulation
**Choice**: All nodes and the topology live in one Python process.
**Alternative**: Multi-process or real UDP sockets.
**Reason**: Dramatically simpler for a prototype; deterministic testing is easier; WebSocket push to frontend is trivial.
**Production bead**: Move to multi-process or container-per-node with real networking when validating distributed implementations (`odmrp-faw`, `odmrp-32m`).

### Distance-based connectivity
**Choice**: Neighbors = nodes whose Euclidean distance ≤ radio range (unit disk, symmetric).
**Alternative**: Explicit link list or unit disk graph with obstacles.
**Reason**: Intuitive for visualization and matches classic MANET papers.
**Production bead**: Add probabilistic loss, asymmetric links, and mobility models.

### Soft-state timers with simulation clock
**Choice**: All timers (ROUTE_REFRESH_INTERVAL, FG_TIMEOUT, etc.) are driven by the simulation clock, not wall-clock.
**Reason**: Enables deterministic, fast tests and step-through debugging.
**Default values** (prototype, see `ProtocolParams`):
- ROUTE_REFRESH_INTERVAL = 3.0 s
- FG_TIMEOUT = 9.0 s
- ROUTE_TIMEOUT = 9.0 s
- SOURCE_IDLE_TIMEOUT = 3.0 s
- JOIN_QUERY_TTL = 32
- jq_jitter = 0.010 s, jr_delay = 0.025 s

### ADR-001 — Canonical identifiers
**Choice**: `NodeId = int` (0..N-1; optional display label); `GroupId = str` (e.g. `"demo"`) that maps 1:1 to a synthetic `224.x.y.z` only at a future wire/RFC 5444 boundary; one per-source `uint32` sequence space shared by Join Query and data, compared with RFC 1982 serial-number arithmetic.
**Reason**: Removes the IP-vs-name inconsistency across specs; a shared counter matches the draft's "Join Query is a data packet with a header".
**Bead**: `odmrp-e47`.

### ADR-002 — Join Query piggyback
**Choice**: Hybrid (ns-2 / GloMoSim style). A `DataPacket` may carry an optional `JoinQueryHeader`. On refresh, if data is queued the next data packet carries the JQ; if the session is still active with no data queued, a standalone JQ (empty payload) is sent. Trace records both as `kind=JOIN_QUERY` with `piggybacked: bool`.
**Reason**: Matches draft-ietf-manet-odmrp-04 §3.1 and the reference implementations (finding F-01).
**Bead**: `odmrp-4i9`.

### ADR-003 — Forwarding Group table scope
**Choice**: Key FG state by `group` (draft-conformant). Keep per-source refresh bookkeeping for observability. Expose `fg_scope: "group" | "source_group"` as a protocol parameter; default `"group"`.
**Reason**: Matches draft §3.6.2; multi-source meshes differ from the old `(source, group)` keying (finding F-03).
**Bead**: `odmrp-1wq`.

### ADR-004 — Join Reply table form
**Choice**: Join Reply is a table: `Count`, `R` (ack-request), `F` (from FG node), group, and `n` entries of `(Sender, NextHop[, RET])`. Intermediate nodes build their own Join Reply from matched entries and broadcast once per refresh if the arrival carries no new source information. RFC 5444 link-local aggregation of multiple Join Replies remains a roadmap item.
**Reason**: Required for correct multi-source behaviour; matches every existing implementation (finding F-02).
**Bead**: `odmrp-3fq`.

### ADR-005 — ODMRPNode interface
**Choice**: Time-driven, pure-output protocol (simulator owns transmission and tracing):
```python
class ODMRPNode(Protocol):
    def configure(self, node_id: NodeId, params: ProtocolParams, rng_seed: int) -> None: ...
    def set_membership(self, group: GroupId, member: bool, now: float) -> list[Packet]: ...
    def originate(self, group: GroupId, payload: bytes, now: float) -> list[Packet]: ...
    def receive(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]: ...
    def advance(self, now: float) -> list[Packet]: ...
    def next_timer(self) -> float | None: ...
    def get_state(self) -> NodeState: ...
```
**Reason**: External C++/Rust nodes need explicit time and timers (finding F-10). Same seven ops form the NDJSON IPC contract.
**Bead**: `odmrp-e7x`.

### ADR-006 — Trace / event schema v1
**Choice**: One JSON-lines schema consumed by the WebSocket feed, pytest-bdd, and multi-implementation diffs. Envelope: `t`, `seq`, `node`, `kind`. Kinds: `tx`, `rx`, `drop`, `state.route`, `state.fg`, `state.member`, `timer`, `deliver`, `transfer`, `topology`, `sim`. Canonical order key: `(t, seq)`.
**Reason**: Determinism and external validation need a single event surface (finding F-09). Normative table: `docs/architecture/03-data-model-and-interfaces.md` §3.4.
**Bead**: `odmrp-0e3`.

### ADR-007 — Frontend rendering
**Choice**: Svelte 5 + plain SVG (nodes, links, FG halo, packet dots via `requestAnimationFrame`). Canvas fallback above ~300 nodes. Graph component is dumb: positions and state come from the WebSocket store. Do **not** use vis-network.
**Reason**: Simulator owns positions; physics layout would fight them; link-specific packet animation is awkward in vis-network (finding F-13).
**Bead**: `odmrp-4z9`.

### Messaging & Files
- Text messages are single packets (or few if large).
- Files are split into fixed-size chunks (1 KB), each carrying a transfer-id, sequence, and total count. Receivers reassemble and expose the completed file via a download endpoint.

## Data Structures (per node)
- Routing table: `source → (next_hop, seq, expires_at)` (draft §3.6.1)
- Forwarding Group table: `group → (expires_at, refreshed_by, last_refresh)` (draft §3.6.2; ADR-003)
- Group membership set
- Message cache: `(source, seq) → timestamp` LRU (draft §3.6.3)
- Source sessions: `group → (next_seq, last_data_at, next_refresh_at, mesh_established)`
- Sequence number counter (per source, shared by JQ and data)

## Out of Scope (captured as beads)
- Unidirectional link detection and blacklist
- Join Reply aggregation
- Mobility prediction / adaptive refresh
- Full RFC5444 encoding
- Multi-source concurrent sessions beyond basic support
