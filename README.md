# ODMRP Python Prototype

Python prototype of the On-Demand Multicast Routing Protocol (ODMRP) with FastAPI backend and Svelte visualization.

This repository starts with a complete **OpenSpec + Gherkin** system description so Cursor (or any AI coding assistant) can research and implement the prototype in a spec-driven way.

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
```

## How to Use with Cursor
1. Open this repo in Cursor.
2. Reference the relevant `specs/*/spec.md` and `design.md` when implementing each phase in `tasks.md`.
3. Prefer vertical slices that make one Gherkin scenario pass before moving on.
4. Keep the Python ODMRP logic behind the interface described in `design.md` so external language implementations can be swapped later.

## Protocol Notes
- Defaults match common literature values (3 s refresh, ~3× FG timeout).
- Unidirectional link detection, Join Reply aggregation, and full RFC5444 encoding are deferred (see `beads.md`).
- Prioritizes observability and determinism over bit-exact wire format.

## Next Step
Begin with Phase 1 of `tasks.md`.
