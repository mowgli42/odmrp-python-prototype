# DEMO.md

## Quick Start (once implemented)

```bash
# Backend
cd backend
uv sync   # or pip install -e .
uvicorn odmrp_sim.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Happy-Path Demo Script

1. Load the default 6-node topology.
2. Select node 0 as source.
3. On nodes 3 and 5, join multicast group `demo`.
4. Send the text message “ODMRP works”.
5. Observe:
   - Join Query flood
   - Join Replies returning
   - FG nodes highlighted
   - Message arriving at nodes 3 and 5

## Sample Scenario Fixture

See `scenarios/basic-mesh.yaml` (to be created) for a deterministic topology and expected FG set.
