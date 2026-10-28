# IPsec tunnel overlay — protocol sketch

Ponytail design for ODMRP without native IPv4 multicast/broadcast.

## Neighbor-send (sole TX boundary)

All ODMRP TX (JQ / JR / DATA) goes through one primitive:

```text
NeighborSender.neighbor_send(sender, packet, now)
  → for each UnicastHop in NeighborProvider.hops_of(sender):
       schedule one unicast delivery (sim) / one tunnel send (real later)
```

`Medium` is a thin façade; `NodeHost._tx_all` calls only `medium.neighbor_send`.
"Broadcast to neighbors" means: loop the current neighbor set and unicast the
same packet once per active peer. Trace `tx` carries:

- `mode: "unicast_over_neighbors"`
- `neighbors: [peer_id, …]`
- `unicasts: [{peer_id, tunnel_endpoint}, …]`

Providers:

| Mode | Provider | Peer set |
| --- | --- | --- |
| `radio` | `TopologyNeighborProvider` | unit-disk RF (still unicast-per-peer) |
| `tunnel` | `AddressBookNeighborProvider` | address-book soft-state tunnels |
| `hybrid` | `HybridNeighborProvider` | logical if present, else RF |

Protocol algorithms are unchanged: reverse-path learning, Join Reply → FG flag,
duplicate cache, FG-scoped pure DATA. Only the wire primitive is neighbor-send.

## Address book

`fixtures/overlay/address-book.json` — Commlink-inspired entries:

- capabilities (`is_super_node`, `can_stage_products`, …)
- `tunnel_endpoint` (e.g. `ipsec://10.8.0.1:500`)
- `neighbors[]` with status / priority / reason / expires_at (soft-state)
- import/export of edge lists via `/api/address-book/export|import/neighbors`

Sparse by design: source 0 tunnels only to relays 1 and 2 (not a full mesh);
far receiver 5 has no direct tunnel to 0.

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

## Scenario + visualization

`scenarios/overlay-mesh.yaml` wires tunnel mode + fixtures + join/text script.
UI draws RF links, logical tunnel peers, SUPER markers, and FG membership
separately so tunnels vs FG mesh are visible.

Later the same `NeighborSender` boundary can bind to simulated radio or real
IPsec tunnel sockets without changing JQ/JR/FG/dup-cache logic.
