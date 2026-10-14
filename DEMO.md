# Demo walkthrough

## Prerequisites
- Python 3.11+
- Node.js 20+

## Install

```bash
cd backend
python3 -m pip install -e '.[dev]'

cd ../frontend
npm install
```

## Run (two terminals)

```bash
# terminal 1 — API + simulator
cd backend
PYTHONPATH=. python3 -m uvicorn odmrp_sim.api.app:app --host 127.0.0.1 --port 8000

# terminal 2 — UI (proxies /api and /ws to :8000)
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173/

The UI loads `scenarios/basic-mesh.yaml` on connect: source **0**, receivers **3** and **5**, ring topology, message already injected at t=1.0. After settle you should see:

- Forwarding-group halo on nodes **1** and **3**
- Inbox text `ODMRP works` on nodes **3** and **5**
- Trace events for `tx` / `rx` / `state.fg` / `deliver`

## Headless scenario

```bash
cd backend
PYTHONPATH=. python3 -m odmrp_sim.cli basic-mesh --trace ../traces/basic-mesh.jsonl
```

## What to try in the UI
1. Click node **1** — inspector shows route `0 → next 0` and FG `demo`.
2. Click **Step 0.1s** or **Run** to watch soft-state clocks advance.
3. Send another text from the messaging panel; delivery report lists receivers from the trace.
4. **Reset scenario** reloads the fixture from a clean seed.

## Screenshot placeholders
- Network view with FG halos: _(capture after load)_
- Node inspector routes table: _(capture node 1)_
- Trace timeline after send: _(capture after messaging)_

## Tests

```bash
cd backend
PYTHONPATH=. python3 -m pytest -q
```
