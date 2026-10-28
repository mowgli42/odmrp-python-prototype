"""Executable coverage for overlay_unicast.feature (Gherkin source of truth).

pytest-bdd 9.x is incompatible with pytest 9 FixtureManager APIs, so these
tests mirror the feature scenarios as plain pytest while keeping the .feature
file under tests/bdd/features/ for OpenSpec / human review.
"""

from pathlib import Path

from odmrp_sim.model.packets import Packet, PacketKind
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimulationEngine

FEATURE = Path(__file__).resolve().parents[1] / "features" / "overlay_unicast.feature"
SCENARIO = Path(__file__).resolve().parents[4] / "scenarios" / "overlay-mesh.yaml"


def _settle():
    assert FEATURE.is_file(), f"missing Gherkin feature: {FEATURE}"
    eng = SimulationEngine()
    load_scenario(eng, SCENARIO)
    assert eng.overlay_mode == "tunnel"
    assert eng.address_book is not None
    assert eng.medium.sender is not None
    eng.run_until(eng.scheduler.now + 0.5)
    return eng


def test_tunnel_mode_tx_is_unicast_over_addressbook_peers_only():
    """Scenario: Tunnel mode TX is unicast over address-book peers only"""
    eng = _settle()
    book = eng.address_book
    assert book is not None
    now = eng.scheduler.now

    txs = [e for e in eng.bus.ring if e.kind == "tx"]
    assert txs
    assert all(e.payload.get("mode") == "unicast_over_neighbors" for e in txs)
    assert all(isinstance(e.payload.get("unicasts"), list) for e in txs)

    expected0 = set(book.nodes[0].neighbor_ids(now))
    src_txs = [e for e in txs if e.node == 0]
    assert src_txs
    for e in src_txs:
        assert set(e.payload.get("neighbors") or []) <= expected0
        for u in e.payload.get("unicasts") or []:
            assert str(u.get("tunnel_endpoint", "")).startswith("ipsec://")

    for e in txs:
        if e.node < 0:
            continue
        allowed = set(book.nodes[e.node].neighbor_ids(now))
        peers = set(e.payload.get("neighbors") or [])
        assert peers <= allowed, f"node {e.node}: {peers} not subset of {allowed}"


def test_sparse_fg_mesh_delivers_data_without_ip_multicast():
    """Scenario: Sparse FG mesh delivers data without IP multicast"""
    eng = _settle()
    book = eng.address_book
    assert book is not None

    n = len(book.nodes)
    undirected = {tuple(sorted((a, b))) for a, b in book.logical_links(eng.scheduler.now)}
    assert len(undirected) < n * (n - 1) // 2
    assert set(book.nodes[0].neighbor_ids()) == {1, 2}

    for rid in (3, 5):
        inbox = eng.hosts[rid].get_state().inbox
        assert any("ODMRP overlay hello" in (i.body or "") for i in inbox), f"node {rid}"

    assert "demo" not in eng.hosts[4].get_state().forwarding_groups
    before4 = sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == 4)
    eng.hosts[4].on_receive(
        Packet(
            kind=PacketKind.DATA,
            source=0,
            group="demo",
            seq=99_001,
            previous_hop=1,
            ttl=16,
            payload=b"fg-only probe",
        ),
        previous_hop=1,
        now=eng.scheduler.now,
    )
    assert sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == 4) == before4
    assert any(
        e.kind == "drop" and e.node == 4 and e.payload.get("reason") == "not_fg"
        for e in eng.bus.ring
    )

    fg = sorted(
        nid for nid, h in eng.hosts.items() if "demo" in h.get_state().forwarding_groups
    )
    assert fg and all(n in (1, 2, 3) for n in fg)
    assert 4 not in fg and 0 not in fg

    fg_node = fg[0]
    before = sum(1 for e in eng.bus.ring if e.kind == "tx" and e.node == fg_node)
    eng.hosts[fg_node].on_receive(
        Packet(
            kind=PacketKind.DATA,
            source=0,
            group="demo",
            seq=99_002,
            previous_hop=0,
            ttl=16,
            payload=b"fg forward",
        ),
        previous_hop=0,
        now=eng.scheduler.now,
    )
    txs = [e for e in eng.bus.ring if e.kind == "tx" and e.node == fg_node]
    assert len(txs) > before
    assert txs[-1].payload.get("mode") == "unicast_over_neighbors"
    assert txs[-1].payload.get("unicasts")
