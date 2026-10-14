package odmrp;

import odmrp.wire.NdjsonServer;

/** Entry point: NDJSON ODMRP node on stdio. */
public final class Main {
    public static void main(String[] args) throws Exception {
        NdjsonServer.main(args);
    }
}
