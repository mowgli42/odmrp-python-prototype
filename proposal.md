# Proposal: ODMRP Python Prototype with Visualization and Test Harness Potential

## Why
Implement a faithful, observable Python prototype of the On-Demand Multicast Routing Protocol (ODMRP) for mobile ad hoc networks (MANETs). Existing Java implementations exist but lack modern tooling for visualization, messaging/file transfer demos, and clean interfaces for later validation of C++ and Rust implementations.

The prototype serves dual purposes:
1. A learning and demonstration vehicle for ODMRP mechanics (Join Query/Join Reply, forwarding group mesh, soft-state, duplicate detection).
2. A future test harness foundation where the Python simulator can drive and observe external protocol implementations.

## What Changes
- New Python FastAPI backend that simulates a configurable MANET of nodes.
- Each node runs an independent ODMRP state machine.
- Connectivity determined by Euclidean distance + range (with optional mobility later).
- Svelte frontend that visualizes nodes, links, forwarding-group membership, group membership, and live traffic.
- Support for multicast text messaging and simple file transfers.
- OpenSpec + Gherkin that captures validated behavior and leaves clear seams for external (C++/Rust) node implementations.

## Impact
- Enables rapid experimentation with ODMRP parameters (refresh interval, FG timeout, etc.).
- Provides a visual, interactive demo suitable for education and validation.
- Creates a clean boundary (control plane + data plane hooks) so future language implementations can be dropped in and compared against the Python reference.

## Out of Scope for Initial Prototype
- Real radio/PHY modeling (packet loss, collisions beyond simple drop probability).
- Full mobility models (random waypoint can be added later).
- Authentication, encryption, or production-grade reliability.
- Distributed multi-process deployment (single-process sim is sufficient for prototype).

## Success Criteria
- A user can open the Svelte UI, see nodes, join a multicast group from one or more nodes, send a message or small file from a source, and observe the ODMRP mesh form and data traverse the forwarding group.
- Gherkin scenarios cover the core protocol flows and are executable against the running system.
- Architecture leaves clear interfaces for later external node implementations.
