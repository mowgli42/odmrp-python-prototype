package odmrp.protocol;

import java.util.LinkedHashMap;
import java.util.Map;

public final class MessageCache {
    private final int capacity;
    private final LinkedHashMap<Long, Double> store = new LinkedHashMap<>(16, 0.75f, true);

    public MessageCache(int capacity) {
        this.capacity = capacity;
    }

    public int size() {
        return store.size();
    }

    private static long key(int source, int seq) {
        return (((long) source) << 32) | (SeqNum.normalize(seq) & 0xffffffffL);
    }

    public boolean contains(int source, int seq) {
        return store.containsKey(key(source, seq));
    }

    public void add(int source, int seq, double now) {
        long k = key(source, seq);
        store.put(k, now);
        while (store.size() > capacity) {
            Map.Entry<Long, Double> eldest = store.entrySet().iterator().next();
            store.remove(eldest.getKey());
        }
    }
}
