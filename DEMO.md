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

## Screenshots

Network view after `basic-mesh` load (FG halos, status strip, Trace):

![Loaded basic-mesh](docs/walkthrough/walkthrough_01_loaded_basic_mesh.png)

Node inspector on forwarding-group node **1**:

![Inspector node 1](docs/walkthrough/walkthrough_02_inspector_node1.png)

After sending a text message:

![After send](docs/walkthrough/walkthrough_03_after_send.png)

Receiver **5** inbox:

![Receiver inbox](docs/walkthrough/walkthrough_04_receiver_inbox.png)

Trace panel filtered to `deliver`:

![Trace deliver filter](docs/walkthrough/walkthrough_05_trace_panel.png)

Trace close-up:

![Trace close-up](docs/walkthrough/walkthrough_05b_trace_closeup.png)

Messaging + Trace strip:

![Messaging and Trace](docs/walkthrough/walkthrough_05c_messaging_and_trace.png)

Regenerate captures (API on :8000, Vite on :5173):

```bash
cd frontend && node scripts/capture_ui_screenshots.mjs
```

## Tests

```bash
cd backend
PYTHONPATH=. python3 -m pytest -q
```
