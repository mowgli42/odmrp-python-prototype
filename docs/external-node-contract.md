# External node contract (ADR-005 / roadmap `odmrp-dn0`)

An external C++/Rust ODMRP binary speaks **NDJSON over stdio**. One request in flight at a time; every request gets exactly one reply.

## Lifecycle
1. Host spawns process with `configure` as the first message.
2. Host calls `set_membership` / `originate` / `receive` / `advance` as the simulator progresses.
3. Host reads `next_timer` to know when to call `advance` again.
4. On reset, host kills the process (or sends `shutdown`).

## Messages (host → node)

```json
{"op":"configure","id":1,"node_id":4,"params":{...},"rng_seed":1234}
{"op":"set_membership","id":2,"group":"demo","member":true,"now":1.0}
{"op":"originate","id":3,"group":"demo","payload_b64":"...","now":1.0}
{"op":"receive","id":4,"packet":{...},"previous_hop":1,"now":1.002}
{"op":"advance","id":5,"now":1.025}
{"op":"next_timer","id":6}
{"op":"get_state","id":7}
{"op":"shutdown","id":8}
```

## Replies (node → host)

```json
{"id":1,"ok":true}
{"id":3,"ok":true,"packets":[{...}]}
{"id":6,"ok":true,"at":4.0}
{"id":7,"ok":true,"state":{...}}
{"id":4,"ok":false,"error":"malformed packet"}
```

`packets` use the same `Packet.to_dict()` schema as the Python reference (`docs/architecture/03-data-model-and-interfaces.md`).

## Conformance checklist
- [ ] Deterministic given the same `rng_seed` and call sequence
- [ ] `advance(now)` fires every timer with `due <= now` in due order
- [ ] Duplicate `(source, seq)` Join Queries are dropped with no state change
- [ ] FG keyed by group (unless `fg_scope=source_group`)
- [ ] Join Reply is a table; once-per-refresh suppression when the table is unchanged
- [ ] Trace-comparable: identical `(kind, node, payload)` stream vs Python on `basic-mesh` with jitter 0
