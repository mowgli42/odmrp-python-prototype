"""Address book, OMS data plan, super-node overlay, NeighborSender unicast-over-tunnels."""

from pathlib import Path

from odmrp_sim.dataplane.neighbor_send import (
    AddressBookNeighborProvider,
    NeighborSender,
    UnicastHop,
)
from odmrp_sim.model.address_book import AddressBook
from odmrp_sim.model.packets import Packet, PacketKind
from odmrp_sim.model.super_node import SuperNodePush
from odmrp_sim.services.address_book_svc import apply_super_node_push, load_address_book
from odmrp_sim.services.data_plan_svc import load_data_plan, resolve_endpoints, text_messages
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
BOOK = ROOT / "fixtures" / "overlay" / "address-book.json"
PLAN = ROOT / "fixtures" / "overlay" / "data-plan.json"
PUSH = ROOT / "fixtures" / "overlay" / "super-node-push.json"
SCENARIO = ROOT / "scenarios" / "overlay-mesh.yaml"


def test_load_address_book_super_node_and_neighbors():
    book = load_address_book(BOOK)
    assert 0 in book.nodes
    assert book.nodes[0].capabilities.is_super_node is True
    assert book.nodes[0].capabilities.can_stage_products is True
    assert any(n.tunnel_endpoint.startswith("ipsec://") for n in book.nodes[1].neighbors)
    assert book.logical_links()


def test_export_import_neighbors_roundtrip():
    book = load_address_book(BOOK)
    exported = book.export_neighbors()
    fresh = AddressBook(name="fresh")
    n = fresh.import_neighbors(exported)
    assert n == len(exported["edges"])
    pairs = {(e["from"], e["to"]) for e in exported["edges"]}
    got = set()
    for entry in fresh.nodes.values():
        for nb in entry.neighbors:
            got.add((entry.node_id, nb.peer_id))
    assert pairs == got


def test_data_plan_text_and_product():
    book = load_address_book(BOOK)
    plan = resolve_endpoints(load_data_plan(PLAN), book)
    texts = text_messages(plan)
    assert texts and texts[0].source_node == 0
    assert texts[0].source_endpoint == "ipsec://10.8.0.1:500"
    prod_msgs = [m for m in plan.messages if m.kind == "data_product"]
    assert prod_msgs
    loc = prod_msgs[0].product.location
    assert loc is not None
    assert loc.staging_node == 0
    assert loc.uri.startswith("https://")
    assert loc.tunnel_endpoint == "ipsec://10.8.0.1:500"


def test_super_node_push_prunes_neighbors():
    book = load_address_book(BOOK)
    before = len(book.nodes[1].neighbors)
    assert before > 3
    push = SuperNodePush.from_dict(__import__("json").loads(PUSH.read_text()))
    summary = apply_super_node_push(book, push, now=0.5)
    assert summary["applied"] >= 1
    after = book.nodes[1].active_neighbors(0.5)
    assert len(after) <= push.policy.max_neighbors
    # Prefer super peer 0
    assert any(n.peer_id == 0 for n in after)


def test_address_book_provider_hops_include_tunnel_endpoints():
    book = load_address_book(BOOK)
    provider = AddressBookNeighborProvider(book)
    hops = provider.hops_of(0, now=0.0)
    assert hops == [
        UnicastHop(peer_id=1, tunnel_endpoint="ipsec://10.8.0.2:500"),
        UnicastHop(peer_id=2, tunnel_endpoint="ipsec://10.8.0.3:500"),
    ]


def test_medium_exposes_neighbor_sender():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    assert isinstance(eng.medium.sender, NeighborSender)
    hops = eng.medium.sender.current_hops(0, now=0.0)
    assert {h.peer_id for h in hops} == {1, 2}
    assert all(h.tunnel_endpoint and h.tunnel_endpoint.startswith("ipsec://") for h in hops)


def test_overlay_mesh_tunnel_delivers():
    eng = SimulationEngine()
    data = load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    assert eng.overlay_mode == "tunnel"
    assert eng.address_book is not None
    assert eng.data_plan is not None
    snap = eng.snapshot()
    assert 0 in snap["overlay"]["super_nodes"]
    assert snap["overlay"]["logical_links"]
    delivered = sorted(
        {
            ev.node
            for ev in eng.bus.ring
            if ev.kind == "deliver" and ev.payload.get("group") == "demo"
        }
    )
    assert delivered == data["expect"]["delivered_to"], f"delivered={delivered}"
    txs = [e for e in eng.bus.ring if e.kind == "tx"]
    assert txs
    assert all(e.payload.get("mode") == "unicast_over_neighbors" for e in txs)
    assert all(e.payload.get("unicasts") is not None for e in txs)


def test_sparse_neighbor_set_not_full_mesh():
    book = load_address_book(BOOK)
    n = len(book.nodes)
    links = {tuple(sorted(p)) for p in book.logical_links()}
    assert len(links) < n * (n - 1) // 2
    # Source has no direct tunnel to far receiver 5 — delivery via FG mesh
    assert set(book.nodes[0].neighbor_ids()) == {1, 2}
    assert 5 not in book.nodes[0].neighbor_ids()


def test_fg_only_pure_data_via_neighbor_send():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    eng.run_until(eng.scheduler.now + 0.5)
    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    assert fg
    assert 4 not in fg

    # Non-FG: no TX
    pure_drop = Packet(
        kind=PacketKind.DATA,
        source=0,
        group="demo",
        seq=88_001,
        previous_hop=1,
        ttl=8,
        payload=b"probe-drop",
    )
    before4 = sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == 4)
    eng.hosts[4].on_receive(pure_drop, previous_hop=1, now=eng.scheduler.now)
    assert sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == 4) == before4

    # FG: neighbor_send with unicast_over_neighbors
    fg_id = fg[0]
    pure_fwd = Packet(
        kind=PacketKind.DATA,
        source=0,
        group="demo",
        seq=88_002,
        previous_hop=0,
        ttl=8,
        payload=b"probe-fwd",
    )
    before = sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == fg_id)
    eng.hosts[fg_id].on_receive(pure_fwd, previous_hop=0, now=eng.scheduler.now)
    txs = [e for e in eng.bus.ring if e.kind == "tx" and e.node == fg_id]
    assert len(txs) > before
    last = txs[-1]
    assert last.payload["mode"] == "unicast_over_neighbors"
    book = eng.address_book
    assert book is not None
    allowed = set(book.nodes[fg_id].neighbor_ids(eng.scheduler.now))
    assert set(last.payload["neighbors"]) <= allowed
    for u in last.payload["unicasts"]:
        assert u["tunnel_endpoint"].startswith("ipsec://")


def test_soft_state_neighbor_remove_stops_unicast():
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    book = eng.address_book
    assert book is not None
    entry = book.nodes[0]
    # Soft-expire peer 2
    for n in entry.neighbors:
        if n.peer_id == 2:
            n.status = "expired"
    hops = eng.medium.sender.current_hops(0, now=eng.scheduler.now)
    assert [h.peer_id for h in hops] == [1]
