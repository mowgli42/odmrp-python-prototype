"""Load / save / apply address books for the overlay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from odmrp_sim.model.address_book import AddressBook, AddressBookEntry, NeighborRelation, NodeCapabilities
from odmrp_sim.model.packets import NodeId
from odmrp_sim.model.super_node import SuperNodePolicy, SuperNodePush

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "fixtures" / "overlay"


def load_address_book(path: Path | str) -> AddressBook:
    path = Path(path)
    if not path.is_absolute():
        for base in (FIXTURES, REPO_ROOT, Path.cwd()):
            candidate = base / path
            if candidate.is_file():
                path = candidate
                break
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return AddressBook.from_dict(data)


def save_address_book(book: AddressBook, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(book.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def book_from_scenario_nodes(
    nodes: list[dict[str, Any]],
    *,
    name: str = "from-scenario",
    default_endpoint_fmt: str = "ipsec://10.8.0.{id}:500",
) -> AddressBook:
    """Build a minimal book from scenario node list + optional overlay fields."""
    book = AddressBook(name=name, description="Derived from scenario nodes")
    for n in nodes:
        nid = int(n["id"])
        caps = NodeCapabilities.from_dict(n.get("capabilities"))
        neighbors = [NeighborRelation.from_dict(x) for x in n.get("neighbors", [])]
        endpoint = str(n.get("tunnel_endpoint") or default_endpoint_fmt.format(id=nid))
        book.upsert(
            AddressBookEntry(
                node_id=nid,
                callsign=str(n.get("callsign") or f"n{nid}"),
                name=str(n.get("name") or ""),
                platform=str(n.get("platform", "mobile")),
                tunnel_endpoint=endpoint,
                capabilities=caps,
                neighbors=neighbors,
                groups=[str(g) for g in n.get("groups", [])],
                position={"x": float(n["x"]), "y": float(n["y"])} if "x" in n else n.get("position"),
                status=str(n.get("status", "active")),
                addressbook_ref=n.get("addressbook_ref"),
            )
        )
    return book


def apply_super_node_push(
    book: AddressBook,
    push: SuperNodePush,
    *,
    target: NodeId | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Apply recommendations to one or all ordinary nodes. Returns summary."""
    policy = push.policy
    t = push.at if now is None else now
    targets = [target] if target is not None else [
        e.node_id for e in book.nodes.values() if not e.capabilities.is_super_node
    ]
    applied = 0
    pruned = 0
    for nid in targets:
        entry = book.get(nid)
        if entry is None:
            continue
        recs = push.recommendations_for(nid)
        if not recs:
            continue
        # Stamp soft-state + reason
        stamped: list[NeighborRelation] = []
        for rel in recs:
            rel.reason = "super_node"
            rel.status = "recommended" if rel.status == "pending" else rel.status
            if rel.expires_at is None:
                rel.expires_at = t + policy.soft_state_ttl
            rel.last_refresh = t
            stamped.append(rel)
        # Merge then prune by policy
        by_peer = {n.peer_id: n for n in entry.neighbors}
        for rel in stamped:
            by_peer[rel.peer_id] = rel
        merged = list(by_peer.values())
        ranked = _rank_neighbors(merged, book, policy, now=t)
        keep = ranked[: policy.max_neighbors]
        pruned += max(0, len(merged) - len(keep))
        entry.neighbors = keep
        applied += 1

    # Membership hints → groups on entries
    for mu in push.membership:
        if mu.op == "set":
            for e in book.nodes.values():
                if e.node_id in mu.members:
                    if mu.group not in e.groups:
                        e.groups.append(mu.group)
                elif mu.group in e.groups and e.node_id not in mu.members:
                    e.groups = [g for g in e.groups if g != mu.group]
        elif mu.op == "add":
            for mid in mu.members:
                e = book.get(mid)
                if e and mu.group not in e.groups:
                    e.groups.append(mu.group)
        elif mu.op == "remove":
            for mid in mu.members:
                e = book.get(mid)
                if e and mu.group in e.groups:
                    e.groups = [g for g in e.groups if g != mu.group]

    # Staging products: mark staging nodes as can_stage_products
    for prod in push.staging_products:
        loc = prod.location
        if loc and loc.staging_node is not None:
            e = book.get(loc.staging_node)
            if e:
                e.capabilities.can_stage_products = True

    return {"targets": targets, "applied": applied, "pruned": pruned, "from_node": push.from_node}


def _rank_neighbors(
    neighbors: list[NeighborRelation],
    book: AddressBook,
    policy: SuperNodePolicy,
    *,
    now: float,
) -> list[NeighborRelation]:
    active = [n for n in neighbors if n.is_active(now)]

    def score(rel: NeighborRelation) -> tuple:
        peer = book.get(rel.peer_id)
        super_bonus = 0 if (peer and peer.capabilities.is_super_node and policy.prefer_super_peers) else 1
        stage_bonus = 0 if (peer and peer.capabilities.can_stage_products and policy.prefer_staging_capable) else 1
        # Lower tuple sorts first
        if policy.preference == "priority":
            return (rel.priority, super_bonus, stage_bonus, rel.peer_id)
        if policy.preference == "capability":
            return (super_bonus, stage_bonus, rel.priority, rel.peer_id)
        if policy.preference == "geo":
            # Without real geo distance, prefer lower priority then id
            return (rel.priority, rel.peer_id, super_bonus)
        # mixed
        return (super_bonus, rel.priority, stage_bonus, rel.peer_id)

    return sorted(active, key=score)
