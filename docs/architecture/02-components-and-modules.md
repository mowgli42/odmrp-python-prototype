# Architecture 2 — Components and modules

C4 level 3 for the backend and the frontend, plus the one rule that keeps the harness goal intact: **only `NodeHost` talks to an `ODMRPNode`, and only `Medium` delivers packets.**

## 2.1 Backend components

```mermaid
flowchart TB
  subgraph api["odmrp_sim.api"]
    R1[routers.network]
    R2[routers.nodes / groups]
    R3[routers.messages / files]
    R4[routers.sim]
    R5[routers.trace]
    WS[ws.WebSocketBroadcaster]
  end
  subgraph services["odmrp_sim.services"]
    SES[SimulationSession<br/>one per process]
    MSG[MessagingService]
    TRF[TransferAssembler registry]
    DR[DeliveryReportBuilder]
    SCN[ScenarioLoader]
    CTL[SimControls<br/>run/pause/step/speed/reset]
  end
  subgraph sim["odmrp_sim.sim"]
    ENG[SimulationEngine]
    SCH["Scheduler<br/>heap (t, seq, node)"]
    RNG[SeededRng<br/>per-node substreams]
    TOPO[Topology<br/>positions, ranges, neighbour sets]
    MED[Medium<br/>broadcast, delay, jitter, LossModel]
    TMR[TimerService]
    NH[NodeHost × N]
  end
  subgraph protocol["odmrp_sim.protocol"]
    IF[[ODMRPNode Protocol]]
    PY[PythonODMRPNode]
    TB[tables: RoutingTable, FGTable,<br/>MessageCache, Members]
    FK[FakeNode]
    EXT[ExternalProcessNode<br/>roadmap]
  end
  subgraph events["odmrp_sim.events"]
    BUS[EventBus]
    JSONL[JsonlTraceWriter]
    RING[RingBuffer]
  end

  R1 & R2 & R3 & R4 & R5 --> SES
  SES --> MSG & SCN & CTL & DR
  MSG --> TRF
  SES --> ENG
  CTL --> ENG
  ENG --> SCH & RNG & TOPO & MED & TMR & NH
  MED --> SCH
  TMR --> SCH
  NH --> IF
  IF -.implemented by.-> PY & FK & EXT
  PY --> TB
  NH --> MED
  NH --> BUS
  MED --> BUS
  TOPO --> BUS
  ENG --> BUS
  BUS --> JSONL & RING & WS
  DR --> RING
  MSG --> NH
```

### Component contracts

| Component | Key API | Notes |
|---|---|---|
| `Scheduler` | `schedule(t, node, fn, *args) -> handle`, `cancel(handle)`, `pop() -> Event`, `peek_time()` | Heap keyed `(t, global_seq, node_id)`. `global_seq` is a monotonically increasing counter, so equal-time events run in scheduling order. |
| `SeededRng` | `for_node(node_id) -> random.Random` | Substream seed = `hash((seed, node_id))`; the medium uses `for_node(sender)` for jitter so adding nodes does not perturb others. |
| `Topology` | `add(node_spec)`, `remove(id)`, `move(id, pos, now)`, `neighbors(id) -> frozenset`, `links() -> set[tuple]` | Incremental recompute on move; publishes `topology` events with link deltas only. |
| `Medium` | `broadcast(sender, packet, now)` | For each current neighbour: `t_rx = now + hop_delay + rng.uniform(0, jitter)`; `LossModel.drop(sender, receiver, packet) -> bool` hook (default never). Publishes `tx`, `rx`, `drop`. |
| `TimerService` | `arm(node, key, at, payload)`, `disarm(node, key)` | Re-arming a key cancels the previous handle; the host calls `node.advance(now)` when a timer fires. |
| `NodeHost` | `deliver(packet, prev_hop, now)`, `tick(now)`, `originate(group, payload, now)`, `set_membership(group, bool, now)`, `state()` | Wraps one `ODMRPNode`; every returned packet goes to `Medium.broadcast` and a `tx` event. Also diffs `NodeState` before/after each call to emit `state.*` events, so implementations do not need to emit events themselves. |
| `EventBus` | `publish(event)`, `subscribe(fn)` | Synchronous fan-out; subscribers must not block. |
| `SimulationSession` | `load(scenario)`, `engine`, `messaging`, `controls` | The single object the API holds. |

### Why `NodeHost` diffs state instead of asking nodes to emit events

External implementations only have to implement the seven `ODMRPNode` methods; they never see the event schema. The host snapshots `get_state()` after every call and publishes `state.route`, `state.fg`, `state.member` deltas. It is slightly more work per call (state is small: a few dicts) and removes an entire class of conformance bugs.

## 2.2 Python reference node internals

```mermaid
flowchart LR
  subgraph PythonODMRPNode
    direction TB
    RX[receive] --> DISP{packet.kind}
    DISP -- JOIN_QUERY / DATA+JQ --> JQ[process_join_query<br/>draft 5.1.2]
    DISP -- JOIN_REPLY --> JR[process_join_reply<br/>draft 5.1.6]
    DISP -- DATA --> DT[process_data<br/>draft 5.2]
    JQ --> MC[(MessageCache)]
    JQ --> RT[(RoutingTable)]
    JQ -- member? --> JRO[originate_join_reply<br/>after jr_delay]
    JR --> FG[(FGTable)]
    JR --> RT
    JR --> JRF[forward_join_reply<br/>once per refresh]
    DT --> MC
    DT --> FG
    ADV[advance] --> T{due timers}
    T -- route_refresh --> JQO[originate_join_query<br/>draft 5.1.1]
    T -- fg_expire --> FG
    T -- route_expire --> RT
    T -- jr_delay --> JRO
    ORI[originate] --> SESS[(SourceSession)]
    SESS --> JQO
    MEM[set_membership] --> MB[(Members)]
  end
```

Every handler returns `list[Packet]`; no handler schedules or transmits. Timers are expressed by `next_timer()` plus internal due-lists, so the same code can run against the simulator or a real clock later.

## 2.3 Frontend components

```mermaid
flowchart TB
  subgraph store["src/lib/stores"]
    S[sim.svelte.ts<br/>$state: topology, nodes, params, sim, events ring, selection]
    WSC[wsClient.ts<br/>snapshot → replace; events → append; node → merge]
    API[api.ts<br/>typed fetch from OpenAPI]
  end
  subgraph components["src/lib/components"]
    TB[Toolbar.svelte<br/>run/pause/step/speed · clock · scenario · params]
    NV[NetworkView.svelte<br/>SVG nodes/links/halos · drag · zoom]
    PA[PacketLayer.svelte<br/>rAF animation of tx→rx]
    NI[NodeInspector.svelte<br/>tables, groups, inbox]
    MP[MessagingPanel.svelte<br/>compose, upload, delivery report]
    TL[TraceTimeline.svelte<br/>filterable event log]
    LG[Legend.svelte]
  end
  WSC --> S
  S --> TB & NV & PA & NI & MP & TL & LG
  TB & NV & NI & MP --> API
```

Rules: components never fetch directly except through `api.ts`; `NetworkView` positions come only from the store (drag applies an optimistic position, then `PUT /api/nodes/{id}/position`; the next snapshot/node delta is authoritative).

## 2.4 Cross-cutting

- **Identifiers** (ADR-001): `NodeId = int`, `GroupId = str`, `PacketId = str` (`f"{src}:{seq}"` for protocol packets; UUID for app payloads).
- **Time**: `float` seconds of simulation time everywhere in the backend; the WS frame carries `sim.t` and the UI formats it. No `time.time()` inside `sim/` or `protocol/` (enforced by a test that greps the package).
- **Errors**: protocol handlers never raise on malformed packets; they return `[]` and the host emits `drop reason=malformed`.
- **Configuration**: `ProtocolParams` is immutable per network; changing it via REST resets the session with the same topology and seed.
