# Test Harness Capability

## Overview

The node seam is the ADR-005 `ODMRPNode` interface (`configure`, `set_membership`, `originate`, `receive`, `advance`, `next_timer`, `get_state`). See `design.md` and `docs/architecture/03-data-model-and-interfaces.md` §3.3.

The prototype is structured so that the Python ODMRP implementation can later be replaced (node-by-node or entirely) by external implementations. The **first external language is a minimal Java reference** that implements the same `ODMRPNode` operations for differential testing (`specs/java-reference/spec.md`). C++ and Rust remain roadmap targets. The simulator owns topology, timing, and packet delivery; external nodes communicate via the NDJSON stdio contract in `docs/external-node-contract.md`.

## ADDED Requirements

### Requirement: Protocol logic is isolated behind an interface
Each node’s ODMRP state machine SHALL be accessible through a narrow interface (receive, originate, get_state, etc.) so that an alternative implementation can be substituted.

#### Scenario: External node can be plugged in
```gherkin
Given the simulator is configured to use an external ODMRP implementation for node 4
When the simulator delivers a Join Query to node 4
Then the external implementation is invoked and may return zero or more packets to transmit
```

#### Scenario: Java reference can be plugged in for one node
```gherkin
Given the simulator is configured to use the Java ODMRP reference for node 4
When the simulator delivers a Join Query to node 4
Then the Java process handles receive and may return zero or more packets to transmit
```

### Requirement: Trace of all control and data events is available
The system SHALL emit a structured trace (JSON lines or similar) of every Join Query, Join Reply, data packet, and state change so that external implementations can be validated against the Python reference.

#### Scenario: Trace contains Join Query and resulting FG set
```gherkin
Given a scenario that establishes a forwarding group
When the scenario completes
Then the trace contains the Join Query, all Join Replies, and the final set of FG nodes
```

### Requirement: Deterministic replay is possible
Given the same initial topology, node positions, and sequence of injected messages, the simulation SHALL produce identical traces (except for intentionally randomized jitter).

#### Scenario: Two runs produce identical FG membership
```gherkin
Given a fixed seed and fixed topology
When the same message injection sequence is executed twice
Then the set of nodes that become FG members is identical in both runs
```
