# GNS3 ODMRP labs

Neighbour-UDP appliances and scale projects for mixed-type ODMRP meshes
([GitHub issue #4](https://github.com/mowgli42/odmrp-python-prototype/issues/4)).

## Decisions (locked)

| Topic | Choice |
| --- | --- |
| Dataplane | Neighbour UDP (unicast per peer); **not** IP multicast |
| Impairment | **Off** in the agent; set delay/loss on **GNS3 links** |
| Images | Local `docker build` tags (`odmrp/node-*:local`); GHCR later |

## 1. Build images

From the repo root:

```bash
docker build -f docker/odmrp-node/Dockerfile.python -t odmrp/node-python:local .
docker build -f docker/odmrp-node/Dockerfile.java   -t odmrp/node-java:local .
docker build -f docker/odmrp-node/Dockerfile.rust   -t odmrp/node-rust:local .
docker build -f docker/odmrp-node/Dockerfile.cpp    -t odmrp/node-cpp:local .
```

Rust/C++ images are **FakeNode stubs** until real ports land.

## 2. Compose smoke (no GNS3)

```bash
python3 scripts/gen_basic_mesh_udp_configs.py
rm -f docker/compose/basic-mesh-mixed/traces/*.jsonl
docker compose -f docker/compose/basic-mesh-mixed/docker-compose.yml up --build --abort-on-container-exit
python3 scripts/diff_traces.py docker/compose/basic-mesh-mixed/traces --expect-delivered 3,5
```

## 3. Import appliances

1. Generate / refresh appliance files: `python3 scripts/gen_gns3_scale.py --appliances`
2. In GNS3: **Edit → Preferences → Docker → Import appliance**
3. Import `gns3/appliances/*.gns3a` (python, java, rust-stub, cpp-stub)

## 4. Open a scale project

```bash
python3 scripts/gen_gns3_scale.py --all --appliances
```

Projects under `gns3/projects/scale-{08,16,32,64,128}/`:

| Project | Layout |
| --- | --- |
| scale-08 | Two diamonds / corridor |
| scale-16 | 4×4 grid |
| scale-32 | Four clusters + gateways |
| scale-64 | Concentric rings |
| scale-128 | Seeded unit-disk |

Each directory has `adjacency.yaml` (static peers), `project.gns3` skeleton, and a short README.
Wire delay presets are documented in `adjacency.yaml` → `link_presets` — apply them in the GNS3 UI.

## 5. Inject traffic

Mount a per-node config (see `docker/compose/basic-mesh-mixed/configs/`) with a `script:` block:

```yaml
script:
  - { at: 0.0, op: join, group: demo }
  - { at: 1.0, op: text, group: demo, text: "hello" }
```

Or set `ODMRP_CONFIG` to a generated file from `adjacency.yaml`.

## Trace merge / diff

```bash
python3 scripts/diff_traces.py /path/to/traces --expect-fg 1,3 --expect-delivered 3,5
python3 scripts/diff_traces.py ./run-a --baseline ./run-b
```
