# ODMRP Protocol Capability

## Overview
Implements the core On-Demand Multicast Routing Protocol (ODMRP) as a mesh-based, soft-state multicast protocol. Sources that have data to send periodically flood Join Query messages. Receivers and intermediate nodes that lie on reverse paths become members of the Forwarding Group and forward both control and data traffic. State expires via soft-state timers.

Reference: IETF draft-gerla-manet-odmrp and original UCLA papers.

## ADDED Requirements

### Requirement: Source initiates Join Query when it has data
The system SHALL cause a multicast source node that has pending data for a group and no active forwarding group to originate a Join Query containing the multicast group address, source address, and a monotonically increasing sequence number.

#### Scenario: Source with data originates first Join Query
```gherkin
Given a network of nodes with node S as source and nodes R1, R2 as potential receivers
And node S has a text message to send to multicast group 224.1.1.1
And no forwarding group currently exists for (S, 224.1.1.1)
When the simulation advances time
Then node S originates a Join Query with sequence number 1
And the Join Query is flooded to all currently reachable neighbors
```

#### Scenario: Source periodically refreshes Join Query while data remains
```gherkin
Given a source S that previously originated a Join Query
And S still has data pending for the group
When ROUTE_REFRESH_INTERVAL elapses
Then S originates a new Join Query with an incremented sequence number
```

### Requirement: Nodes perform reverse path learning on Join Query
Upon receiving a non-duplicate Join Query, a node SHALL record the previous hop as the next hop toward the source and rebroadcast the Join Query (with TTL decrement) if TTL remains positive.

#### Scenario: Intermediate node learns reverse path and rebroadcasts
```gherkin
Given node A receives a non-duplicate Join Query originated by S from neighbor B
When node A processes the Join Query
Then node A installs or refreshes a routing entry (source=S, next_hop=B)
And node A rebroadcasts the Join Query to its other neighbors
```

#### Scenario: Duplicate Join Query is suppressed
```gherkin
Given node A has already processed a Join Query from S with sequence number 5
When node A receives another Join Query from S with sequence number 5
Then node A discards the duplicate without rebroadcast or state change
```

### Requirement: Multicast group members originate Join Reply
A node that is a member of the multicast group addressed by a Join Query SHALL originate a Join Reply containing the source, group, sequence number, and next-hop toward the source.

#### Scenario: Receiver originates Join Reply
```gherkin
Given node R is a member of multicast group 224.1.1.1
And R receives a valid Join Query from source S via previous hop P
When R processes the Join Query
Then R originates a Join Reply with next_hop = P
And R broadcasts the Join Reply to its neighbors
```

### Requirement: Forwarding Group membership is established on matching Join Reply
A node that receives a Join Reply whose next-hop address matches one of its own addresses SHALL become (or remain) a member of the Forwarding Group for that (source, group) pair and set its FG flag with an expiration of FG_TIMEOUT.

#### Scenario: Intermediate node joins Forwarding Group
```gherkin
Given node I is not currently in the Forwarding Group for (S, G)
And node I receives a Join Reply for (S, G) with next_hop equal to I's address
When node I processes the Join Reply
Then node I sets its FG flag for (S, G) with expiration = now + FG_TIMEOUT
And node I constructs and forwards its own Join Reply upstream based on matched entries
```

#### Scenario: Forwarding Group soft-state expires
```gherkin
Given node I has an FG flag for (S, G) that expires at time T
When simulation time reaches T + epsilon without a refreshing Join Reply
Then node I clears the FG flag for (S, G)
And node I no longer forwards data for that session
```

### Requirement: Multicast data is forwarded only by Forwarding Group members and non-duplicates
A node SHALL forward a multicast data packet only if it is currently a member of the Forwarding Group for the corresponding (source, group) and the packet is not a duplicate (detected by source + sequence number cache).

#### Scenario: FG node forwards data
```gherkin
Given node I is a current member of the Forwarding Group for (S, G)
And node I receives a non-duplicate data packet originated by S for group G
When node I processes the data packet
Then node I rebroadcasts the data packet to its neighbors
```

#### Scenario: Non-FG node does not forward data
```gherkin
Given node N is not a member of the Forwarding Group for (S, G)
And node N receives a data packet originated by S for group G
When node N processes the data packet
Then node N does not rebroadcast the data packet
```

### Requirement: Sequence numbers are monotonically increasing and used for freshness
Each source SHALL maintain a single sequence number space. A Join Query with sequence number S_new is considered fresher than S_old when S_new > S_old (with wrap-around handling).

#### Scenario: Newer sequence number refreshes state
```gherkin
Given a routing entry for source S with sequence number 10
When a Join Query from S with sequence number 11 is received
Then the routing entry is refreshed with sequence number 11 and new expiration
```

### Requirement: Configurable protocol timers
The system SHALL expose the following timers as configurable parameters (with reasonable prototype defaults):
- ROUTE_REFRESH_INTERVAL (default 3.0 s)
- FG_TIMEOUT (default 9.0 s, typically 3× refresh)
- ROUTE_TIMEOUT (default 9.0 s)

#### Scenario: Timers are respected
```gherkin
Given ROUTE_REFRESH_INTERVAL is set to 2.0 seconds
And a source has continuous data
When 2.0 seconds elapse after a Join Query
Then a new Join Query is originated
```
