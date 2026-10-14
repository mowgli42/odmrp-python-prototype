# Sequence 3 — Soft state: refresh, expiry, leave

Draft §3.3 (no explicit leave), §3.4 (FG timeout 3–5× refresh). Defaults: `ROUTE_REFRESH_INTERVAL = 3 s`, `FG_TIMEOUT = 9 s`, `ROUTE_TIMEOUT = 9 s`, `SOURCE_IDLE_TIMEOUT = 3 s`.

## 3.1 Timeline of one FG node while the source keeps sending

```mermaid
gantt
  title FG node 1 — timers (source active from t=1.0)
  dateFormat X
  axisFormat %s s
  section Source 0
  JQ seq=1            :milestone, m1, 1, 0
  JQ seq=2            :milestone, m2, 4, 0
  JQ seq=3            :milestone, m3, 7, 0
  JQ seq=4            :milestone, m4, 10, 0
  section Node 1 FG(demo)
  FG set  (exp 10.x)  :a1, 1, 9
  refresh (exp 13.x)  :a2, 4, 9
  refresh (exp 16.x)  :a3, 7, 9
  refresh (exp 19.x)  :a4, 10, 9
```

Each Join Reply that names node 1 as next hop re-arms `fg_expire:demo` to `now + 9`. The entry never expires while refreshes keep arriving every 3 s.

## 3.2 Source stops: everything drains without any leave packet

```mermaid
sequenceDiagram
  autonumber
  participant S as Node 0 (source)
  participant A as Node 1 (FG)
  participant R1 as Node 3 (FG + member)
  participant R2 as Node 5 (member)

  Note over S: last data at t=8.0
  Note over S: t=10.0 route_refresh fires<br/>data within SOURCE_IDLE_TIMEOUT (3 s)? yes (8.0) → refresh
  S->>A: JQ seq=4 (standalone, empty payload)
  A->>R1: JQ
  R1->>R2: JQ
  R2-->>R1: JR
  R1-->>A: JR
  A-->>S: JR
  Note over A,R1: fg_expire re-armed to 19.x

  Note over S: t=13.0 route_refresh fires<br/>no data since 8.0 (> 3 s) → session Idle, timer not re-armed
  Note over S,R2: no more Join Queries → no more Join Replies

  Note over A: t≈19.0 fg_expire fires → FG cleared (state.fg op=expire)
  Note over R1: t≈19.0 fg_expire fires → FG cleared
  Note over A,R2: t≈19.0 route_expire fires at every node → route[0] removed
  Note over R1,R2: still members (membership is local state, not soft)
```

Worst-case residual: an FG flag can outlive the last data by `SOURCE_IDLE_TIMEOUT + FG_TIMEOUT` (here 8.0 → 19.x s). This is inherent to soft state and is what the UI's fading halo visualises.

## 3.3 Receiver leaves: upstream forwarders expire

```mermaid
sequenceDiagram
  participant S as Node 0
  participant A as Node 1 (FG)
  participant R1 as Node 3 (FG + member)
  participant R2 as Node 5 (member)
  participant UI as UI

  UI->>R2: DELETE /api/nodes/5/groups/demo
  Note over R2: members -= {demo} (state.member false)<br/>no packet is sent
  S->>A: next JQ (seq=n)
  A->>R1: JQ
  R1->>R2: JQ
  Note over R2: not a member → no Join Reply
  R1-->>A: JR [(0, next_hop=1)]  (3 is still a member)
  Note over R1: nobody names 3 as next hop any more<br/>FG(demo) at node 3 is NOT refreshed → expires 9 s after its last refresh
  Note over A: still refreshed by 3 → stays FG
```

After node 3's FG flag expires, the mesh is exactly the path `0–1–3` serving the one remaining receiver. Nothing was signalled; the mesh shrank by omission.

## 3.4 Receiver joins late: pending until the next refresh

```mermaid
sequenceDiagram
  participant S as Node 0
  participant B as Node 2
  participant C as Node 4
  participant UI as UI
  UI->>C: POST /api/nodes/4/groups {group: demo}   (t = 5.0)
  Note over C: MemberPending — no Join Query seen since joining
  S->>B: DATA seq=k (t = 5.5)  — node 2 not FG → not forwarded
  Note over C: receives nothing (correct: not yet on the mesh)
  S->>B: JQ seq=k+1 (t = 7.0, next refresh)
  B->>C: JQ
  Note over C: member → deliver piggybacked payload, send JR [(0, next_hop=2)]
  C-->>B: JR
  Note over B: FG(demo) set
  B-->>S: JR [(0, next_hop=0)]
  Note over C: MemberActive / FG set is now {1, 3, 2}
```

Expected join latency is uniform in `[0, ROUTE_REFRESH_INTERVAL)`; the inspector shows the countdown to the source's next refresh so the delay is explainable.

## 3.5 Timer bookkeeping (host side)

```mermaid
sequenceDiagram
  participant N as PythonODMRPNode
  participant H as NodeHost
  participant T as TimerService
  participant Sch as Scheduler
  H->>N: receive(JR, prev, now)
  N-->>H: [JR'] (packets to send)
  H->>N: next_timer()
  N-->>H: 10.025 (fg_expire)
  H->>T: arm(node, "wake", 10.025)
  T->>Sch: schedule(10.025, node, host.tick)
  Note over Sch: ... time passes ...
  Sch->>H: tick(now=10.025)
  H->>N: advance(10.025)
  N-->>H: [] (FG cleared internally)
  H->>H: diff get_state() → emit state.fg op=expire
  H->>N: next_timer() → None
```

The node keeps its own due-list; the host only needs one wake-up timer per node. External implementations follow the identical pattern over IPC.
