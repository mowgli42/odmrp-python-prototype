package odmrp.model;

public enum PacketKind {
    JOIN_QUERY,
    JOIN_REPLY,
    DATA;

    public static PacketKind fromString(String s) {
        return PacketKind.valueOf(s);
    }
}
