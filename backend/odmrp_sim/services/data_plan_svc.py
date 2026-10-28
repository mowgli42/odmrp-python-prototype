"""Load OMS-aligned data plans and resolve address-book endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from odmrp_sim.model.address_book import AddressBook
from odmrp_sim.model.data_plan import DataPlan, DataPlanMessage, ProductMetadata

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "fixtures" / "overlay"


def load_data_plan(path: Path | str) -> DataPlan:
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
    return DataPlan.from_dict(data)


def resolve_endpoints(plan: DataPlan, book: AddressBook) -> DataPlan:
    """Fill source_endpoint / product tunnel_endpoint from the address book."""
    for msg in plan.messages:
        entry = book.get(msg.source_node)
        if entry and not msg.source_endpoint:
            msg.source_endpoint = entry.tunnel_endpoint
        if msg.product and msg.product.location:
            loc = msg.product.location
            if loc.staging_node is not None and not loc.tunnel_endpoint:
                st = book.get(loc.staging_node)
                if st:
                    loc.tunnel_endpoint = st.tunnel_endpoint
    for prod in plan.products:
        if prod.location and prod.location.staging_node is not None:
            if not prod.location.tunnel_endpoint:
                st = book.get(prod.location.staging_node)
                if st:
                    prod.location.tunnel_endpoint = st.tunnel_endpoint
    return plan


def text_messages(plan: DataPlan) -> list[DataPlanMessage]:
    return [m for m in plan.messages if m.kind == "data_text"]


def product_messages(plan: DataPlan) -> list[DataPlanMessage]:
    return [m for m in plan.messages if m.kind == "data_product"]


def all_products(plan: DataPlan) -> list[ProductMetadata]:
    seen = {p.product_id: p for p in plan.products}
    for m in plan.messages:
        if m.product:
            seen[m.product.product_id] = m.product
    return list(seen.values())
