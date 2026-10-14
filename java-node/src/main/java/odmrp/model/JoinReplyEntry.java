package odmrp.model;

import com.google.gson.JsonObject;

public final class JoinReplyEntry {
    public int sender;
    public int nextHop;
    public Double routeExpiration;

    public JoinReplyEntry(int sender, int nextHop) {
        this.sender = sender;
        this.nextHop = nextHop;
    }

    public JoinReplyEntry(int sender, int nextHop, Double routeExpiration) {
        this.sender = sender;
        this.nextHop = nextHop;
        this.routeExpiration = routeExpiration;
    }

    public JsonObject toJson() {
        JsonObject o = new JsonObject();
        o.addProperty("sender", sender);
        o.addProperty("next_hop", nextHop);
        if (routeExpiration == null) {
            o.add("route_expiration", null);
        } else {
            o.addProperty("route_expiration", routeExpiration);
        }
        return o;
    }

    public static JoinReplyEntry fromJson(JsonObject o) {
        Double exp = null;
        if (o.has("route_expiration") && !o.get("route_expiration").isJsonNull()) {
            exp = o.get("route_expiration").getAsDouble();
        }
        return new JoinReplyEntry(o.get("sender").getAsInt(), o.get("next_hop").getAsInt(), exp);
    }
}
