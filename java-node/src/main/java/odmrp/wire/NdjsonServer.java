package odmrp.wire;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;
import odmrp.model.Packet;
import odmrp.model.ProtocolParams;
import odmrp.protocol.OdmrpNode;

/** NDJSON-over-stdio host adapter (docs/external-node-contract.md). */
public final class NdjsonServer {
    private final OdmrpNode node = new OdmrpNode();
    private final BufferedReader in;
    private final BufferedWriter out;
    private boolean running = true;

    public NdjsonServer(BufferedReader in, BufferedWriter out) {
        this.in = in;
        this.out = out;
    }

    public void run() throws IOException {
        String line;
        while (running && (line = in.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) {
                continue;
            }
            JsonObject req;
            try {
                req = JsonParser.parseString(line).getAsJsonObject();
            } catch (Exception e) {
                writeError(-1, "malformed json: " + e.getMessage());
                continue;
            }
            handle(req);
        }
    }

    private void handle(JsonObject req) throws IOException {
        long id = req.has("id") ? req.get("id").getAsLong() : -1;
        String op = req.has("op") ? req.get("op").getAsString() : "";
        try {
            switch (op) {
                case "configure" -> {
                    int nodeId = req.get("node_id").getAsInt();
                    ProtocolParams params =
                            ProtocolParams.fromJson(
                                    req.has("params") && req.get("params").isJsonObject()
                                            ? req.getAsJsonObject("params")
                                            : null);
                    long seed = req.has("rng_seed") ? req.get("rng_seed").getAsLong() : 0L;
                    node.configure(nodeId, params, seed);
                    writeOk(id, null, null, null);
                }
                case "set_membership" -> {
                    String group = req.get("group").getAsString();
                    boolean member = req.get("member").getAsBoolean();
                    double now = req.get("now").getAsDouble();
                    List<Packet> pkts = node.setMembership(group, member, now);
                    writeOk(id, pkts, node.nextTimer(), null);
                }
                case "originate" -> {
                    String group = req.get("group").getAsString();
                    byte[] payload =
                            req.has("payload_b64") && !req.get("payload_b64").isJsonNull()
                                    ? Base64.getDecoder()
                                            .decode(req.get("payload_b64").getAsString())
                                    : new byte[0];
                    double now = req.get("now").getAsDouble();
                    List<Packet> pkts = node.originate(group, payload, now);
                    writeOk(id, pkts, node.nextTimer(), null);
                }
                case "receive" -> {
                    Packet packet = Packet.fromJson(req.getAsJsonObject("packet"));
                    int prev =
                            req.has("previous_hop")
                                    ? req.get("previous_hop").getAsInt()
                                    : req.get("prev_hop").getAsInt();
                    double now = req.get("now").getAsDouble();
                    List<Packet> pkts = node.receive(packet, prev, now);
                    writeOk(id, pkts, node.nextTimer(), null);
                }
                case "advance" -> {
                    double now = req.get("now").getAsDouble();
                    List<Packet> pkts = node.advance(now);
                    writeOk(id, pkts, node.nextTimer(), null);
                }
                case "next_timer" -> writeOk(id, null, node.nextTimer(), null);
                case "get_state" -> writeOk(id, null, null, node.getState().toJson());
                case "shutdown" -> {
                    writeOk(id, null, null, null);
                    running = false;
                }
                default -> writeError(id, "unknown op: " + op);
            }
        } catch (Exception e) {
            writeError(id, e.getMessage() == null ? e.toString() : e.getMessage());
        }
    }

    private void writeOk(long id, List<Packet> packets, Double nextTimer, JsonObject state)
            throws IOException {
        JsonObject resp = new JsonObject();
        resp.addProperty("id", id);
        resp.addProperty("ok", true);
        if (packets != null) {
            JsonArray arr = new JsonArray();
            for (Packet p : packets) {
                arr.add(p.toJson());
            }
            resp.add("packets", arr);
            // Alias used in sequence docs
            resp.add("tx", arr);
        }
        if (nextTimer != null) {
            resp.addProperty("at", nextTimer);
            resp.addProperty("next_timer", nextTimer);
        } else if (packets != null) {
            resp.add("at", null);
            resp.add("next_timer", null);
        }
        if (state != null) {
            resp.add("state", state);
        }
        write(resp);
    }

    private void writeError(long id, String error) throws IOException {
        JsonObject resp = new JsonObject();
        resp.addProperty("id", id);
        resp.addProperty("ok", false);
        resp.addProperty("error", error);
        write(resp);
    }

    private void write(JsonObject resp) throws IOException {
        out.write(resp.toString());
        out.write('\n');
        out.flush();
    }

    public static void main(String[] args) throws IOException {
        BufferedReader in =
                new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        BufferedWriter out =
                new BufferedWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8));
        new NdjsonServer(in, out).run();
    }
}
