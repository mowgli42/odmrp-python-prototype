# Visualization Capability

## Overview
A Svelte frontend that displays the simulated network as an interactive graph, shows protocol state (FG membership, group membership), and animates control and data traffic.

## ADDED Requirements

### Requirement: Nodes and links are rendered
The frontend SHALL render each node at its simulated position and draw edges between currently neighboring nodes.

#### Scenario: Graph reflects current topology
```gherkin
Given the simulation has 5 nodes with known positions and ranges
When the frontend loads the network view
Then 5 nodes are visible at correct relative positions
And edges exist only between nodes within radio range
```

### Requirement: Forwarding Group membership is visually distinguished
Nodes that currently belong to the Forwarding Group for the selected (source, group) SHALL be visually highlighted (e.g. different color or badge).

#### Scenario: FG nodes are highlighted after mesh forms
```gherkin
Given a source has sent a Join Query and receivers have replied
When the frontend refreshes state
Then nodes that set FG flags are rendered with the FG highlight
```

### Requirement: Live traffic can be observed
The frontend SHALL animate or log recent Join Query, Join Reply, and data packets so a user can see the mesh form and data flow.

#### Scenario: Packet animation appears
```gherkin
Given a user sends a message from the UI
When the message is transmitted
Then the frontend shows a visual indication of the packet traveling along the mesh
```

### Requirement: User can control the simulation from the UI
The frontend SHALL allow a user to:
- Add/remove nodes or move them
- Select a source and join/leave groups from nodes
- Inject a text message or upload a small file
- Pause/resume or step the simulation

#### Scenario: User joins a group from the UI
```gherkin
Given the frontend is connected to a running simulation
When the user selects node R1 and clicks "Join group chat"
Then node R1 becomes a member of group "chat"
And subsequent messages to "chat" are eligible for delivery to R1
```
