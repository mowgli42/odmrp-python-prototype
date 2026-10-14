# Java ODMRP Reference Capability

## Overview

A **minimal Java reference** implements the same ADR-005 `ODMRPNode` contract as the Python node (`configure`, `set_membership`, `originate`, `receive`, `advance`, `next_timer`, `get_state`) so the simulator can run differential tests: same scenario, same seed, compare FG sets, delivery sets, and compact traces.

This is the first-party cross-language baseline for the harness. It is intentionally small (Join Query flood + reverse-path learning + Join Reply FG mesh + soft-state + FG-scoped data forward). It does **not** require RFC 5444 for the first cut; packets use the same JSON `Packet.to_dict()` schema as Python over the NDJSON stdio IPC in `docs/external-node-contract.md`. RFC 5444 remains a later roadmap item (`odmrp-32m`) once behaviour matches.

Protocol behaviour MUST match `specs/odmrp/spec.md` and the Python reference defaults in `ProtocolParams` (3 s refresh, 9 s FG/route timeout, FG keyed by group, JR table form, piggybacked JQ).

White-paper / draft references for expected behaviour: Lee, Gerla, Chiang, *On-Demand Multicast Routing Protocol*, WCNC 1999; Lee, Su, Gerla, MONET 2002; draft-ietf-manet-odmrp-02/-04; E-ODMRP timer defaults (Oh, Park, Gerla, 2008).

## ADDED Requirements

### Requirement: Java node implements the ODMRPNode operations
A Java process SHALL expose the seven ADR-005 operations over NDJSON-on-stdio (or an equivalent in-process JNI/bridge used only in tests), returning packets as JSON objects compatible with Python `Packet.to_dict()` / `from_dict()`.

#### Scenario: Java node answers configure and get_state
```gherkin
Given a Java ODMRP node process is started
When the host sends configure with node_id 4, default ProtocolParams, and rng_seed 42
And the host sends get_state
Then the reply is ok
And the state id is 4
And members, routes, and forwarding_groups are empty
```

#### Scenario: Java node receive returns packets to transmit
```gherkin
Given a configured Java node that is a member of group "demo"
When the host delivers a non-duplicate Join Query for group "demo" from previous_hop 1
Then the Java node returns a Join Reply table with an entry for the query source
And may return a rebroadcast Join Query with decremented ttl
```

### Requirement: Java protocol matches Python on core ODMRP flows
For identical `ProtocolParams` with `jq_jitter = 0` and `jr_delay = 0`, a Java node SHALL produce the same control-plane outcomes as `PythonODMRPNode` for Join Query processing, reverse-path install, Join Reply / FG membership, soft-state expiry, and FG-scoped data forwarding as specified in `specs/odmrp/spec.md`.

#### Scenario: Java intermediate learns reverse path and rebroadcasts
```gherkin
Given a Java node A that has not seen source S sequence 1
When A receives a Join Query from S via previous hop B
Then A installs route[S].next_hop = B
And A returns a rebroadcast Join Query with previous_hop = A and ttl decremented
```

#### Scenario: Java receiver originates Join Reply table
```gherkin
Given a Java node R that is a member of group "demo"
When R receives a valid Join Query from source S via previous hop P
Then R schedules or returns a Join Reply whose entries include (sender=S, next_hop=P)
```

#### Scenario: Java intermediate joins Forwarding Group on matching Join Reply
```gherkin
Given a Java node I that is not in the Forwarding Group for group G
When I receives a Join Reply for G with an entry whose next_hop equals I
Then I sets FG for G with expiration = now + FG_TIMEOUT
And I returns its own Join Reply upstream from matched entries when not suppressed
```

#### Scenario: Java FG node forwards non-duplicate data
```gherkin
Given a Java node I that is an FG member for group G
When I receives a non-duplicate data packet for G
Then I returns a rebroadcast of that data packet
```

#### Scenario: Java non-FG node does not forward data
```gherkin
Given a Java node N that is not an FG member for group G
And N is not a member of G
When N receives a data packet for G
Then N returns no transmit packets for that data
```

### Requirement: Soft-state timers are driven by advance and next_timer
Java nodes SHALL arm FG, route, Join Reply delay, and source refresh timers and fire them only through `advance(now)`, reporting the next due time via `next_timer()`.

#### Scenario: Java FG soft-state expires
```gherkin
Given a Java node I with FG for group G expiring at time T
When the host calls advance with now = T + epsilon and no refreshing Join Reply arrived
Then I clears FG for G
And I no longer returns forwards for data of group G
```

#### Scenario: Java source refreshes Join Query on interval
```gherkin
Given a Java source that originated for group "demo" with ROUTE_REFRESH_INTERVAL = 3.0
And the session is still active
When the host advances to the refresh deadline
Then the Java node returns a Join Query with an incremented sequence number
```

### Requirement: Differential testing against the Python reference
The harness SHALL run the same scenario with (a) all-Python nodes and (b) all-Java nodes (and optionally a mixed assignment) and compare FG membership, delivery sets, and a compact trace projection.

#### Scenario: All-Java basic-mesh matches Python FG and delivery
```gherkin
Given scenarios/basic-mesh.yaml with jq_jitter 0 and jr_delay 0
When the scenario is executed with every node backed by the Java reference
And the same scenario is executed with every node backed by PythonODMRPNode
Then both runs report FG nodes {1, 3}
And both runs deliver the text payload to nodes {3, 5}
```

#### Scenario: Mixed Python and Java mesh still delivers
```gherkin
Given scenarios/basic-mesh.yaml with jq_jitter 0 and jr_delay 0
And nodes 0, 2, 4 use Python and nodes 1, 3, 5 use Java
When the scenario completes
Then the text payload is delivered to nodes {3, 5}
And every FG node is in {1, 2, 3, 4}
```

#### Scenario: Compact traces match for all-Java vs all-Python
```gherkin
Given a fixed seed and scenarios/basic-mesh.yaml with jitter disabled
When all-Java and all-Python runs complete
Then the sequences of (kind, node, normalized payload) for kinds tx, state.fg, and deliver are identical after stripping packet ids
```

### Requirement: Java packaging is runnable by the host
The Java reference SHALL be buildable and launchable as a single process per node (jar or `java -cp … Main`) suitable for `ExternalProcessNode` and later a Docker appliance.

#### Scenario: Host spawns Java node by configured command
```gherkin
Given the simulator node impl is "java" with command ["java", "-jar", "odmrp-java-node.jar"]
When the simulation creates node 4
Then a Java process is started and successfully answers configure
```
