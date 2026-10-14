package odmrp.model;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

public final class StateModels {
    private StateModels() {}

    public static final class Position {
        public double x;
        public double y;

        public Position(double x, double y) {
            this.x = x;
            this.y = y;
        }

        public JsonObject toJson() {
            JsonObject o = new JsonObject();
            o.addProperty("x", x);
            o.addProperty("y", y);
            return o;
        }
    }

    public static final class RouteEntry {
        public int nextHop;
        public int seq;
        public double expiresAt;

        public RouteEntry(int nextHop, int seq, double expiresAt) {
            this.nextHop = nextHop;
            this.seq = seq;
            this.expiresAt = expiresAt;
        }

        public JsonObject toJson() {
            JsonObject o = new JsonObject();
            o.addProperty("next_hop", nextHop);
            o.addProperty("seq", seq);
            o.addProperty("expires_at", expiresAt);
            return o;
        }
    }

    public static final class FGEntry {
        public double expiresAt;
        public Set<Integer> refreshedBy = new LinkedHashSet<>();
        public double lastRefresh;

        public FGEntry(double expiresAt, double lastRefresh) {
            this.expiresAt = expiresAt;
            this.lastRefresh = lastRefresh;
        }

        public JsonObject toJson() {
            JsonObject o = new JsonObject();
            o.addProperty("expires_at", expiresAt);
            JsonArray arr = new JsonArray();
            List<Integer> sorted = new ArrayList<>(refreshedBy);
            sorted.sort(Integer::compareTo);
            for (int id : sorted) {
                arr.add(id);
            }
            o.add("refreshed_by", arr);
            o.addProperty("last_refresh", lastRefresh);
            return o;
        }
    }

    public static final class SourceSession {
        public String group;
        public int nextSeq = 1;
        public double lastDataAt;
        public Double nextRefreshAt;
        public boolean meshEstablished;

        public SourceSession(String group) {
            this.group = group;
        }

        public JsonObject toJson() {
            JsonObject o = new JsonObject();
            o.addProperty("group", group);
            o.addProperty("next_seq", nextSeq);
            o.addProperty("last_data_at", lastDataAt);
            if (nextRefreshAt == null) {
                o.add("next_refresh_at", null);
            } else {
                o.addProperty("next_refresh_at", nextRefreshAt);
            }
            o.addProperty("mesh_established", meshEstablished);
            return o;
        }
    }

    public static final class InboxItem {
        public String messageId;
        public String group;
        public int source;
        public String appKind;
        public String body;
        public String transferId;
        public Integer index;
        public Integer total;
        public double t;

        public JsonObject toJson() {
            JsonObject o = new JsonObject();
            o.addProperty("message_id", messageId);
            o.addProperty("group", group);
            o.addProperty("source", source);
            o.addProperty("app_kind", appKind);
            if (body == null) {
                o.add("body", null);
            } else {
                o.addProperty("body", body);
            }
            if (transferId == null) {
                o.add("transfer_id", null);
            } else {
                o.addProperty("transfer_id", transferId);
            }
            if (index == null) {
                o.add("index", null);
            } else {
                o.addProperty("index", index);
            }
            if (total == null) {
                o.add("total", null);
            } else {
                o.addProperty("total", total);
            }
            o.addProperty("t", t);
            return o;
        }
    }

    public static final class NodeState {
        public int id;
        public Position pos = new Position(0, 0);
        public double range = 130.0;
        public Set<String> members = new LinkedHashSet<>();
        public Map<Integer, RouteEntry> routes = new LinkedHashMap<>();
        public Map<String, FGEntry> forwardingGroups = new LinkedHashMap<>();
        public int messageCacheSize;
        public List<SourceSession> sessions = new ArrayList<>();
        public List<InboxItem> inbox = new ArrayList<>();

        public JsonObject toJson() {
            JsonObject o = new JsonObject();
            o.addProperty("id", id);
            o.add("pos", pos.toJson());
            o.addProperty("range", range);
            JsonArray mem = new JsonArray();
            for (String g : new TreeSet<>(members)) {
                mem.add(g);
            }
            o.add("members", mem);
            JsonObject routesObj = new JsonObject();
            for (Map.Entry<Integer, RouteEntry> e : routes.entrySet()) {
                routesObj.add(String.valueOf(e.getKey()), e.getValue().toJson());
            }
            o.add("routes", routesObj);
            JsonObject fgObj = new JsonObject();
            for (Map.Entry<String, FGEntry> e : forwardingGroups.entrySet()) {
                fgObj.add(e.getKey(), e.getValue().toJson());
            }
            o.add("forwarding_groups", fgObj);
            o.add("last_seq_by_source", new JsonObject());
            o.addProperty("message_cache_size", messageCacheSize);
            JsonArray sess = new JsonArray();
            for (SourceSession s : sessions) {
                sess.add(s.toJson());
            }
            o.add("sessions", sess);
            JsonArray inb = new JsonArray();
            for (InboxItem i : inbox) {
                inb.add(i.toJson());
            }
            o.add("inbox", inb);
            JsonArray fgKeys = new JsonArray();
            for (String g : new TreeSet<>(forwardingGroups.keySet())) {
                fgKeys.add(g);
            }
            o.add("fg", fgKeys);
            return o;
        }
    }
}
