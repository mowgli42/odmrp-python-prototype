# IPsec tunnel overlay — protocol sketch

Ponytail design for ODMRP without native IPv4 multicast/broadcast.

## Neighbor-send

All ODMRP TX (JQ / JR / DATA) goes through one primitive:

```text
neighbor_send(sender, packet) → for each active peer in NeighborProvider
```

Providers:

| Mode | Provider | Peer set |
| --- | --- | --- |
| `radio` | `TopologyNeighborProvider` | unit-disk RF |
| `tunnel` | `AddressBookNeighborProvider` | address-book soft-state tunnels |
| `hybrid` | `HybridNeighborProvider` | logical if present, else RF |

FG-scoped data forwarding is unchanged: only FG members (and sources/members as today) rebroadcast, still via neighbor-send.

## Address book

`fixtures/overlay/address-book.json` — Commlink-inspired entries:

- capabilities (`is_super_node`, `can_stage_products`, …)
- `tunnel_endpoint` (e.g. `ipsec://10.8.0.1:500`)
- `neighbors[]` with status / priority / reason / expires_at
- import/export of edge lists via `/api/address-book/export|import/neighbors`

## OMS data plan

`fixtures/overlay/data-plan.json`:

- `data_text` → ODMRP DATA (AppPayload text)
- `data_product` → ProductMetadata + ProductLocation (uri, mime, expiration, staging_node, tunnel_endpoint)
- endpoints resolved from the address book

## Super-node overlay

Ground / high-capability nodes push:

1. neighbor recommendations (pruned by `max_neighbors` + preference)
2. membership updates
3. data-plan fragments + staging product hints

Policy knobs: `max_neighbors`, `preference` (`geo`|`capability`|`priority`|`mixed`), `refresh_interval`, `soft_state_ttl`.

## Scenario

`scenarios/overlay-mesh.yaml` wires tunnel mode + fixtures + classic join/text script so FG delivery still proves out.
