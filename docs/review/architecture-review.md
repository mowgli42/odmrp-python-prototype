# Architecture review — ODMRP Python prototype

| | |
|---|---|
| Reviewed revision | `0b39375` (`Add complete OpenSpec + Gherkin system description`) |
| Repository state | Specification only: `proposal.md`, `design.md`, `tasks.md`, `beads.md`, `DEMO.md`, `specs/*/spec.md`. No source code, no build files, no scenario fixtures. |
| Primary references | draft-ietf-manet-odmrp-02 (Jan 2000) and -04 (Nov 2002); draft-yi-manet-odmrp-00 (Mar 2003); Lee, Gerla, Chiang, *On-Demand Multicast Routing Protocol*, WCNC 1999; Lee, Su, Gerla, *ODMRP in Multihop Wireless Mobile Networks*, MONET 2002; UCLA GloMoSim / CMU Monarch ns-2 ODMRP implementations (as documented in the RIT RODMRP thesis); Oh, Park, Gerla, *E-ODMRP*, JPDC 2008; Gerla, Lamont, Pellegrino, *ODMRP-ASYM* (unidirectional links, RFC 5444 format proposal); gautamgitspace/ODMRP (Java, RFC 5444 framing, 2016). |
| Companion documents | `adherence-matrix.md` (mechanism-by-mechanism comparison), `../architecture/` (target architecture), `../sequences/` (protocol and system sequences), `../mockups/` (UI wireframes), `../implementation-plan.md` (beads). |

## 1. Executive summary

The repository is a well-scoped *intent* document: the OpenSpec + Gherkin layout is coherent, the goals (observable, deterministic, swappable node implementations) are the right ones for a reference prototype, and the chosen defaults (3 s refresh, 9 s FG lifetime) match the values the UCLA authors used in their simulations.

It is not yet an implementable architecture. The protocol description simplifies three mechanisms in ways that would make traces from this prototype disagree with every existing ODMRP implementation — which defeats its stated purpose as a test harness for C++ and Rust ports:

1. **Join Query is modelled as a standalone control packet.** In the drafts and in GloMoSim/ns-2 it is a *data packet with the Join Query header piggybacked* (draft §3.1). [F-01]
2. **Join Reply is modelled as a single next-hop pointer.** It is a *table* of (Sender, NextHop) entries with Count and R/F flags; forwarding-group nodes forward it once per refresh built from the *matched* entries only (draft §4.2, §5.1.6). Without the table form, multi-source groups do not work. [F-02]
3. **Forwarding Group state is keyed by (source, group).** The draft keys it by group (§3.6.2); the difference changes which nodes forward data when a group has more than one source. [F-03]

Two structural issues affect the harness goal rather than protocol fidelity:

4. **The `ODMRPNode` seam has no notion of time.** An external node cannot run soft-state timers through `receive()` alone; it needs `advance(now)` and a timer-query method, and all methods should return the packets to transmit so the simulator owns I/O and tracing. [F-10]
5. **Determinism is asserted but not designed.** No event-ordering rule, RNG ownership, or trace schema is defined; these are prerequisites for the "two runs produce identical FG membership" scenario. [F-09]

Everything else is a matter of filling gaps (timer/TTL/jitter parameters, identifier types, spec name drift) and of sequencing the work so the seam and the trace exist before the protocol is written. All findings are captured as beads; the seven that need a decision are `decision` beads under the Phase 0 epic (`odmrp-vy0`).

**Verdict:** proceed, after the Phase 0 decisions. The recommended target architecture (`../architecture/`) keeps every choice in `design.md` that is sound (single process, distance-based links, simulation-clock timers, FastAPI + WebSocket, Svelte) and changes only the packet/table model, the node interface, and the build order.

## 2. What exists today

```
proposal.md          why / what / impact / success criteria
design.md            architecture sketch, key decisions, data structures, interface seam
tasks.md             7 phases, 30 checkbox tasks (no dependencies, no acceptance criteria)
beads.md             10 roadmap items (prose list, not tracked)
DEMO.md              intended run commands and happy-path script
specs/odmrp          7 requirements, 11 Gherkin scenarios
specs/simulation     4 requirements, 5 scenarios
specs/messaging      3 requirements, 3 scenarios
specs/visualization  4 requirements, 4 scenarios
specs/test-harness   3 requirements, 3 scenarios
```

Observations on the document set itself:

- The Gherkin is readable and mostly testable, but several scenarios assert on internal state ("installs or refreshes a routing entry") rather than observable behaviour. The trace schema (ADR-006) is how those become observable without white-box tests.
- `tasks.md` has no dependency information and no acceptance criteria; `beads.md` is prose. Both are now represented as beads (see `../implementation-plan.md`).
- `DEMO.md` references `scenarios/basic-mesh.yaml` and a "default 6-node topology" that are not defined anywhere. The 6-node topology used in the sequence diagrams (`../sequences/01-mesh-formation.md`) is proposed as that fixture.

## 3. Findings

Severity: **High** = traces would diverge from reference implementations or a stated goal is unachievable; **Medium** = design gap that will force rework if not decided now; **Low** = consistency/clarity.

### Protocol fidelity

**F-01 (High) — Join Query should be a piggybacked data-packet header, not only a control packet.**
Draft §2.1 defines Join Query as "the special data packet sent by multicast sources"; §3.1: the source "floods a member advertising packet with data payload piggybacked". ns-2's `odmrp_join_query` carries a `piggyback_` flag; GloMoSim behaves the same. Consequences for the prototype if kept as a pure control packet: one extra flood per refresh, different packet counts and timing in traces, and receivers that learn membership one packet later than reference implementations. Recommendation: hybrid as in ns-2 — `DataPacket` has an optional `JoinQueryHeader`; a standalone (empty-payload) Join Query is only emitted when the refresh timer fires with nothing queued. Bead: `odmrp-4i9` (ADR-002).

**F-02 (High) — Join Reply must be a table with Count, R, F flags and per-source entries.**
Draft §4.2 and the worked example in §3.1 (nodes I1/I2) define the aggregation rule: a node that finds its own address as next hop in one or more entries sets FG_FLAG, builds its *own* Join Reply from only those entries using its routing table, and broadcasts it once even if it receives several Join Replies carrying the same source set. The repo spec's "Join Reply containing the source, group, sequence number, and next-hop toward the source" is the single-source special case. Recommendation: adopt the table form now; RFC 5444 link-local aggregation of several Join Replies (the item deferred in README) stays deferred. Bead: `odmrp-3fq` (ADR-004).

**F-03 (High) — Forwarding Group table scope.**
Draft §3.6.2: "the multicast group ID and the time when the node was last refreshed are recorded" — the FG flag is per group, and §5.2 forwards data "if the setting of FG_FLAG for the multicast group has not expired". A node refreshed as FG by receivers of source S1 therefore also forwards data from source S2 of the same group. The repo's (source, group) key is stricter and yields a smaller mesh with multiple sources. Either can be argued for a prototype, but the default must be the draft's if traces are to be compared with GloMoSim/ns-2/QualNet. Recommendation: key by group, keep per-source refresh bookkeeping for the UI, expose `fg_scope` as a parameter. Bead: `odmrp-1wq` (ADR-003).

**F-04 (Medium) — Sequence number / message-cache identity.**
`specs/odmrp` says "Each source SHALL maintain a single sequence number space" and the message cache is keyed (source, seq). This is correct and matches the draft's "(Source IP Address, Sequence Number)" duplicate check, but only if data packets and Join Queries share the counter (which the piggyback model makes natural). The messaging spec's chunk "sequence" must be a separate application-level index (`transfer_id`, `index`, `total`) so protocol freshness and reassembly do not interfere. Define wrap-around with RFC 1982 serial arithmetic. Beads: `odmrp-e47` (ADR-001), `odmrp-iql`.

**F-05 (Medium) — Receiver join latency and the "Member Table".**
Receivers only answer Join Queries; a node that joins a group between refreshes is not reachable until the next Join Query arrives (up to ROUTE_REFRESH_INTERVAL later). The visualization scenario "subsequent messages to chat are eligible for delivery to R1" is true only after that refresh. The UI should show membership as *pending* until the node's first Join Reply is sent (mockup `02-node-inspector.svg`). The GloMoSim implementation also keeps a receiver-side Member Table with its own timeout; this is an implementation convenience, not required by the draft, and is not recommended for the prototype.

**F-06 (Medium) — Reliability machinery is absent, and that is fine until loss exists.**
Draft §3.2 (passive acknowledgement, R flag, retransmission, "next hop unreachable" fallback) is not mentioned in the spec and `beads.md` folds it into "unidirectional link detection". In a lossless single-process simulator none of it changes behaviour. The dependency must be recorded: any loss model (roadmap item 5) or real networking (item 3) first requires Join Reply reliability. Bead: `odmrp-bv6` (Join Reply reliability), which blocks the loss model (`odmrp-9bc`), real networking (`odmrp-32m`) and unidirectional links (`odmrp-ujn`).

**F-07 (Medium) — Timer defaults are right; jitter, TTL and session-idle timers are missing.**
The drafts give no numeric defaults; they require FG timeout to be "3 to 5 times" the refresh interval. 3 s / 9 s are the UCLA simulation settings (restated in the E-ODMRP paper). Reference implementations also add (a) a small random jitter before rebroadcasting a Join Query, (b) a short delay before a receiver sends its Join Reply so several Join Queries can be collected, and (c) an idle rule for when a source stops refreshing. The prototype needs all three as seeded, configurable parameters: `jq_jitter` (default 10 ms), `jr_delay` (25 ms), `source_idle_timeout` (= refresh interval), plus `join_query_ttl` (32) and `message_cache_size`. `ROUTE_TIMEOUT` is not in the draft (routing entries are simply overwritten) but is harmless and useful for the UI. Bead: `odmrp-amm`.

**F-08 (Low) — Data-plane rules are under-specified in one direction.**
The spec covers "FG forwards" and "non-FG does not forward" but not: the source transmits regardless of FG status; a receiver that is a group member but not FG delivers locally and does not forward; a node that is both member and FG does both. Sequence `../sequences/02-data-forwarding.md` spells these out. Bead: `odmrp-2xj`.

### Harness and determinism

**F-09 (High) — Determinism needs an explicit design.**
Required and currently undefined: (1) scheduler ordering for equal timestamps — key by `(time, global_seq, node_id)`; (2) a single seeded RNG owned by the engine, with per-node sub-generators derived from `(seed, node_id)` so adding a node does not perturb others; (3) no wall-clock reads inside the simulation; (4) a canonical trace event schema with a total order `(t, seq)`, so "identical traces" is a byte comparison. Beads: `odmrp-d3t`, `odmrp-0e3` (ADR-006), `odmrp-7vc`.

**F-10 (High) — The `ODMRPNode` seam cannot host an external implementation as written.**

```python
# design.md today
class ODMRPNode(Protocol):
    def receive(self, packet: Packet, previous_hop: NodeId) -> list[Packet]: ...
    def originate_data(self, group: str, payload: bytes) -> None: ...
    def get_state(self) -> NodeState: ...
```

Missing: time (soft state cannot expire), membership changes, configuration, and a symmetric return type (`originate_data` returns nothing, so the simulator cannot trace what the node transmitted). `specs/test-harness` uses different names (`process_packet`, `originate_join_query`). Recommended seam (ADR-005, `odmrp-e7x`):

```python
class ODMRPNode(Protocol):
    def configure(self, params: ProtocolParams) -> None: ...
    def set_membership(self, group: GroupId, member: bool, now: float) -> list[Packet]: ...
    def originate(self, group: GroupId, payload: bytes, now: float) -> list[Packet]: ...
    def receive(self, packet: Packet, previous_hop: NodeId, now: float) -> list[Packet]: ...
    def advance(self, now: float) -> list[Packet]:      # fire timers due at or before now
    def next_timer(self) -> float | None: ...            # lets the scheduler skip idle time
    def get_state(self) -> NodeState: ...
```

All methods are pure with respect to I/O: the node returns packets, the `NodeHost` transmits and traces them. The same seven calls map one-to-one onto an NDJSON-over-stdio protocol for C++/Rust processes (`../sequences/06-external-node-adapter.md`).

**F-11 (Low) — Name and type drift across documents.**
Interface names (`receive` vs `process_packet`), group identifiers (`224.1.1.1` vs `"chat"`), node identifiers (`S`, `R1` vs `node 3`), and the FG timeout wording differ between files. ADR-001 fixes identifiers; ADR-005 fixes names. Bead: `odmrp-e47`.

### System architecture

**F-12 (Low) — The single-process, distance-based, simulation-clock decisions are sound.** They are the same decisions the UCLA authors took in GloMoSim and nothing in the harness goal requires changing them. The `LossModel` and `symmetric_links` hooks recommended in Phase 1 keep the roadmap items drop-in.

**F-13 (Medium) — vis-network is the wrong rendering choice.** Its force layout will fight simulator-owned positions, and per-link packet animation is awkward. Plain SVG in Svelte 5 (Canvas above a few hundred nodes) is simpler and deterministic. Bead: `odmrp-4z9` (ADR-007).

**F-14 (Medium) — WebSocket protocol needs snapshot + delta semantics and backpressure.** Pushing "state whenever anything changes" (design.md) does not scale past a handful of packets per second. Recommended: snapshot on connect; event frames coalesced every 50 ms; `tx/rx` events droppable for slow clients, `state.*` events never dropped. Bead: `odmrp-hlj`.

**F-15 (Low) — File transfer is best-effort by construction.** Without retransmission a single lost chunk leaves a partial file. Acceptable in a lossless simulator; the transfer state machine (`../architecture/04-state-machines.md`) therefore exposes `missing` indices so the UI can show partial transfers honestly, and repair is left to the roadmap.

**F-16 (Low) — "Full RFC 5444 encoding" is a new design, not a deferral.** No IETF ODMRP draft uses RFC 5444; the drafts define fixed binary headers. The RFC 5444 mapping exists only in later academic work (ODMRP-ASYM) and in the UB Java implementation (message types 127/128, address-block TLV type extensions 0/1 for group and next-hop). If the harness ever moves to real networking, that Java layout is a reasonable starting point; until then the dataclass fields should simply mirror draft §4 so the codec is a pure mapping.

### Process

**F-17 (Medium) — Build order.** `tasks.md` implements the protocol (Phase 2) before the node interface and trace (Phase 6). Reversing that order costs nothing and means every Phase 2 test asserts on trace events through the seam, which is exactly what an external implementation will be judged by. The beads plan encodes this as Phase 6a (`odmrp-e6c`) blocking Phase 2.

## 4. Recommended target architecture (summary)

Full detail in `../architecture/`. In one paragraph: a FastAPI process hosts one `SimulationEngine` (scheduler + seeded RNG), a `Topology` (positions, ranges, incremental neighbour sets), a `Medium` (broadcast delivery with delay/jitter and a loss hook), one `NodeHost` per node wrapping an `ODMRPNode` implementation (Python reference or external process), an `EventBus` with three subscribers (JSONL trace, ring buffer, WebSocket broadcaster), and a `MessagingService` that turns text and files into `AppPayload`s and reassembles them from `deliver` events. The Svelte frontend is a dumb renderer of the WebSocket store plus REST calls for every mutation.

```mermaid
flowchart LR
  UI[Svelte UI] <-- WS snapshot + deltas --> WS[WebSocket broadcaster]
  UI -- REST --> API[FastAPI routers]
  API --> SVC[MessagingService / Scenario loader / Controls]
  SVC --> ENG[SimulationEngine<br/>scheduler · seeded RNG]
  ENG --> TOPO[Topology]
  ENG --> MED[Medium]
  ENG --> HOST[NodeHost × N]
  HOST --> NODE[ODMRPNode<br/>Python ref | external]
  HOST --> BUS[EventBus]
  MED --> BUS
  BUS --> WS
  BUS --> TR[JSONL trace]
  BUS --> RB[Ring buffer]
```

## 5. Recommended sequence (summary)

Phase 0 decisions → Phase 1 simulation core → Phase 6a seams (interface + trace) → Phase 2 protocol → Phase 3 messaging → Phase 4 API/WS → Phase 5 UI and Phase 6b executable Gherkin in parallel → Phase 7 demo. Roadmap items hang off the beads that enable them (e.g. loss model and real networking both depend on Join Reply reliability). See `../implementation-plan.md` for the full graph with IDs, and run `bd ready` for the current frontier.

## 6. References

- S.-J. Lee, W. Su, M. Gerla, *On-Demand Multicast Routing Protocol (ODMRP) for Ad Hoc Networks*, draft-ietf-manet-odmrp-02, January 2000. (Includes §6 "Simulation and Implementation Status": GloMoSim and a Linux 2.0.36 testbed.)
- Y. Yi, S.-J. Lee, W. Su, M. Gerla, draft-ietf-manet-odmrp-04, November 2002; draft-yi-manet-odmrp-00, March 2003 (same text; adds passive clustering).
- S.-J. Lee, M. Gerla, C.-C. Chiang, *On-Demand Multicast Routing Protocol*, IEEE WCNC 1999.
- S.-J. Lee, W. Su, M. Gerla, *On-Demand Multicast Routing Protocol in Multihop Wireless Mobile Networks*, Mobile Networks and Applications 7(6), 2002.
- S. Y. Oh, J.-S. Park, M. Gerla, *E-ODMRP: Enhanced ODMRP with Motion Adaptive Refresh*, J. Parallel Distrib. Comput. 2008 — source for the "3 s refresh / 9 s forwarder lifetime" simulation settings.
- M. Gerla, L. Lamont, F. Pellegrino et al., *On demand multicast routing with unidirectional links* (ODMRP-ASYM) and the follow-on thesis *Multicast and flooding in Ad Hoc Networks* proposing an RFC 5444 packet format.
- RIT thesis *RODMRP — Resilient On-Demand Multicast Routing Protocol* — documents the CMU Monarch ns-2 ODMRP classes (`ODMRPAgent`, `hdr_odmrp`, `MSGCache`, `McastMemberTable`, `JQTable`, `JRTable`, `JoinQueryTimer`, `JoinReplyTimer`, `piggyback_` flag).
- gautamgitspace/ODMRP (GitHub, 2016) — Java, RFC 5444 framing, `ROUTING_TIMEOUT`, `FG_TIMEOUT`, `ACK_TIMEOUT` constants.
- T. Clausen, C. Dearlove, J. Dean, C. Adjih, RFC 5444, *Generalized MANET Packet/Message Format*, 2009.
- R. Elz, R. Bush, RFC 1982, *Serial Number Arithmetic*, 1996.
