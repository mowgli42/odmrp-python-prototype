# Sequence 4 — Messaging and file transfer

Application layer (`specs/messaging/spec.md`) on top of ODMRP data packets. Beads `odmrp-2kc`, `odmrp-a1c`, `odmrp-o8u`.

## 4.1 Text message end to end

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant API as POST /api/messages
  participant MS as MessagingService
  participant H0 as NodeHost 0
  participant N0 as ODMRPNode 0
  participant M as Medium
  participant H3 as NodeHost 3
  participant N3 as ODMRPNode 3
  participant BUS as EventBus

  U->>API: {source: 0, group: "demo", text: "ODMRP works"}
  API->>MS: send_text(0, "demo", text)
  MS->>MS: message_id = uuid / payload = AppPayload(kind=text, message_id, body)
  MS->>H0: originate("demo", payload.encode(), now)
  H0->>N0: originate(...)
  N0-->>H0: [DATA(+JQ if no session)]
  H0->>M: broadcast(0, packet, now)
  M->>BUS: tx {packet, neighbors:[1,2]}
  API-->>U: 202 {message_id}
  Note over M,H3: ... flood / forwarding per sequences 1–2 ...
  M->>H3: deliver(packet, prev=1, now)
  H3->>N3: receive(...)
  N3-->>H3: [forwarded copies]
  H3->>H3: member of demo → decode AppPayload
  H3->>BUS: deliver {packet_id, message_id, group, app_kind=text}
  H3->>MS: inbox(3).append(InboxItem(message_id, body, t))
```

The HTTP response returns before delivery (the simulation may be paused). Delivery is observed through the WebSocket `deliver` events or `GET /api/messages/{id}/report`.

## 4.2 File transfer: chunking and reassembly

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant API as POST /api/files (multipart)
  participant MS as MessagingService
  participant H0 as NodeHost 0
  participant Net as ODMRP mesh
  participant H5 as NodeHost 5
  participant TA as TransferAssembler(5, transfer_id)
  participant FS as FileStore

  U->>API: source=0, group=demo, file=demo.txt (10 240 B)
  API->>MS: send_file(0, "demo", "demo.txt", bytes)
  MS->>MS: transfer_id = uuid / total = ceil(10240/1024) = 10 / sha256 = digest(bytes)
  loop index = 0 .. 9
    MS->>H0: originate("demo", AppPayload(kind=chunk, transfer_id, index, total, name, sha256, data[index]))
    H0->>Net: DATA seq=s+index
  end
  API-->>U: 202 {transfer_id, total: 10}

  Net->>H5: deliver(DATA chunk 0)
  H5->>TA: create (total=10, sha256) / add(0)
  H5->>MS: transfer op=start
  Net->>H5: deliver(chunk 1 .. 9)  (any order, duplicates ignored)
  H5->>TA: add(index)
  TA-->>H5: received == total
  TA->>TA: verify sha256
  alt match
    TA->>FS: store(transfer_id, node=5, name, bytes)
    H5->>MS: transfer op=complete
  else mismatch
    H5->>MS: transfer op=verify_failed
  end
  U->>API: GET /api/files/{transfer_id}/receivers/5
  API->>FS: read
  API-->>U: 200 application/octet-stream (byte-identical demo.txt)
```

Because chunks ride ordinary data packets, each one is forwarded by the same FG rule; there is no separate reliability. If the mesh refreshes mid-transfer (every 3 s) the first chunk after the refresh simply carries the Join Query header.

## 4.3 Delivery report (built from the trace)

```mermaid
sequenceDiagram
  actor U as User
  participant API as GET /api/messages/{id}/report
  participant DR as DeliveryReportBuilder
  participant RB as RingBuffer / JSONL

  U->>API: report for message_id
  API->>DR: build(message_id)
  DR->>RB: deliver events where message_id matches
  RB-->>DR: [{node:3, t:1.21, packet_id:"0:1"}, {node:5, t:1.42, packet_id:"0:1"}]
  loop each receiver
    DR->>RB: rx events for packet_id at node, then rx at prev_hop ... back to source
    RB-->>DR: path 0 → 1 → 3 (→ 5)
  end
  DR->>RB: members of group at send time (state.member) − receivers
  RB-->>DR: missed: []
  DR-->>API: {message_id, sent_at, receivers:[{node, t, path, hops}], missed, fg_at_send:[1,3]}
  API-->>U: 200 report
```

For a transfer, the report is per receiver `{received, total, missing:[...], complete, verified}` and the path is that of the first chunk.

## 4.4 What the UI shows (ties to `docs/mockups/03-messaging-panel.svg`)

| Event | Messaging panel | Network view |
|---|---|---|
| `tx` of first chunk / message at source | row appears with status *sent* | dot leaves node 0 |
| `deliver` at node | receiver chip turns green, shows `t` | node flashes |
| `transfer op=chunk` | progress bar `received/total` per receiver | — |
| `transfer op=complete` | download icon enabled | — |
| report row clicked | — | path edges highlighted |
