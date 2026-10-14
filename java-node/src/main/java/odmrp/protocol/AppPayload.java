package odmrp.protocol;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/** Minimal AppPayload encode/decode matching Python odmrp_sim.model.app_payload. */
public final class AppPayload {
    public String kind;
    public String messageId;
    public String body;
    public String transferId;
    public Integer index;
    public Integer total;

    public static AppPayload decode(byte[] raw) {
        AppPayload a = new AppPayload();
        try {
            if (raw.length >= 4) {
                int n =
                        ((raw[0] & 0xff) << 24)
                                | ((raw[1] & 0xff) << 16)
                                | ((raw[2] & 0xff) << 8)
                                | (raw[3] & 0xff);
                if (n >= 2 && n <= raw.length - 4 && raw[4] == '{') {
                    String meta = new String(raw, 4, n, StandardCharsets.UTF_8);
                    JsonObject o = JsonParser.parseString(meta).getAsJsonObject();
                    fill(a, o);
                    return a;
                }
            }
            JsonObject o =
                    JsonParser.parseString(new String(raw, StandardCharsets.UTF_8)).getAsJsonObject();
            fill(a, o);
            return a;
        } catch (Exception e) {
            a.kind = "text";
            a.messageId = "raw-" + Arrays.hashCode(raw);
            a.body = new String(raw, StandardCharsets.UTF_8);
            return a;
        }
    }

    private static void fill(AppPayload a, JsonObject o) {
        a.kind = o.get("kind").getAsString();
        a.messageId = o.get("message_id").getAsString();
        if (o.has("body") && !o.get("body").isJsonNull()) {
            a.body = o.get("body").getAsString();
        }
        if (o.has("transfer_id") && !o.get("transfer_id").isJsonNull()) {
            a.transferId = o.get("transfer_id").getAsString();
        }
        if (o.has("index") && !o.get("index").isJsonNull()) {
            a.index = o.get("index").getAsInt();
        }
        if (o.has("total") && !o.get("total").isJsonNull()) {
            a.total = o.get("total").getAsInt();
        }
    }
}
