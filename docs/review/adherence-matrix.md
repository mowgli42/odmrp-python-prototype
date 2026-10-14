# Adherence matrix — repo spec vs. ODMRP references

How each ODMRP mechanism is defined by the IETF drafts, how the existing implementations realise it, what the repository's specs currently say, and the recommended position for the prototype. Status values:

- **Conforms** — repo spec matches the draft.
- **Partial** — direction is right, detail missing.
- **Deviates** — repo spec contradicts the draft or all reference implementations.
- **Silent** — not addressed in the repo.
- **Deferred** — intentionally out of scope (and recorded as a roadmap bead).

Column legend: *Draft* = draft-ietf-manet-odmrp-02/-04 (identical normative text for these rows). *GloMoSim / ns-2* = UCLA GloMoSim module and CMU Monarch ns-2 `ODMRPAgent` (as documented in the RODMRP thesis). *Java (UB)* = gautamgitspace/ODMRP, RFC 5444 framing.

## Control plane

| # | Mechanism | Draft | GloMoSim / ns-2 | Java (UB) | Repo spec today | Status | Recommendation / bead |
|---|---|---|---|---|---|---|---|
| 1 | Join Query trigger | Source with data and no route floods JQ; repeats every REFRESH_INTERVAL while data exists (§3.1, §5.1.1) | `JoinQueryTimer` per source; refresh while sending | Periodic JQ sender | Same ("pending data and no active FG"; refresh while data remains) | Conforms | Add `source_idle_timeout` to define when refresh stops. `odmrp-g0v` |
| 2 | Join Query carriage | Data packet with payload piggybacked (§2.1, §3.1) | `odmrp_join_query.piggyback_` flag inside the ODMRP header | Standalone RFC 5444 message | Standalone control packet | **Deviates** | Hybrid: optional JQ header on data packets, standalone only when nothing queued. ADR-002 `odmrp-4i9` |
| 3 | Join Query fields | Type, TTL, Hop Count, Group, Seq, Source, Previous Hop (+ optional GPS fields, MIN_LET) (§4.1) | Same subset (`seqno_`, `hop_count_`, prev hop in header) | Source, Seq, Group (address block) | Group, source, seq; TTL mentioned | Partial | Add hop_count, previous_hop, ttl explicitly in the dataclass. `odmrp-58d` |
| 4 | Duplicate detection | Message cache keyed (Source, Seq); LRU/FIFO allowed (§3.6.3, §5.1.2 step 1) | `MSGCache` (source, uid) | — | Duplicate cache (source, seq) → timestamp, LRU | Conforms | Make capacity a parameter. `odmrp-b21` |
| 5 | Backward learning | Insert/update routing entry source → previous hop on non-duplicate JQ (§3.6.1, §5.1.2 step 2) | `JQTable` | — | Same | Conforms | `odmrp-0ew` |
| 6 | JQ rebroadcast | hop_count+1, ttl−1, drop if ttl ≤ 0, set previous hop = self, broadcast (§5.1.2 steps 4–6) | Same; ns-2 drops at IP ttl ≤ 1 | — | "rebroadcast with TTL decrement if TTL remains positive" | Partial | Specify default TTL (32) and jitter before rebroadcast. `odmrp-0ew`, `odmrp-amm` |
| 7 | Join Reply trigger | Group member receiving a (non-duplicate) JQ originates JR (§5.1.2 step 3, §5.1.5) | Receiver sends Join Table; `JoinReplyTimer` | — | Same | Conforms | Add short `jr_delay` to collect multiple JQs (matches implementations). `odmrp-zig` |
| 8 | Join Reply content | Table: Type, Count, R flag, F flag, Group, Previous Hop, Seq, n × (Sender, Next Hop[, RET]) (§4.2) | `odmrp_join_reply{seqno_, count_, pairs_[]}` | Group + Next-hop address blocks (TLV type ext 0/1) | Single next-hop toward source | **Deviates** | Adopt table form. ADR-004 `odmrp-3fq` |
| 9 | JR processing / FG join | If any entry's next hop == self: set FG_FLAG, build own JR from matched entries via routing table, broadcast; broadcast once if no new source info (§3.1, §5.1.6) | Same; `JRTable` tracks forwarded tables | — | "sets FG flag … constructs and forwards its own Join Reply upstream based on matched entries" | Partial | Specify once-per-refresh suppression and source-side termination. `odmrp-vlo` |
| 10 | FG table scope | Keyed by multicast group; forward if FG_FLAG for the group unexpired (§3.6.2, §5.2) | Per group | Per group | Per (source, group) | **Deviates** | Default to group scope, parameterise. ADR-003 `odmrp-1wq` |
| 11 | Soft state / leave | No explicit leave; sources stop sending JQ, receivers stop replying, FG nodes expire (§3.3) | Timer expiry | Timeouts | Same | Conforms | `odmrp-co6` |
| 12 | Timer values | FG timeout must be 3–5× refresh interval; no numeric defaults (§3.4) | UCLA simulations: refresh 3 s, FG lifetime 9 s (E-ODMRP paper) | ROUTING_TIMEOUT 60 s, FG_TIMEOUT 120 s, ACK 30 s | 3 s / 9 s / 9 s | Conforms | Validate `fg_timeout ≥ 2 × refresh`; add jitter params. `odmrp-amm` |
| 13 | Sequence numbers | Per source, "large enough to prevent wraparound ambiguity" (§5.1.1) | int seqno | 16-bit field | Monotonic, wrap-around "handled" | Partial | uint32 + RFC 1982 comparison; shared by JQ and data. ADR-001 `odmrp-e47`, `odmrp-iql` |
| 14 | JR reliability | Passive ACK, R flag, retransmission, "next hop unreachable" fallback (§3.2) | Partially (ACK fields in ns-2 header `valid_ack_`) | ACK_TIMEOUT / PRE_ACK_TIMEOUT | Not mentioned | Silent → Deferred | Roadmap, prerequisite for loss/real networking. `odmrp-bv6` |
| 15 | Mobility prediction / RET | Optional GPS fields, MIN_LET, RET, adaptive refresh (§3.7) | GloMoSim option | — | Out of scope | Deferred | `odmrp-c78` |
| 16 | Passive clustering | Optional efficient flooding (§3.8) | — | — | Not mentioned | Deferred | Not planned (note only) |
| 17 | Unidirectional links | Not supported; bidirectional assumed (§6.2) | Same | ACK-based (ODMRP-ASYM lineage) | Deferred in README | Deferred | `odmrp-ujn` (after `odmrp-bv6`, `odmrp-9bc`) |

## Data plane

| # | Mechanism | Draft | GloMoSim / ns-2 | Repo spec today | Status | Recommendation / bead |
|---|---|---|---|---|---|---|
| 18 | Forwarding rule | Relay iff non-duplicate and FG_FLAG for the group unexpired (§5.2) | Same | Same, keyed (source, group) | Partial (scope) | Group scope per ADR-003. `odmrp-2xj` |
| 19 | Local delivery | Implicit: members consume data | `mcast-sink` check | "receives the message" | Partial | Emit `deliver` trace event; member-not-FG delivers but does not forward. `odmrp-2xj` |
| 20 | Source behaviour | Source transmits; not an FG node itself | Same | Not stated | Silent | State explicitly. `odmrp-2xj` |
| 21 | Loop freedom | Via message cache (§6.2) | Same | Via duplicate cache | Conforms | — |

## Simulation and harness (no draft equivalent; compared with GloMoSim / ns-2 practice)

| # | Topic | Reference practice | Repo spec today | Status | Recommendation / bead |
|---|---|---|---|---|---|
| 22 | Connectivity model | Radio range / propagation model; GloMoSim two-ray etc. | Unit disk, symmetric | Acceptable for prototype | Add `symmetric_links` and `LossModel` hooks. `odmrp-ehv`, `odmrp-5fz` |
| 23 | Event ordering | Discrete-event simulators order by time then insertion | "deterministic" asserted only | Silent | `(time, seq, node)` heap key, seeded RNG. `odmrp-d3t` |
| 24 | Trace | ns-2 trace files; GloMoSim stats | "JSON lines or similar" | Partial | Normative schema v1. ADR-006 `odmrp-0e3`, `odmrp-zdb` |
| 25 | Node interface | n/a (monolithic simulators) | `receive / originate_data / get_state` | Partial | Time-aware, pure-output seam. ADR-005 `odmrp-e7x`, `odmrp-42n` |
| 26 | Wire format | Fixed binary headers (draft §4); RFC 5444 only in ODMRP-ASYM thesis and UB Java | "Full RFC5444 encoding deferred" | Deferred | Keep dataclass fields = draft §4; RFC 5444 codec with real networking. `odmrp-32m` |

## Reading the matrix

- Rows 2, 8 and 10 are the three changes that affect trace comparability with every reference implementation; they are the Phase 0 decision beads.
- Rows 12 and 13 are where the repo is already aligned with the literature; only parameterisation is missing.
- Rows 14, 15, 17 and 26 are the deferrals the README already lists; the matrix adds the dependency order between them (reliability before loss, loss before unidirectional links, both before real networking).
