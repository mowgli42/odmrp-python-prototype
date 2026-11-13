# Sequence 7 — OMS SA status + position over ODMRP

Normative behaviour: `specs/oms-sa-distribution/spec.md`, ADR-008 in `design.md`.
Assumes FG formation from `01-mesh-formation.md` and pure-DATA forwarding rules from `02-data-forwarding.md`.

Rates: **status every 20 s**, **position every 5 s**. After `mesh_established`, app reports are **pure DATA** (no Join Query). Mesh refresh still floods JQ every `ROUTE_REFRESH_INTERVAL` (~3 s).

## 7.1 Dual-rate planes

```mermaid
sequenceDiagram
  autonumber
  participant S as Node S (OMS peer)
  participant FG as FG members
  participant R as Peer members

  Note over S: t=0 first oms_status<br/>mesh not established → DATA+JQ (flood)
  S->>FG: DATA+JQ oms_status seq=1
  FG->>R: DATA+JQ (TTL rebroadcast)
  R-->>S: Join Reply path → mesh_established

  Note over S: t=5,10,15 oms_position<br/>pure DATA (FG only)
  S->>FG: DATA oms_position seq=2
  FG->>R: DATA (FG forward, dup cache)
  Note over R: deliver; non-FG non-member drop not_fg

  Note over S: t=3,6,9… ROUTE_REFRESH<br/>JQ standalone or piggyback
  S->>FG: JQ seq=k (flood once per refresh)
```

## 7.2 Multi-source without re-originate

```mermaid
sequenceDiagram
  participant A as Node A
  participant B as Node B
  participant I as FG relay
  A->>I: DATA oms_status platform_id=A
  I->>B: DATA (forward)
  Note over B: deliver; store by platform_id=A
  B->>I: DATA oms_status platform_id=B
  I->>A: DATA (forward)
  Note over A: MUST NOT originate payload platform_id=B
  Note over A,B: (source,seq) cache drops echoes / loops
```

## 7.3 Storm accounting (trace assertions)

| Window | Expect |
| --- | --- |
| One position period, N sources, mesh up | ≈ N pure DATA originates; JQ count ≈ refreshes in window (not N) |
| Dup drops | Echoes on bidirectional links reason=`duplicate` |
| Non-FG non-member | reason=`not_fg`, no TX |
| Delivery | Each member delivers N−1 peer reports per round |

## 7.4 Overlay note

In `tunnel` mode, neighbor-send unicasts the same pure DATA to address-book peers; FG membership still gates who forwards. Gateway `product_meta` / `product_loc` (ttl=1) and JREAP SA feed remain separate from periodic `oms_status` / `oms_position`.
