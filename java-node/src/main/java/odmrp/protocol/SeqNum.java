package odmrp.protocol;

public final class SeqNum {
    private static final long MOD = 1L << 32;

    private SeqNum() {}

    public static int normalize(int n) {
        return (int) (Integer.toUnsignedLong(n) % MOD);
    }

    public static int nextSeq(int n) {
        return normalize(n + 1);
    }
}
