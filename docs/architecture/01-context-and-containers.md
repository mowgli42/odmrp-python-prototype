# Architecture 1 — Context and containers

C4 levels 1 and 2 for the prototype. Diagrams are Mermaid; GitHub renders them inline.

## 1.1 System context

```mermaid
C4Context
  title ODMRP Python prototype — system context
  Person(user, "Learner / protocol engineer", "Builds topologies, joins groups, sends messages, watches the mesh form")
  Person(tester, "CI / harness author", "Runs Gherkin scenarios and determinism checks")
  System(proto, "ODMRP prototype", "Single-process MANET simulator with a Python ODMRP reference, REST + WebSocket API, Svelte UI")
  System_Ext(ext, "External ODMRP node (C++ / Rust)", "Future: speaks the NodeHost IPC contract over stdio")
  System_Ext(ci, "CI runner", "pytest, pytest-bdd, Playwright")
  Rel(user, proto, "Uses", "browser")
  Rel(tester, proto, "Drives", "REST / trace files")
  Rel(proto, ext, "Hosts as node N", "NDJSON over stdio (roadmap)")
  Rel(ci, proto, "Runs scenarios against", "HTTP / in-process")
```

## 1.2 Containers

```mermaid
C4Container
  title ODMRP prototype — containers
  Person(user, "User")
  Container_Boundary(fe, "frontend/ (Vite + Svelte 5)") {
    Container(ui, "Svelte SPA", "TypeScript, SVG", "Network view, node inspector, messaging panel, trace timeline")
  }
  Container_Boundary(be, "backend/ (Python 3.12, FastAPI, uvicorn)") {
    Container(api, "API layer", "FastAPI routers", "REST mutations/queries, WebSocket feed, OpenAPI")
    Container(svc, "Services", "Python", "MessagingService, ScenarioLoader, SimControls, DeliveryReports")
    Container(sim, "Simulation core", "Python", "SimulationEngine, Topology, Medium, TimerService, NodeHost×N")
    Container(proto, "ODMRP reference", "Python", "PythonODMRPNode behind the ODMRPNode Protocol")
    Container(bus, "EventBus + trace", "Python", "JSONL writer, ring buffer, WS broadcaster")
  }
  ContainerDb(files, "Local files", "filesystem", "scenarios/*.yaml, traces/*.jsonl, reassembled files")
  System_Ext(extnode, "External node process", "C++ / Rust (roadmap)")
  Rel(user, ui, "Uses", "HTTPS")
  Rel(ui, api, "REST", "JSON")
  Rel(ui, api, "Subscribe", "WebSocket")
  Rel(api, svc, "Calls")
  Rel(svc, sim, "Schedules / queries")
  Rel(sim, proto, "receive / advance / originate")
  Rel(sim, extnode, "same calls", "NDJSON stdio")
  Rel(sim, bus, "publish events")
  Rel(bus, api, "events → WS frames")
  Rel(bus, files, "append trace")
  Rel(svc, files, "load scenarios, store files")
```

### Container responsibilities

| Container | Owns | Must not |
|---|---|---|
| Svelte SPA | Rendering, local UI state (selection, filters), optimistic drag | Compute protocol state or infer FG membership; everything comes from the server |
| API layer | HTTP/WS framing, validation (pydantic), OpenAPI | Hold simulation state; it only reaches the `SimulationSession` |
| Services | Use-case orchestration: send message, load scenario, step/run | Touch the scheduler directly |
| Simulation core | Time, topology, delivery, timers, node hosting, tracing of every tx/rx | Know ODMRP semantics |
| ODMRP reference | Protocol tables and rules per draft §3.6, §5.1, §5.2 | Read the clock or RNG directly (both arrive via arguments / seeded sub-generator) |
| EventBus + trace | Fan-out of immutable events; durable JSONL | Mutate state |

## 1.3 Deployment (development)

```mermaid
flowchart LR
  subgraph dev["Developer machine"]
    direction LR
    V["vite dev server :5173<br/>(proxies /api, /ws)"] --> U["uvicorn :8000<br/>odmrp_sim.api.app:app"]
    U --> FS[("./scenarios<br/>./traces<br/>./var/files")]
  end
  B["Browser"] --> V
  CI["pytest / pytest-bdd"] -. in-process ASGI or :8000 .-> U
```

Single process, single simulation session per backend. Multi-session and multi-machine deployment are roadmap items (`odmrp-faw`).

## 1.4 Repository layout (proposed)

```
backend/
  pyproject.toml                 # uv-managed; deps: fastapi, uvicorn, pydantic, pyyaml
  odmrp_sim/
    model/        packets.py  topology.py  params.py  state.py  app_payload.py
    sim/          engine.py   scheduler.py  medium.py  timers.py  node_host.py  rng.py
    protocol/     interface.py  python_node.py  tables.py  seqnum.py  fake_node.py
    events/       bus.py  trace_writer.py  ring_buffer.py  schema.py
    services/     messaging.py  transfers.py  delivery_report.py  scenarios.py  controls.py
    api/          app.py  routers/{network,nodes,groups,messages,files,sim,trace}.py  ws.py  schemas.py
    cli.py                       # run a scenario headless, write trace
  tests/
    unit/        test_topology.py test_scheduler.py test_tables.py test_odmrp_*.py
    api/         test_rest.py test_ws.py
    bdd/         features/*.feature  steps/*.py
  schemas/      trace-event.v1.json  ws-frame.v1.json
frontend/
  src/lib/stores/sim.svelte.ts  src/lib/api.ts
  src/lib/components/{NetworkView,NodeInspector,MessagingPanel,TraceTimeline,Toolbar}.svelte
scenarios/     basic-mesh.yaml  two-sources.yaml  partition.yaml
docs/          (this directory)
```
