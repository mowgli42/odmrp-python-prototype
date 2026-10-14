# Sequence 2 — Data forwarding through the forwarding group

Draft §5.2: "Nodes relay data packets only if the packet is not a duplicate and the setting of FG_FLAG for the multicast group has not expired." Fixture and FG set `{1, 3}` from `01-mesh-formation.md`.

## 2.1 Second message after the mesh exists (no Join Query header)

```mermaid
sequenceDiagram
  autonumber
  participant S as Node 0 (source)
  participant A as Node 1 (FG)
  participant B as Node 2
  participant R1 as Node 3 (FG + member)
  participant C as Node 4
  participant R2 as Node 5 (member)

  Note over S: originate(demo, "second") → seq=2 (same counter as JQ)<br/>source transmits regardless of FG status
  S->>A: DATA(src=0, seq=2, prev=0)
  S->>B: DATA(src=0, seq=2, prev=0)

  Note over A: not duplicate → cache<br/>not member → no deliver<br/>FG(demo) unexpired → forward
  A->>S: DATA(prev=1) — drop reason=duplicate
  A->>R1: DATA(prev=1)
  Note over B: not duplicate → cache<br/>FG(demo) absent → drop reason=not_fg
  Note over R1: member → deliver (inbox, emit deliver)<br/>FG → forward
  R1->>A: DATA(prev=3) — drop reason=duplicate
  R1->>R2: DATA(prev=3)
  Note over R2: member → deliver<br/>not FG → no forward
  Note over C: never receives seq=2 (2 and 5 did not forward)
```

Decision table implemented by `odmrp-2xj`:

| duplicate? | member of group? | FG(group) unexpired? | action |
|---|---|---|---|
| yes | — | — | `drop reason=duplicate` |
| no | yes | yes | `deliver` + forward |
| no | yes | no | `deliver` only |
| no | no | yes | forward only |
| no | no | no | `drop reason=not_fg` (still cached, so a later copy is a duplicate) |

The source's own transmission is traced as `tx` with no preceding `rx`; the source never "forwards".

## 2.2 Data piggybacking a Join Query (first packet of a cycle)

When the packet carries a `JoinQueryHeader`, the Join Query rules run first (§5.1.2), then the payload is delivered to members. Forwarding of the *packet* follows the Join Query rule (rebroadcast if non-duplicate and TTL > 0) — i.e. a piggybacked data packet floods the whole network once per refresh. This is the ODMRP property that lets a brand-new receiver get the first packet of each cycle even before any FG exists.

```mermaid
sequenceDiagram
  participant X as Any node
  participant N as Neighbours
  X->>X: receive(DATA+JQ)
  alt (source, seq) in message cache
    X->>X: drop reason=duplicate
  else
    X->>X: cache / route[source] = prev_hop
    opt member of group
      X->>X: deliver payload / schedule Join Reply (jr_delay)
    end
    X->>X: hop_count += 1 / ttl -= 1
    alt ttl > 0
      X->>N: DATA+JQ(prev_hop = X)
    else
      X->>X: drop reason=ttl
    end
  end
```

## 2.3 Topology change between refreshes

If a link on the mesh breaks (node moved out of range) between refreshes, data is simply lost on that branch until the next Join Query/Join Reply cycle rebuilds the mesh — there is no local repair in base ODMRP (E-ODMRP and PatchODMRP add it). The sequence is therefore the same as 2.1 with the `rx` events missing on the broken link; the delivery report (`04-messaging-file-transfer.md`) shows which receivers were reached.

```mermaid
sequenceDiagram
  participant S as Node 0
  participant A as Node 1 (FG)
  participant R1 as Node 3
  participant UI as UI
  UI->>S: PUT /api/nodes/3/position (moved away from 1)
  Note over A,R1: topology op=link_down a=1 b=3
  S->>A: DATA(seq=3)
  A--xR1: no rx scheduled (not a neighbour at tx time)
  Note over R1: nothing delivered until next refresh re-learns a path (if any)
```

Trace assertion for the regression test: after `link_down`, the next `JOIN_QUERY` cycle produces a `state.route op=set` at node 3 with a new `next_hop` (or none if partitioned), and FG membership of node 1 is *not* refreshed by node 3 any more and expires at `last_refresh + FG_TIMEOUT`.
