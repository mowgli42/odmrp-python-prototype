# OMS Situational Awareness Distribution Capability

## Overview

Distribute **OMS system status** and **platform position** reports across an ODMRP mesh so every OMS-capable node receives every peer's reports without distribution loops or broadcast storms.

This capability sits **above** core ODMRP (`specs/odmrp/spec.md`) and the IPsec tunnel overlay (`specs/overlay/spec.md`). It does **not** change Join Query / Join Reply / Forwarding Group / duplicate-cache algorithms except where this spec explicitly adds an application originate path for **pure DATA** after the mesh is established.

### Rates (normative interpretation)

| Report | Rate notation | Period | Notes |
| --- | --- | --- | --- |
| OMS system status | 1/20 Hz | 20 s | Soft-state readiness, fuel, weapons, subsystems, task load |
| Platform position | 1/5 Hz | 5 s | Latitude / longitude (and optional altitude / heading later) |

Literal continuous 20 Hz / 5 Hz streams are **out of scope**; they would require aggregation or a different transport.

### Design intent

1. **Dual-rate planes** — Mesh control refreshes on `ROUTE_REFRESH_INTERVAL` (~3 s). Application reports ride **pure DATA** (no Join Query header) once `mesh_established` for the group.
2. **Shared multicast group** — Default group id `oms.sa`. Optional split groups `oms.status` / `oms.position` MAY be enabled by DataPlan configuration.
3. **Every node is source + member** — Each OMS platform originates its own reports and joins the group to receive peers.
4. **Loop freedom** — Wire duplicates suppressed by `(source, seq)` message cache (draft §6.2). Application MUST NOT re-originate a peer's report as a new source sequence.
5. **Storm prevention** — After mesh formation, status/position MUST NOT attach a Join Query (network-wide flood). Control floods remain bounded to the refresh interval.
6. **Edge translation** — On local delivery, adapters MAY emit o-my / OMS bus topics (`uci.platform.status` style) without putting full UCI XML on the mesh.

Related review artifact (non-normative): Cursor canvas *ODMRP OMS Status & Position Distribution Review*.

## ADDED Requirements

### Requirement: Pure DATA originate after mesh is established
The ODMRP node SHALL expose an application originate path that transmits **DATA without a Join Query header** when the source session for the group has `mesh_established = true`. Until the mesh is established, the first originate for that group MAY piggyback a Join Query (existing ADR-002 behaviour) so the FG can form.

#### Scenario: First status report may piggyback Join Query
```gherkin
Given an overlay or radio mesh of OMS nodes that are all members of group "oms.sa"
And node S has not yet established a mesh for "oms.sa"
When node S originates an oms_status report for "oms.sa"
Then the transmitted packet carries a Join Query header
And non-duplicate receivers learn the reverse path and may schedule Join Replies
```

#### Scenario: Subsequent position reports are pure DATA
```gherkin
Given node S has mesh_established true for group "oms.sa"
When node S originates an oms_position report for "oms.sa"
Then the transmitted packet is PacketKind DATA with no Join Query header
And only Forwarding Group members rebroadcast the packet
And non-FG non-members drop with reason not_fg without rebroadcast
```

#### Scenario: Mesh refresh still emits Join Query on interval
```gherkin
Given node S has mesh_established true for group "oms.sa"
And S continues to originate oms_position reports every 5 seconds as pure DATA
When ROUTE_REFRESH_INTERVAL elapses since the last Join Query
Then S originates a Join Query (standalone or piggybacked on queued data)
And the Join Query uses an incremented sequence number in the shared source sequence space
```

### Requirement: Periodic OMS system status at 1/20 Hz
Each OMS node SHALL publish a system status report to group `oms.sa` (or configured status group) once every 20 seconds while the node is an active OMS peer, with configurable phase offset to desynchronize peers.

#### Scenario: Status timer fires every 20 seconds
```gherkin
Given node A is an active OMS peer and a member of group "oms.sa"
And status_period_s is 20
And status_phase_offset_s for A is 2.5
When simulation time reaches 2.5 seconds after A became active
Then A originates an oms_status report
When an additional 20 seconds elapse
Then A originates another oms_status report
And both reports use distinct protocol sequence numbers
```

#### Scenario: Status payload carries OMS system fields
```gherkin
Given node A originates an oms_status report
Then the AppPayload kind is "oms_status"
And the payload includes platform_id, readiness, fuel_percent, weapons_remaining
And the payload includes active_task_count and a generated_at timestamp
And optional subsystems map MAY be present
And the mesh payload is not required to be full UCI XML
```

### Requirement: Periodic platform position at 1/5 Hz
Each OMS node SHALL publish a position report to group `oms.sa` (or configured position group) once every 5 seconds while active, with configurable phase offset.

#### Scenario: Position timer fires every 5 seconds
```gherkin
Given node B is an active OMS peer and a member of group "oms.sa"
And position_period_s is 5
And position_phase_offset_s for B is 0.0
When simulation time advances in 5 second steps while B is active
Then B originates an oms_position report at each step
And each report is pure DATA after mesh_established
```

#### Scenario: Position payload carries coordinates
```gherkin
Given node B originates an oms_position report
Then the AppPayload kind is "oms_position"
And the payload includes platform_id, latitude, longitude, and generated_at
And optional altitude and heading MAY be present
```

### Requirement: All OMS peers receive every peer report without loops
When N OMS nodes are members of `oms.sa` and the Forwarding Group is established, each originated status or position report SHALL be delivered locally to every other member exactly once per protocol sequence (duplicate copies may arrive on the medium but MUST be dropped by the message cache without rebroadcast).

#### Scenario: Multi-source status delivery without re-originate
```gherkin
Given N OMS nodes are members of group "oms.sa" with an established FG
And each node originates its own oms_status on its status timer
When all status timers for one period have fired and the simulation settles
Then each member has delivered N-1 peer oms_status reports for that period
And no node originates a new DATA packet whose payload platform_id is not its own
And duplicate receptions are dropped with reason duplicate
```

#### Scenario: Multi-source position delivery uses shared FG
```gherkin
Given fg_scope is "group"
And nodes 0..7 are members of "oms.sa" with an established FG
When each node originates one oms_position as pure DATA
Then FG members forward each non-duplicate packet
And every member delivers every other node's position for that round
And Join Query flood count for the round equals the number of mesh refreshes not the number of position reports
```

### Requirement: Storm and loop guards are enforced
The system SHALL prevent broadcast storms from application rates and SHALL prevent distribution loops from peer re-injection.

#### Scenario: Pure DATA does not flood non-FG nodes
```gherkin
Given mesh_established is true for source S on group "oms.sa"
And node Z is neither FG nor a group member
When S originates oms_position as pure DATA
Then Z does not rebroadcast the packet
```

#### Scenario: Application refuses to re-originate foreign reports
```gherkin
Given node A delivered an oms_status whose platform_id identifies peer P
When an application on A attempts to originate that same payload as A's report
Then the OMS SA service rejects or rewrites the originate so source identity remains A only for A's platform_id
And foreign platform_id payloads are not accepted for originate
```

#### Scenario: Message cache still suppresses wire loops
```gherkin
Given node I previously cached (source=S, seq=42)
When I receives another DATA packet from S with seq 42
Then I drops the packet as duplicate without rebroadcast or second local deliver
```

### Requirement: Rate and phase configuration
The system SHALL expose configurable `status_period_s` (default 20), `position_period_s` (default 5), and per-node phase offsets. Periods MUST be ≥ the named defaults unless an explicit test override is set. Continuous rates above 1 Hz for either report type SHALL be rejected in production configuration.

#### Scenario: Reject unsafe production rates
```gherkin
Given a production OMS SA configuration
When status_period_s is set below 1.0 or position_period_s is set below 1.0
Then configuration validation fails
And the SA publisher does not start
```

### Requirement: Freshness and stale marking at consumers
A receiving OMS node SHALL track the latest report per `platform_id` and mark a peer stale when age exceeds twice the configured period for that report type (status stale after 40 s by default; position stale after 10 s by default).

#### Scenario: Peer marked stale after 2× period
```gherkin
Given node A last delivered an oms_position for platform P at time T
And position_period_s is 5
When simulation time reaches T + 10 + epsilon without a newer report for P
Then A's OMS SA consumer marks platform P position as stale
```

#### Scenario: Newer generated_at wins
```gherkin
Given node A holds an oms_status for platform P with generated_at T1
When A delivers another oms_status for P with generated_at T2 where T2 > T1
Then A replaces the stored status with the newer report
When a late report arrives with generated_at T0 where T0 < T2
Then A retains the T2 report
```

### Requirement: Overlay tunnel mode remains the preferred OMS interconnect
When overlay mode is `tunnel`, OMS SA DATA SHALL use neighbor-send unicast over address-book peers. FG-scoped forwarding and duplicate cache behaviour remain as in `specs/overlay/spec.md`. Gateway DataPlan product announcements (ttl=1) remain separate from periodic SA DATA.

#### Scenario: Tunnel mode SA uses unicast-over-neighbors
```gherkin
Given the overlay-mesh scenario is loaded in tunnel mode with OMS SA enabled
When node 0 originates oms_position as pure DATA after mesh_established
Then transmissions use mode unicast_over_neighbors
And FG members forward only to their active tunnel peers
And announcement-style ttl=1 product packets are not used for oms_position
```

### Requirement: Metrics for SA distribution health
The system SHALL emit or expose counters suitable for detecting storms and measuring SA quality: offer load, TX amplification, duplicate drop rate, not_fg drop rate, delivery ratio, freshness age, control overhead (JQ+JR bytes / DATA bytes), and message cache occupancy.

#### Scenario: Trace supports amplification accounting
```gherkin
Given an OMS SA run with N sources for one position period
When the trace is summarized
Then the number of Join Query floods is counted separately from pure DATA originates
And duplicate and not_fg drops are counted
And per-member delivery counts for oms_position are available
```

## MODIFIED Requirements

### Requirement: AppPayload kinds include OMS SA types
`AppPayload.kind` SHALL accept `oms_status` and `oms_position` in addition to existing `text` and `chunk` (and overlay product kinds where already defined).

#### Scenario: Inbox records OMS kinds
```gherkin
Given node R is a member of "oms.sa"
When R delivers an oms_status from peer S
Then R's inbox (or SA consumer store) records app_kind "oms_status"
And platform_id is available to the consumer without re-parsing opaque bytes only
```

## Out of Scope

- Literal 20 Hz status or 5 Hz continuous kinematic streams
- Replacing o-my Redis/ASB fusion; this spec only covers mesh distribution + optional edge emit
- Join Reply reliability, loss models, and unidirectional links (existing roadmap beads)
- Native UCI 2.5 XSD validation on the mesh wire
