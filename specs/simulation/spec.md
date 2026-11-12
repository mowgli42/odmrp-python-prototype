# Simulation Capability

## Overview
A single-process discrete-event simulation of a MANET in which nodes have 2D positions, a configurable radio range, and ODMRP instances. Connectivity is determined by distance ≤ range. The simulator advances time, delivers packets only to currently reachable neighbors, and exposes state for visualization and testing.

## ADDED Requirements

### Requirement: Nodes have positions and radio range
The system SHALL allow creation of nodes with unique IDs, 2D coordinates, and a shared or per-node radio range.

#### Scenario: Two nodes are neighbors when within range
```gherkin
Given node A at (0, 0) and node B at (50, 0)
And radio range is 100
When connectivity is computed
Then A and B are neighbors
```

#### Scenario: Nodes outside range are not neighbors
```gherkin
Given node A at (0, 0) and node B at (150, 0)
And radio range is 100
When connectivity is computed
Then A and B are not neighbors
```

### Requirement: Packet delivery respects current topology
When a node transmits a packet (broadcast), the simulator SHALL deliver a copy only to nodes that are currently neighbors.

#### Scenario: Broadcast reaches only neighbors
```gherkin
Given nodes A, B, C where A-B are neighbors and A-C are not
When A broadcasts a Join Query
Then B receives the Join Query
And C does not receive the Join Query
```

### Requirement: Simulation time can be advanced
The system SHALL support both continuous real-time mode and stepped discrete-event mode so that tests can control exactly when timers fire.

#### Scenario: Step time causes timer expiration
```gherkin
Given an FG flag set to expire in 5 seconds
When the simulation is advanced by 5.1 seconds
Then the FG flag has expired
```

### Requirement: Scenario load schedules script without advancing time
Loading a scenario SHALL create nodes, overlay, and data plan, schedule scripted operations on the discrete-event scheduler, and leave the engine paused at t=0 with no scripted events executed. Play (or step) SHALL advance time at the configured speed and execute script ops when simulation time reaches their `at` values. Reset SHALL pause, clear engine state, reload the current scenario at t=0, and leave the UI ready to play again.

#### Scenario: Load leaves simulation paused at t=0 ready to play
```gherkin
Given the basic-mesh scenario is loaded for playback
Then simulation time is 0
And the simulation mode is "paused"
And no scripted join or text events have executed yet
And scripted operations are scheduled on the engine
```

#### Scenario: Play at 1x executes scripted events progressively
```gherkin
Given the basic-mesh scenario is loaded for playback
When the simulation advances at 1x through the script horizon plus settle
Then scripted joins and the text payload have executed
And the forwarding group for "demo" is nodes 1 and 3
And nodes 3 and 5 have delivered "ODMRP works"
And simulation time is greater than 1
```

#### Scenario: Reset restores clean initial state at t=0
```gherkin
Given the basic-mesh scenario is loaded for playback
And the simulation advances at 1x through the script horizon plus settle
When the scenario is reset for playback
Then simulation time is 0
And the simulation mode is "paused"
And no scripted join or text events have executed yet
And scripted operations are scheduled on the engine
And the simulation is ready to play again
```

### Requirement: Node state is observable
The system SHALL expose, for every node, its current routing table, forwarding group memberships, group memberships, and recent packet log.

#### Scenario: Visualization can query node state
```gherkin
Given a running simulation
When the frontend requests the state of node 3
Then the response includes node 3's position, FG flags, and group memberships
```
