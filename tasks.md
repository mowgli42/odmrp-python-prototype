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
- [ ] Define ODMRPNode protocol/interface
- [ ] Emit structured JSON-lines trace
- [ ] Implement Gherkin scenarios as pytest-bdd or behave tests against the running API
- [ ] Document how an external C++/Rust node would implement the interface

## Phase 7 – Demo Closure
- [ ] DEMO.md with exact run commands
- [ ] Sample scenario that forms a mesh and delivers a message
- [ ] Screenshot walkthrough placeholders
- [ ] Beads roadmap for production / multi-language validation
