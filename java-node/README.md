# Minimal Java ODMRPNode reference

First-party Java implementation of the ADR-005 `ODMRPNode` contract over NDJSON stdio
(`docs/external-node-contract.md`). Used for differential testing against `PythonODMRPNode`.

## Build

Requires JDK 17+ (`JAVA_HOME` or `~/tools/jdk`).

```bash
./build.sh
```

Produces `dist/odmrp-java-node.jar`.

## Run

```bash
java -jar dist/odmrp-java-node.jar
```

Speak NDJSON on stdin; one reply line per request. Example:

```json
{"op":"configure","id":1,"node_id":4,"params":{},"rng_seed":42}
{"op":"get_state","id":2}
{"op":"shutdown","id":3}
```

## Spec

See `specs/java-reference/spec.md` and beads epic `odmrp-7o1`.
