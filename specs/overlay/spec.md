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
