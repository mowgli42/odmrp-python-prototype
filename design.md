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
**Production bead**: Move to multi-process or container-per-node with real networking when validating distributed implementations.

### Distance-based connectivity
**Choice**: Neighbors = nodes whose Euclidean distance ≤ radio range.  
**Alternative**: Explicit link list or unit disk graph with obstacles.  
**Reason**: Intuitive for visualization and matches classic MANET papers.  
**Production bead**: Add probabilistic loss, asymmetric links, and mobility models.

### Soft-state timers with simulation clock
**Choice**: All timers (ROUTE_REFRESH_INTERVAL, FG_TIMEOUT, etc.) are driven by the simulation clock, not wall-clock.  
**Reason**: Enables deterministic, fast tests and step-through debugging.  
**Default values** (prototype):
- ROUTE_REFRESH_INTERVAL = 3.0 s
- FG_TIMEOUT = 9.0 s
- ROUTE_TIMEOUT = 9.0 s

### Packet model
Control packets (Join Query, Join Reply) and data packets (message or file chunk) are Python objects. The simulator delivers them only to current neighbors and invokes the receiving node’s ODMRP handler.

### External implementation seam
Each node holds an `ODMRPNode` interface:
```python
class ODMRPNode(Protocol):
    def receive(self, packet: Packet, previous_hop: NodeId) -> list[Packet]: ...
    def originate_data(self, group: str, payload: bytes) -> None: ...
    def get_state(self) -> NodeState: ...
```
The Python implementation satisfies this; a future adapter can speak to a C++ or Rust process over stdin/stdout or a local socket.

### Frontend
Svelte + a lightweight graph library (e.g. vis-network or a simple SVG/Canvas). State is pushed over WebSocket whenever topology, FG membership, or a packet event occurs.

### Messaging & Files
- Text messages are single packets (or few if large).
- Files are split into fixed-size chunks (e.g. 1 KB), each carrying a transfer-id, sequence, and total count. Receivers reassemble and expose the completed file via a download endpoint.

## Data Structures (per node)
- Routing table: source → (next_hop, seq, expiry)
- Forwarding table: (source, group) → (seq, expiry)
- Group membership set
- Duplicate cache: (source, seq) → timestamp (LRU)
- Sequence number counter (for sources)

## Out of Scope (captured as beads)
- Unidirectional link detection and blacklist
- Join Reply aggregation
- Mobility prediction / adaptive refresh
- Full RFC5444 encoding
- Multi-source concurrent sessions beyond basic support
