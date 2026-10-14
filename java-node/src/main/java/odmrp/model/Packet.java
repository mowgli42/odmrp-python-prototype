package odmrp.model;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class Packet {
    private static final AtomicInteger IDS = new AtomicInteger(1);

    public int id;
    public PacketKind kind;
    public int source;
    public String group;
    public int seq;
    public int previousHop;
    public int ttl = 32;
    public int hopCount = 0;
    public JoinQueryHeader joinQuery;
    public byte[] payload = new byte[0];
    public boolean ackRequest;
    public boolean fromFgNode;
    public List<JoinReplyEntry> entries = new ArrayList<>();

    public Packet() {
        this.id = IDS.getAndIncrement();
    }

    public static void resetIds(int start) {
        IDS.set(start);
    }

    public Packet copyForForward(int previousHop) {
        Packet p = new Packet();
        p.kind = this.kind;
        p.source = this.source;
        p.group = this.group;
        p.seq = this.seq;
        p.previousHop = previousHop;
        p.ttl = this.ttl - 1;
        p.hopCount = this.hopCount + 1;
        p.joinQuery = this.joinQuery;
        p.payload = this.payload;
        p.ackRequest = this.ackRequest;
        p.fromFgNode = this.fromFgNode;
        for (JoinReplyEntry e : this.entries) {
            p.entries.add(new JoinReplyEntry(e.sender, e.nextHop, e.routeExpiration));
        }
        return p;
    }

    public JsonObject toJson() {
        JsonObject d = new JsonObject();
        d.addProperty("id", id);
        d.addProperty("kind", kind.name());
        d.addProperty("source", source);
        d.addProperty("group", group);
        d.addProperty("seq", seq);
        d.addProperty("previous_hop", previousHop);
        d.addProperty("ttl", ttl);
        d.addProperty("hop_count", hopCount);
        if (kind == PacketKind.JOIN_QUERY || kind == PacketKind.DATA) {
            if (joinQuery != null) {
                d.add("join_query", joinQuery.toJson());
            } else {
                d.add("join_query", null);
            }
            d.addProperty("payload_len", payload.length);
            d.addProperty("payload_b64", Base64.getEncoder().encodeToString(payload));
            String preview;
            try {
                preview = new String(payload, 0, Math.min(64, payload.length), StandardCharsets.UTF_8);
            } catch (Exception e) {
                preview = "";
            }
            d.addProperty("payload_preview", preview);
        }
        if (kind == PacketKind.JOIN_REPLY) {
            d.addProperty("ack_request", ackRequest);
            d.addProperty("from_fg_node", fromFgNode);
            d.addProperty("count", entries.size());
            JsonArray arr = new JsonArray();
            for (JoinReplyEntry e : entries) {
                arr.add(e.toJson());
            }
            d.add("entries", arr);
        }
        return d;
    }

    public static Packet fromJson(JsonObject d) {
        Packet p = new Packet();
        if (d.has("id")) {
            p.id = d.get("id").getAsInt();
        }
        p.kind = PacketKind.fromString(d.get("kind").getAsString());
        p.source = d.get("source").getAsInt();
        p.group = d.get("group").getAsString();
        p.seq = d.get("seq").getAsInt();
        p.previousHop = d.get("previous_hop").getAsInt();
        if (d.has("ttl")) {
            p.ttl = d.get("ttl").getAsInt();
        }
        if (d.has("hop_count")) {
            p.hopCount = d.get("hop_count").getAsInt();
        }
        if (d.has("join_query") && d.get("join_query").isJsonObject()) {
            p.joinQuery = JoinQueryHeader.fromJson(d.getAsJsonObject("join_query"));
        }
        if (d.has("payload_b64") && !d.get("payload_b64").isJsonNull()) {
            p.payload = Base64.getDecoder().decode(d.get("payload_b64").getAsString());
        } else {
            p.payload = new byte[0];
        }
        if (d.has("ack_request")) {
            p.ackRequest = d.get("ack_request").getAsBoolean();
        }
        if (d.has("from_fg_node")) {
            p.fromFgNode = d.get("from_fg_node").getAsBoolean();
        }
        if (d.has("entries") && d.get("entries").isJsonArray()) {
            JsonArray arr = d.getAsJsonArray("entries");
            for (int i = 0; i < arr.size(); i++) {
                p.entries.add(JoinReplyEntry.fromJson(arr.get(i).getAsJsonObject()));
            }
        }
        return p;
    }

    public static Packet makeDataWithJq(
            int source, String group, int seq, byte[] payload, int ttl, boolean piggybacked) {
        Packet p = new Packet();
        p.kind = PacketKind.JOIN_QUERY;
        p.source = source;
        p.group = group;
        p.seq = seq;
        p.previousHop = source;
        p.ttl = ttl;
        p.hopCount = 0;
        p.joinQuery = new JoinQueryHeader(piggybacked);
        p.payload = payload != null ? payload : new byte[0];
        return p;
    }

    public static Packet makeJoinReply(
            int source,
            String group,
            int seq,
            int previousHop,
            List<JoinReplyEntry> entries,
            boolean fromFgNode,
            int ttl) {
        Packet p = new Packet();
        p.kind = PacketKind.JOIN_REPLY;
        p.source = source;
        p.group = group;
        p.seq = seq;
        p.previousHop = previousHop;
        p.ttl = ttl;
        p.hopCount = 0;
        p.fromFgNode = fromFgNode;
        p.entries = new ArrayList<>(entries);
        return p;
    }
}
