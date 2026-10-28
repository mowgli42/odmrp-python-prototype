#!/usr/bin/env python3
"""Sparse IPsec-tunnel overlay demo: NeighborSender unicast-over-tunnels.

Shows:
  - neighbor graph is not a full mesh (source 0 → relays 1,2 only)
  - every TX uses mode=unicast_over_neighbors with tunnel endpoints
  - FG mesh forms; receivers 3 and 5 get the payload
  - pure DATA is forwarded only by current FG members
  - no IP multicast / link-layer broadcast
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from odmrp_sim.model.packets import Packet, PacketKind  # noqa: E402
from odmrp_sim.services.scenarios import load_scenario  # noqa: E402
from odmrp_sim.sim.engine import SimulationEngine  # noqa: E402

SCENARIO = ROOT / "scenarios" / "overlay-mesh.yaml"


def main() -> int:
    eng = SimulationEngine()
    data = load_scenario(eng, SCENARIO)
    book = eng.address_book
    assert book is not None

    links = {tuple(sorted(p)) for p in book.logical_links()}
    n = len(book.nodes)
    print(f"overlay mode={eng.overlay_mode}  nodes={n}  undirected tunnels={len(links)}  full-mesh would be {n * (n - 1) // 2}")
    src_peers = sorted(book.nodes[0].neighbor_ids())
    print(f"source 0 active tunnels → {src_peers}")
    assert len(links) < n * (n - 1) // 2
    # Sparse from the source: no direct unicast path 0→5 (delivery via FG mesh)
    assert 5 not in src_peers
    assert src_peers == [1, 2]

    eng.run_until(eng.scheduler.now + 0.5)

    txs = [e for e in eng.bus.ring if e.kind == "tx"]
    assert txs and all(e.payload.get("mode") == "unicast_over_neighbors" for e in txs)
    sample = next(e for e in txs if e.node == 0)
    print(f"sample TX node=0 mode={sample.payload['mode']} unicasts={sample.payload['unicasts']}")

    delivered = sorted(
        {
            e.node
            for e in eng.bus.ring
            if e.kind == "deliver" and e.payload.get("group") == "demo"
        }
    )
    print(f"delivered_to={delivered}  expect={data['expect']['delivered_to']}")
    assert delivered == data["expect"]["delivered_to"]

    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    print(f"FG(demo)={fg}")

    # Pure DATA: only FG rebroadcasts via neighbor-send
    for nid in (4, fg[0]):
        pkt = Packet(
            kind=PacketKind.DATA,
            source=0,
            group="demo",
            seq=70_000 + nid,
            previous_hop=0,
            ttl=8,
            payload=b"probe",
        )
        before = sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == nid)
        eng.hosts[nid].on_receive(pkt, previous_hop=0, now=eng.scheduler.now)
        after = sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == nid)
        print(f"  pure DATA @ node {nid}: tx_delta={after - before}  fg={nid in fg}")

    print("ok — unicast-over-tunnels FG mesh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
