# Beads Roadmap (Production / Multi-Language Validation)

These items are intentionally not implemented in the prototype. They capture what would be required to turn the learning prototype into a robust test harness or production-grade system.

Each item is now tracked as a bead under the roadmap epic `odmrp-azt` (`bd list --parent odmrp-azt`).
The bead IDs below are the source of truth for status and dependencies; this file is the narrative.
Two items (11 and 12) were added by the architecture review (`docs/review/architecture-review.md`).

1. **External node adapter** — `odmrp-dn0`  
   Implement a process-based adapter so a C++ or Rust binary can act as one or more nodes. Define the exact IPC protocol (length-prefixed JSON or protobuf) for receive/send/state.

2. **Deterministic multi-implementation comparison** — `odmrp-izv`  
   Run the same scenario against pure-Python, pure-Rust, and pure-C++ node sets and diff the traces. Fail CI if FG membership or delivery sets diverge.

3. **Real networking mode** — `odmrp-32m`  
   Replace the in-process simulator with actual UDP sockets (or a TUN/TAP overlay) so protocol implementations can be tested on real or emulated wireless links. Includes the RFC 5444 codec (Join Query / Join Reply as RFC 5444 messages) that the in-process prototype deliberately skips.

4. **Mobility models** — `odmrp-m84`  
   Add random waypoint, Gauss-Markov, and scripted mobility. Visualize node movement in the frontend.

5. **Packet loss and collision model** — `odmrp-9bc`  
   Optional probabilistic loss, hidden-terminal collisions, and 802.11-like MAC so performance studies become meaningful.

6. **Unidirectional link detection** — `odmrp-ujn`  
   Implement the ACK / blacklist logic from the IETF draft so the prototype matches the full specification.

7. **Persistent scenario library** — `odmrp-dml`  
   Store scenarios as versioned YAML/JSON fixtures with expected traces. Enable regression testing of any language implementation.

8. **Observability** — `odmrp-5z4`  
   OpenTelemetry traces, Prometheus metrics (control overhead, delivery ratio, FG size), and structured logging.

9. **Authentication & integrity (optional)** — `odmrp-0q4`  
   If the harness is ever used for security research, add optional packet authentication.

10. **Distributed deployment** — `odmrp-faw`  
    Ability to run the simulator and node processes across multiple machines or containers for larger-scale tests.

11. **Join Reply reliability** — `odmrp-bv6`  
    Passive acknowledgement of forwarded Join Replies, the R (retransmission) flag, bounded retransmission, and route invalidation after repeated failure, as described in the IETF draft. The prototype relies on the periodic refresh alone.

12. **Mobility prediction / adaptive refresh** — `odmrp-c78`  
    Optional GPS/velocity fields in the Join Query, route expiration time (RET) prediction, and E-ODMRP-style adaptive refresh intervals. Builds on the soft-state expiry logic (`odmrp-co6`) and is only meaningful once the mobility models (item 4) exist.
