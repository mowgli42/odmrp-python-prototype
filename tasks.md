# Implementation Tasks

## Phase 1 – Simulation Core
- [ ] Define Packet, Node, Topology data classes
- [ ] Implement distance-based neighbor computation
- [ ] Implement discrete-event simulation clock and packet delivery
- [ ] Expose REST endpoints: create network, get state, step time

## Phase 2 – ODMRP Reference Implementation
- [ ] Implement Join Query origination and flooding with reverse-path learning
- [ ] Implement Join Reply origination and FG membership
- [ ] Implement soft-state timers (FG_TIMEOUT, ROUTE_TIMEOUT)
- [ ] Implement duplicate detection cache
- [ ] Implement data packet forwarding by FG members only
- [ ] Add sequence number management

## Phase 3 – Messaging & File Transfer
- [ ] Add text message injection API
- [ ] Add file chunking, transfer-id, and reassembly
- [ ] Add delivery status reporting

## Phase 4 – FastAPI + WebSocket
- [ ] WebSocket endpoint that pushes topology + state + packet events
- [ ] REST endpoints for join/leave group, send message, upload file
- [ ] Pause / resume / step controls

## Phase 5 – Svelte Frontend
- [ ] Render nodes and links
- [ ] Highlight FG members and group members
- [ ] Animate or log packet events
- [ ] Controls: add node, move node, join group, send message, upload file
- [ ] Connect via WebSocket

## Phase 6 – Test Harness Hooks & Gherkin
- [x] Define ODMRPNode protocol/interface
- [x] Emit structured JSON-lines trace
- [x] Implement Gherkin scenarios as pytest-bdd or behave tests against the running API
- [x] Document how an external node would implement the interface

## Phase 6c – Minimal Java ODMRPNode reference (differential testing)
Spec: `specs/java-reference/spec.md`. Beads epic `odmrp-7o1` (parent `odmrp-azt`). IDs: `docs/beads/java-ids.json`.
- [ ] Scaffold Java project (jar) implementing ADR-005 ops over NDJSON stdio — `odmrp-a9f`
- [ ] Port packet/state JSON models to match Python `to_dict`/`from_dict` — `odmrp-6p1`
- [ ] Implement JQ flood, reverse-path learning, JR table / FG soft-state, data forward — `odmrp-2i1`
- [ ] Implement source originate + refresh via `advance` / `next_timer` — `odmrp-gwg`
- [ ] Python `ExternalProcessNode` launches the Java jar (`odmrp-dn0` → `odmrp-nud`)
- [ ] All-Java `basic-mesh` matches Python FG `{1,3}` and delivery `{3,5}` — `odmrp-cko`
- [ ] Mixed Python/Java mesh delivers; compact trace diff in CI precursor (`odmrp-cko` → `odmrp-izv`) — `odmrp-awl`

## Phase 7 – Demo Closure
- [x] DEMO.md with exact run commands
- [x] Sample scenario that forms a mesh and delivers a message
- [x] Screenshot walkthrough placeholders
- [x] Beads roadmap for production / multi-language validation
