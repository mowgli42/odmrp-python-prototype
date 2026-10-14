# Architecture 4 — State machines

Per-entity state machines that the Phase 1–3 beads implement. All transitions are driven by simulation time or packets; none by wall-clock.

## 4.1 Forwarding-group entry (per node, per group) — draft §3.6.2, §5.1.6, §3.3

```mermaid
stateDiagram-v2
  [*] --> NotFG
  NotFG --> FG : Join Reply received with an entry whose next_hop == self<br/>set expires_at = now + FG_TIMEOUT, refreshed_by = {sender}
  FG --> FG : matching Join Reply<br/>expires_at = now + FG_TIMEOUT, refreshed_by ∪= {sender}
  FG --> NotFG : timer fg_expire fires (now ≥ expires_at)<br/>emit state.fg op=expire
  note right of FG
    While FG: forward non-duplicate DATA for this group.
    Forward own Join Reply once per (group, source set, source seq).
  end note
```

## 4.2 Routing entry (per node, per source) — draft §3.6.1, §5.1.2

```mermaid
stateDiagram-v2
  [*] --> Unknown
  Unknown --> Known : non-duplicate Join Query from source S via P<br/>next_hop = P, seq = S.seq, expires_at = now + ROUTE_TIMEOUT
  Known --> Known : Join Query with newer seq (RFC 1982)<br/>refresh next_hop/seq/expires_at
  Known --> Known : Join Query with same seq → duplicate, ignored
  Known --> Unknown : timer route_expire fires
  note right of Known
    Used to fill next_hop when building a Join Reply.
    If Unknown at Join Reply build time, the entry for S is omitted.
  end note
```

## 4.3 Source session (per source node, per group) — draft §5.1.1, §3.3

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Querying : originate(group, payload)<br/>seq += 1; send DATA with Join Query header (piggybacked);<br/>arm route_refresh = now + ROUTE_REFRESH_INTERVAL
  Querying --> Established : Join Reply received with entry (sender == self)
  Established --> Established : originate() → send DATA (no header)
  Querying --> Querying : originate() → send DATA (no header)
  Established --> Refreshing : route_refresh fires
  Querying --> Refreshing : route_refresh fires
  Refreshing --> Querying : data queued or sent within SOURCE_IDLE_TIMEOUT<br/>seq += 1; send Join Query (piggybacked if data queued, else standalone);<br/>re-arm route_refresh
  Refreshing --> Idle : no data for SOURCE_IDLE_TIMEOUT<br/>stop refreshing (soft leave)
  note right of Established
    "Established" is observational only (UI badge);
    forwarding never depends on it.
  end note
```

## 4.4 Group membership (per node, per group) — receiver side

```mermaid
stateDiagram-v2
  [*] --> NonMember
  NonMember --> MemberPending : set_membership(group, true)<br/>emit state.member
  MemberPending --> MemberActive : Join Query for group received<br/>→ Join Reply originated after JR_DELAY
  MemberActive --> MemberActive : each new Join Query → new Join Reply
  MemberActive --> NonMember : set_membership(group, false)<br/>(no leave packet; FG nodes expire upstream)
  MemberPending --> NonMember : set_membership(group, false)
  note right of MemberPending
    Visible in the UI as "pending": the node will not receive data
    until the source's next refresh (≤ ROUTE_REFRESH_INTERVAL).
  end note
```

## 4.5 Transfer assembler (per receiver, per transfer_id) — Phase 3

```mermaid
stateDiagram-v2
  [*] --> Receiving : first chunk (any index) delivered<br/>total known from chunk header
  Receiving --> Receiving : chunk delivered, index new → received += 1
  Receiving --> Receiving : chunk delivered, index known → ignore (duplicate)
  Receiving --> Verifying : received == total
  Verifying --> Complete : sha256 matches → file stored, transfer op=complete
  Verifying --> Failed : sha256 mismatch → transfer op=verify_failed
  Receiving --> Stalled : no chunk for TRANSFER_STALL_TIMEOUT (default 3 × ROUTE_REFRESH_INTERVAL)
  Stalled --> Receiving : late chunk delivered
  note right of Stalled
    Best-effort transport: Stalled exposes `missing` indices to the UI.
    Repair (NACK / re-request) is a roadmap bead.
  end note
```

## 4.6 Simulation engine run modes — Phase 1 / Phase 4

```mermaid
stateDiagram-v2
  [*] --> Empty
  Empty --> Paused : load(scenario | inline network)<br/>emit sim op=load
  Paused --> Running : POST /sim/run<br/>real-time driver maps sim time to wall-clock × speed
  Running --> Paused : POST /sim/pause
  Paused --> Paused : POST /sim/step {dt}<br/>run_until(t + dt), then stop
  Running --> Running : PUT /sim/speed
  Paused --> Paused : PUT /params → reset with same topology + seed
  Running --> Paused : PUT /params
  Paused --> Paused : POST /sim/reset (same seed)
  Running --> Paused : POST /sim/reset
  note right of Running
    POST /sim/step while Running → 409 Conflict.
    Mutations (join, move, send) are allowed in both Paused and Running;
    they are scheduled at the current sim time.
  end note
```

## 4.7 Packet life cycle (for the trace and the animation layer)

```mermaid
stateDiagram-v2
  [*] --> Created : node returns Packet from receive/advance/originate
  Created --> Transmitted : NodeHost → Medium.broadcast<br/>emit tx {neighbors}
  Transmitted --> InFlight : one rx event scheduled per neighbour at now + delay + jitter
  InFlight --> Received : rx fires → NodeHost.deliver → node.receive
  InFlight --> Lost : LossModel.drop → emit drop reason=loss
  Received --> Consumed : node returns [] (delivered / cached / not FG)
  Received --> Forwarded : node returns packets → each becomes a new Created
  note right of Transmitted
    The animation layer draws one dot per (tx, rx) pair along the link,
    coloured by packet kind; drops render as a short cross at the receiver.
  end note
```
