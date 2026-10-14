package odmrp.model;

import com.google.gson.JsonObject;

public final class JoinQueryHeader {
    public boolean piggybacked = true;
    public Double minLet = null;

    public JoinQueryHeader() {}

    public JoinQueryHeader(boolean piggybacked) {
        this.piggybacked = piggybacked;
    }

    public JsonObject toJson() {
        JsonObject o = new JsonObject();
        o.addProperty("piggybacked", piggybacked);
        o.add("mobility", null);
        if (minLet == null) {
            o.add("min_let", null);
        } else {
            o.addProperty("min_let", minLet);
        }
        return o;
    }

    public static JoinQueryHeader fromJson(JsonObject o) {
        if (o == null || o.isJsonNull()) {
            return null;
        }
        JoinQueryHeader h = new JoinQueryHeader();
        if (o.has("piggybacked")) {
            h.piggybacked = o.get("piggybacked").getAsBoolean();
        }
        if (o.has("min_let") && !o.get("min_let").isJsonNull()) {
            h.minLet = o.get("min_let").getAsDouble();
        }
        return h;
    }
}
