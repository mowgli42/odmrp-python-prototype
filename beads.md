# Beads Roadmap (Production / Multi-Language Validation)

These items are intentionally not implemented in the prototype. They capture what would be required to turn the learning prototype into a robust test harness or production-grade system.

1. **External node adapter**  
   Implement a process-based adapter so a C++ or Rust binary can act as one or more nodes. Define the exact IPC protocol (length-prefixed JSON or protobuf) for receive/send/state.

2. **Deterministic multi-implementation comparison**  
   Run the same scenario against pure-Python, pure-Rust, and pure-C++ node sets and diff the traces. Fail CI if FG membership or delivery sets diverge.

3. **Real networking mode**  
   Replace the in-process simulator with actual UDP sockets (or a TUN/TAP overlay) so protocol implementations can be tested on real or emulated wireless links.

4. **Mobility models**  
   Add random waypoint, Gauss-Markov, and scripted mobility. Visualize node movement in the frontend.

5. **Packet loss and collision model**  
   Optional probabilistic loss, hidden-terminal collisions, and 802.11-like MAC so performance studies become meaningful.

6. **Unidirectional link detection**  
   Implement the ACK / blacklist logic from the IETF draft so the prototype matches the full specification.

7. **Persistent scenario library**  
   Store scenarios as versioned YAML/JSON fixtures with expected traces. Enable regression testing of any language implementation.

8. **Observability**  
   OpenTelemetry traces, Prometheus metrics (control overhead, delivery ratio, FG size), and structured logging.

9. **Authentication & integrity (optional)**  
   If the harness is ever used for security research, add optional packet authentication.

10. **Distributed deployment**  
    Ability to run the simulator and node processes across multiple machines or containers for larger-scale tests.
