"""Address book, OMS data plan, super-node overlay, tunnel neighbor-send."""

from pathlib import Path

from odmrp_sim.model.address_book import AddressBook
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
    # TX neighbors should be from address book, not empty
    txs = [e for e in eng.bus.ring if e.kind == "tx"]
    assert txs
    assert all(e.payload.get("neighbors") is not None for e in txs)
