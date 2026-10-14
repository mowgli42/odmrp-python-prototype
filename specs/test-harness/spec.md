# Test Harness Capability

## Overview
The prototype is structured so that the Python ODMRP implementation can later be replaced (node-by-node or entirely) by external implementations written in C++ or Rust. The simulator owns topology, timing, and packet delivery; external nodes communicate via a well-defined control and data interface.

## ADDED Requirements

### Requirement: Protocol logic is isolated behind an interface
Each node’s ODMRP state machine SHALL be accessible through a narrow interface (process_packet, originate_join_query, get_state, etc.) so that an alternative implementation can be substituted.

#### Scenario: External node can be plugged in
```gherkin
Given the simulator is configured to use an external ODMRP implementation for node 4
When the simulator delivers a Join Query to node 4
Then the external implementation is invoked and may return zero or more packets to transmit
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
