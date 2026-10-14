# ODMRP Python Prototype

Python prototype of the On-Demand Multicast Routing Protocol (ODMRP) with FastAPI backend and Svelte visualization.

The simulator, Python ODMRP reference, REST/WebSocket API, and Svelte UI are implemented under `backend/` and `frontend/`. Specs, architecture docs, and beads-tracked sequencing remain the source of truth for what was built and what is still roadmap.

## Quick start

```bash
# backend
cd backend && python3 -m pip install -e '.[dev]'
PYTHONPATH=. python3 -m uvicorn odmrp_sim.api.app:app --host 127.0.0.1 --port 8000

# frontend (other terminal)
cd frontend && npm install && npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173/ — see `DEMO.md` for the walkthrough.

## Purpose
- Observable, deterministic simulation of ODMRP (mesh-based forwarding group, soft-state, Join Query / Join Reply).
- Interactive Svelte frontend showing nodes, links, FG membership, and live traffic.
- Multicast text messaging and chunked file transfers.
- Clean interfaces so the Python reference implementation can later serve as a test harness for C++ and Rust versions.

## OpenSpec Structure
```
proposal.md
design.md
tasks.md
beads.md
DEMO.md
specs/
  odmrp/spec.md
  simulation/spec.md
  messaging/spec.md
  visualization/spec.md
  test-harness/spec.md
docs/
  review/          architecture review + adherence matrix
  architecture/    C4, component, data-model, state-machine drawings
  sequences/       sequence diagrams
  mockups/         notional display mockups (SVG)
  implementation-plan.md
  beads/           beads graph plan and key-to-ID map
.beads/            beads issue database (bd) + issues.jsonl export
```

## Architecture Review and Implementation Package
The `docs/` tree holds the architecture review, the drawings, and the implementation plan that
were produced from the specs above. Read them in this order:

| Document | What it gives you |
| --- | --- |
| `docs/review/architecture-review.md` | Findings F-01…F-17 against the IETF ODMRP drafts and the GloMoSim / ns-2 / Java implementations, the recommended `ODMRPNode` interface, target architecture. |
| `docs/review/adherence-matrix.md` | Row-by-row comparison of control plane, data plane, and harness behaviour: draft vs. reference implementations vs. this repo's spec. |
| `docs/architecture/01-context-and-containers.md` | C4 context and container diagrams, deployment view, proposed repository layout. |
| `docs/architecture/02-components-and-modules.md` | Backend and frontend component diagrams, component contracts, cross-cutting rules. |
| `docs/architecture/03-data-model-and-interfaces.md` | Packet and node-state class diagrams, protocol parameter defaults, trace event kinds, REST and WebSocket schemas, scenario file format. |
| `docs/architecture/04-state-machines.md` | FG entry, routing entry, source session, membership, transfer assembler, run mode, and packet lifecycle state machines. |
| `docs/sequences/*.md` | Sequence diagrams: mesh formation, data forwarding, soft-state refresh and expiry, messaging and file transfer, UI/API/simulation loop, external node adapter. |
| `docs/mockups/` | Notional display mockups (SVG wireframes) for the network view, node inspector, messaging panel, and trace timeline, with region-to-API bindings in `docs/mockups/README.md`. |
| `docs/implementation-plan.md` | Phase sequencing, per-epic task tables, dependency graph, and spec-scenario traceability, all keyed to beads IDs. |

## Work Tracking with Beads
Implementation work is tracked with [beads](https://github.com/steveyegge/beads) (`bd`). The issue
database lives in `.beads/` and the portable export is `.beads/issues.jsonl`.

```bash
bd ready                      # unblocked work, highest priority first
bd show odmrp-vy0             # Phase 0 epic: decisions and spec reconciliation
bd list --type epic           # all phases
bd graph odmrp-4fi            # dependency graph for the ODMRP epic
bd update <id> --status in_progress
bd close <id> --reason "..."
bd export -o .beads/issues.jsonl   # before committing
```

If you are starting from a fresh clone and `bd list` is empty, run `bd import -i .beads/issues.jsonl`.
The original authoring plan is kept in `docs/beads/graph-plan.json` with the key-to-ID map in
`docs/beads/ids.json`.

## How to Use with Cursor
1. Open this repo in Cursor.
2. Run `bd ready` and pick the top unblocked bead; its description links the spec scenarios and the docs section it implements.
3. Reference the relevant `specs/*/spec.md`, `design.md`, and the matching `docs/` page while implementing.
4. Prefer vertical slices that make one Gherkin scenario pass before moving on.
5. Keep the Python ODMRP logic behind the `ODMRPNode` interface (`docs/review/architecture-review.md`, F-10) so external language implementations can be swapped later.

## Protocol Notes
- Defaults match common literature values (3 s refresh, 9 s FG / route timeout, TTL 32); see `docs/architecture/03-data-model-and-interfaces.md`.
- Join Queries are piggybacked on data packets and Join Replies are per-group tables, as in the IETF draft and the GloMoSim / ns-2 reference code (`docs/review/architecture-review.md`, F-01 and F-02).
- Unidirectional link detection, Join Reply reliability, and full RFC 5444 encoding are deferred to the roadmap epic (see `beads.md`).
- Prioritizes observability and determinism over bit-exact wire format.

## Next Step
Start with the Phase 0 decision beads (`bd list --parent odmrp-vy0`), then Phase 1 of `docs/implementation-plan.md`.
