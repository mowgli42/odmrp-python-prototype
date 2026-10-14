package odmrp.model;

import com.google.gson.JsonObject;

public final class ProtocolParams {
    public double routeRefreshInterval = 3.0;
    public double fgTimeout = 9.0;
    public double routeTimeout = 9.0;
    public double sourceIdleTimeout = 3.0;
    public int joinQueryTtl = 32;
    public double jqJitter = 0.010;
    public double jrDelay = 0.025;
    public double hopDelay = 0.001;
    public int messageCacheSize = 1024;
    public String fgScope = "group";
    public int chunkSize = 1024;

    public static ProtocolParams fromJson(JsonObject o) {
        ProtocolParams p = new ProtocolParams();
        if (o == null) {
            return p;
        }
        if (o.has("route_refresh_interval")) {
            p.routeRefreshInterval = o.get("route_refresh_interval").getAsDouble();
        }
        if (o.has("fg_timeout")) {
            p.fgTimeout = o.get("fg_timeout").getAsDouble();
        }
        if (o.has("route_timeout")) {
            p.routeTimeout = o.get("route_timeout").getAsDouble();
        }
        if (o.has("source_idle_timeout")) {
            p.sourceIdleTimeout = o.get("source_idle_timeout").getAsDouble();
        }
        if (o.has("join_query_ttl")) {
            p.joinQueryTtl = o.get("join_query_ttl").getAsInt();
        }
        if (o.has("jq_jitter")) {
            p.jqJitter = o.get("jq_jitter").getAsDouble();
        }
        if (o.has("jr_delay")) {
            p.jrDelay = o.get("jr_delay").getAsDouble();
        }
        if (o.has("hop_delay")) {
            p.hopDelay = o.get("hop_delay").getAsDouble();
        }
        if (o.has("message_cache_size")) {
            p.messageCacheSize = o.get("message_cache_size").getAsInt();
        }
        if (o.has("fg_scope") && !o.get("fg_scope").isJsonNull()) {
            p.fgScope = o.get("fg_scope").getAsString();
        }
        if (o.has("chunk_size")) {
            p.chunkSize = o.get("chunk_size").getAsInt();
        }
        return p;
    }
}
