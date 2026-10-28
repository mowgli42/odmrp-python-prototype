# IPsec Tunnel Overlay Capability

## Overview

Extend ODMRP to run over an **IPsec tunnel overlay** with no native IPv4 multicast/broadcast. Nodes exchange control and data only via an explicit **neighbor-send** primitive whose peer set comes from an address book (logical tunnels) and/or unit-disk radio topology. Super nodes push neighbor recommendations, membership, and OMS-aligned data-plan fragments; ordinary nodes prune tunnels under policy.

Inspired by Commlink-Directory contacts/capabilities and Commlink-Schedule assets; products use open-arsenal OMS-style ProductMetadata + ProductLocation.

## ADDED Requirements

### Requirement: Address book describes nodes and logical neighbors
The system SHALL maintain an address book where every node has capability flags (including `is_super_node`), a tunnel endpoint, and a soft-state neighbor set `(peer_id, tunnel_endpoint, status, priority, reason, expires_at)`. Neighbor relations SHALL be importable and exportable as JSON.

#### Scenario: Load overlay address book
```gherkin
Given the overlay address book fixture is available
When the address book is loaded
Then node 0 is marked is_super_node
And node 0 can_stage_products is true
And node 1 has at least one neighbor relation with a tunnel_endpoint
```

#### Scenario: Export and re-import neighbor relations
```gherkin
Given a loaded address book with logical neighbors
When neighbor relations are exported
And the edges are re-imported into a fresh book
Then the fresh book contains the same from→to peer pairs
```

### Requirement: Neighbor-send uses logical peers for tunnel mode
When overlay mode is `tunnel`, the medium SHALL deliver packets only to active address-book neighbors (not RF unit-disk flood). FG-scoped data forwarding continues to use the same neighbor-send primitive.

#### Scenario: Tunnel mode does not use RF-only links
```gherkin
Given the overlay-mesh scenario is loaded in tunnel mode
And the address book defines logical neighbors for each node
When source 0 originates a Join Query for group "demo"
Then transmissions list only address-book neighbors of the sender
And receivers 3 and 5 eventually receive the text payload
```

### Requirement: NeighborSender unicasts over each current tunnel
The system SHALL expose an explicit `NeighborSender` (or equivalent) whose `neighbor_send` primitive loops the current neighbor set and schedules one unicast delivery per active tunnel peer. ODMRP Join Query / Join Reply / data forwarding SHALL call only that primitive. Trace `tx` events SHALL record `mode=unicast_over_neighbors` and a per-peer `unicasts` list (peer_id + tunnel_endpoint). There SHALL be no reliance on native IPv4 multicast or link-layer broadcast.

#### Scenario: Tunnel mode TX is unicast over address-book peers only
```gherkin
Given the overlay-mesh scenario is loaded in tunnel mode
When the simulation settles
Then every transmission uses mode unicast_over_neighbors
And source 0 unicasts only to its address-book tunnel peers
And no transmission lists a peer outside the sender's active neighbor set
```

#### Scenario: Sparse FG mesh delivers data without IP multicast
```gherkin
Given the overlay-mesh scenario is loaded in tunnel mode
When the simulation settles
Then the neighbor graph is not a full mesh
And receivers 3 and 5 have delivered the overlay text payload
And non-FG node 4 does not forward DATA for group "demo"
And FG members for "demo" are among the relay nodes
```

### Requirement: OMS-aligned data plan maps messages and products
The system SHALL load a data plan that maps short text messages and file products onto ODMRP data messaging, with ProductMetadata and ProductLocation (uri, mime_type, expires_at, staging_node, tunnel_endpoint) resolved against the address book.

#### Scenario: Data plan includes text and staged file product
```gherkin
Given the overlay data-plan fixture
When the data plan is loaded and endpoints are resolved
Then there is a data_text message from node 0
And there is a data_product message referencing product prod-isr-001
And the product location staging_node is a super node with a tunnel_endpoint
```

### Requirement: Super nodes push recommendations that prune neighbors
A super node SHALL push neighbor recommendations, membership updates, and optional data-plan fragments. Ordinary nodes SHALL apply recommendations under policy knobs `max_neighbors`, preference, and soft-state TTL, pruning excess tunnels.

#### Scenario: Ordinary node prunes to max_neighbors after super-node push
```gherkin
Given an address book where node 1 has more than 3 neighbors
And a super-node push from node 0 with max_neighbors 3 for node 1
When the push is applied
Then node 1 has at most 3 active neighbors
And retained peers prefer the super node when prefer_super_peers is true
```

### Requirement: Visualization shows logical links and super nodes
The UI SHALL continue to show RF topology and SHALL optionally draw logical neighbor links and mark super nodes. Recommendation flow MAY be shown as transient overlay events.

#### Scenario: Snapshot exposes overlay visual fields
```gherkin
Given the overlay-mesh scenario is loaded
When a network snapshot is taken
Then overlay.super_nodes contains 0
And overlay.logical_links is a non-empty list of undirected pairs
And overlay.mode is "tunnel"
```

### Requirement: Gateway DataPlan drives product dissemination
The gateway (super-node) SHALL maintain an active DataPlan that maps `(product_type, optional source_node)` to destination node IDs. When a product becomes available, the gateway SHALL evaluate the plan, build OMS ProductMetadata and ProductLocation announcements, and transmit them via destination-filtered neighbor-send (`neighbor_send_to`) over currently active tunnels only (`destinations ∩ connected`). ODMRP Join Query / Join Reply / FG / duplicate-cache SHALL remain unchanged; announcement packets use ttl=1 so FG members do not rebroadcast them. Multi-hop group DATA continues to use the classic FG mesh.

#### Scenario: DataPlan evaluation announces only to named destinations
```gherkin
Given the overlay-mesh scenario is loaded with a gateway DataPlan
When product prod-isr-001 of type imagery becomes available on the gateway
Then the gateway announces product_meta and product_loc
And announcement unicasts go only to DataPlan destinations that are connected
And no announcement unicast targets a node outside the destination set
```

### Requirement: Gateway monitor updates DataPlan on connectivity change
A gateway-local process SHALL track currently connected tunnel peers, detect connect/disconnect, prune unreachable destinations from the active DataPlan on disconnect, and expose status (connected set, dissemination rules, recent monitor events) for the API/UI. Ordinary ODMRP nodes SHALL not require changes for this monitor.

#### Scenario: Connectivity loss updates DataPlan destinations
```gherkin
Given the overlay-mesh scenario is loaded with a gateway DataPlan
And the gateway DataPlan lists destinations 1 and 2 for imagery
When tunnel peer 2 disconnects from the gateway
And the gateway monitor ticks
Then destination 2 is removed from the active DataPlan
And a subsequent imagery product is announced only to destination 1
```

### Requirement: JREAP-A SA feed interest and ProductLocation mint
Any node SHALL be able to express interest in product type `Link16-JREAP-A` without creating tunnels or changing FG membership. The gateway SHALL evaluate the active DataPlan; only authorized destinations receive a minted ProductMetadata + ProductLocation whose URI points at a thin (mock) JREAP-A endpoint. Announcements use neighbor-send and may be forwarded by current FG members. ODMRP JQ/JR/FG/dup-cache logic SHALL remain unchanged.

#### Scenario: Interest leads to ProductLocation and mock SA stream
```gherkin
Given the overlay-mesh scenario has settled with FG formed
When node 3 expresses interest in Link16-JREAP-A
Then the gateway authorizes node 3 and mints a ProductLocation
And the ProductLocation URI points at the thin JREAP endpoint
When the gateway pumps the SA feed
Then node 3 has consumed SA bytes
And only the gateway opened the JREAP endpoint connection
```

### Requirement: Consume-while-forward without a second JREAP connection
When SA/JREAP bytes arrive on an upstream tunnel, a node SHALL offer them to a local consumer if it is interested or is an FG forwarder for that product, then relay the same bytes downstream via neighbor-send if forwarding. Each node SHALL keep a per-product record `(upstreamTunnel, consuming, forwarding, downstreamTunnels)`. A node SHALL never open a second connection to the ProductLocation endpoint for a product it is already receiving or forwarding. Pruned destinations SHALL lose leaf subscriptions; relay paths for remaining nodes remain.

#### Scenario: Forwarder consumes without a second connection
```gherkin
Given the overlay-mesh scenario has settled with FG formed
And node 3 has an authorized Link16-JREAP-A subscription
When the gateway pumps the SA feed
Then FG forwarder node 1 consumes the stream locally
And node 1 did not open a second JREAP endpoint connection
And node 1 forwarded SA chunks downstream toward node 3
```
