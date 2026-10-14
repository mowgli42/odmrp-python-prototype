package odmrp.protocol;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import odmrp.model.JoinQueryHeader;
import odmrp.model.JoinReplyEntry;
import odmrp.model.Packet;
import odmrp.model.PacketKind;
import odmrp.model.ProtocolParams;
import odmrp.model.StateModels.FGEntry;
import odmrp.model.StateModels.InboxItem;
import odmrp.model.StateModels.NodeState;
import odmrp.model.StateModels.Position;
import odmrp.model.StateModels.RouteEntry;
import odmrp.model.StateModels.SourceSession;

/** Java port of PythonODMRPNode — same control-plane behaviour for differential tests. */
public final class OdmrpNode {
    private static final class PendingJR {
        final String group;
        final List<JoinReplyEntry> entries;
        final double due;

        PendingJR(String group, List<JoinReplyEntry> entries, double due) {
            this.group = group;
            this.entries = entries;
            this.due = due;
        }
    }

    private int nodeId = -1;
    private ProtocolParams params = new ProtocolParams();
    private Position pos = new Position(0, 0);
    private double range = 130.0;
    private final Set<String> members = new HashSet<>();
    private final Map<Integer, RouteEntry> routes = new LinkedHashMap<>();
    private final Map<String, FGEntry> fg = new LinkedHashMap<>();
    private MessageCache cache = new MessageCache(1024);
    private final Map<String, SourceSession> sessions = new LinkedHashMap<>();
    private final List<InboxItem> inbox = new ArrayList<>();
    private int jrSeq = 0;
    private final List<PendingJR> pendingJr = new ArrayList<>();
    private final Map<String, Set<Long>> jrSent = new HashMap<>();
    private final Map<String, List<byte[]>> queuedPayloads = new HashMap<>();
    private double now;

    public void configure(int nodeId, ProtocolParams params, long rngSeed) {
        this.nodeId = nodeId;
        this.params = params != null ? params : new ProtocolParams();
        this.cache = new MessageCache(this.params.messageCacheSize);
        // rngSeed reserved for future jitter inside the node; medium owns jitter today.
    }

    public List<Packet> setMembership(String group, boolean member, double now) {
        this.now = now;
        if (member) {
            members.add(group);
        } else {
            members.remove(group);
        }
        return List.of();
    }

    public List<Packet> originate(String group, byte[] payload, double now) {
        this.now = now;
        SourceSession session = sessions.get(group);
        if (session == null) {
            session = new SourceSession(group);
            sessions.put(group, session);
        }
        session.lastDataAt = now;
        queuedPayloads.computeIfAbsent(group, g -> new ArrayList<>()).add(payload);
        return emitJoinQuery(group, now, true);
    }

    public List<Packet> receive(Packet packet, int previousHop, double now) {
        this.now = now;
        if (packet.kind == PacketKind.JOIN_REPLY) {
            return handleJoinReply(packet, previousHop, now);
        }
        if (packet.kind == PacketKind.JOIN_QUERY || packet.kind == PacketKind.DATA) {
            return handleDataOrJq(packet, previousHop, now);
        }
        return List.of();
    }

    public List<Packet> advance(double now) {
        this.now = now;
        List<Packet> out = new ArrayList<>();
        List<PendingJR> still = new ArrayList<>();
        for (PendingJR p : pendingJr) {
            if (p.due <= now + 1e-12) {
                out.addAll(sendJoinReply(p.group, p.entries, now, false));
            } else {
                still.add(p);
            }
        }
        pendingJr.clear();
        pendingJr.addAll(still);

        List<Integer> expiredRoutes = new ArrayList<>();
        for (Map.Entry<Integer, RouteEntry> e : routes.entrySet()) {
            if (e.getValue().expiresAt <= now) {
                expiredRoutes.add(e.getKey());
            }
        }
        for (int s : expiredRoutes) {
            routes.remove(s);
        }

        List<String> expiredFg = new ArrayList<>();
        for (Map.Entry<String, FGEntry> e : fg.entrySet()) {
            if (e.getValue().expiresAt <= now) {
                expiredFg.add(e.getKey());
            }
        }
        for (String g : expiredFg) {
            fg.remove(g);
            jrSent.remove(g);
        }

        for (Map.Entry<String, SourceSession> e : new ArrayList<>(sessions.entrySet())) {
            String group = e.getKey();
            SourceSession session = e.getValue();
            if (session.nextRefreshAt != null && session.nextRefreshAt <= now + 1e-12) {
                double idle = now - session.lastDataAt;
                List<byte[]> q = queuedPayloads.get(group);
                if (idle > params.sourceIdleTimeout && (q == null || q.isEmpty())) {
                    session.nextRefreshAt = null;
                    continue;
                }
                out.addAll(emitJoinQuery(group, now, false));
            }
        }
        return out;
    }

    public Double nextTimer() {
        List<Double> times = new ArrayList<>();
        for (PendingJR p : pendingJr) {
            times.add(p.due);
        }
        for (RouteEntry e : routes.values()) {
            times.add(e.expiresAt);
        }
        for (FGEntry e : fg.values()) {
            times.add(e.expiresAt);
        }
        for (SourceSession s : sessions.values()) {
            if (s.nextRefreshAt != null) {
                times.add(s.nextRefreshAt);
            }
        }
        if (times.isEmpty()) {
            return null;
        }
        double min = times.get(0);
        for (double t : times) {
            if (t < min) {
                min = t;
            }
        }
        return min;
    }

    public NodeState getState() {
        NodeState st = new NodeState();
        st.id = nodeId;
        st.pos = new Position(pos.x, pos.y);
        st.range = range;
        st.members = new HashSet<>(members);
        st.routes = new LinkedHashMap<>(routes);
        st.forwardingGroups = new LinkedHashMap<>(fg);
        st.messageCacheSize = cache.size();
        st.sessions = new ArrayList<>(sessions.values());
        st.inbox = new ArrayList<>(inbox);
        return st;
    }

    public void setPos(double x, double y) {
        this.pos = new Position(x, y);
    }

    public void setRange(double range) {
        this.range = range;
    }

    private List<Packet> emitJoinQuery(String group, double now, boolean forcePayload) {
        SourceSession session = sessions.computeIfAbsent(group, SourceSession::new);
        List<byte[]> queue = queuedPayloads.computeIfAbsent(group, g -> new ArrayList<>());
        byte[] payload;
        boolean piggybacked;
        if (forcePayload || !queue.isEmpty()) {
            payload = queue.isEmpty() ? new byte[0] : queue.remove(0);
            piggybacked = true;
        } else {
            payload = new byte[0];
            piggybacked = false;
        }
        int seq = session.nextSeq;
        session.nextSeq = SeqNum.nextSeq(seq);
        if (payload.length > 0) {
            session.lastDataAt = now;
        }
        session.nextRefreshAt = now + params.routeRefreshInterval;
        cache.add(nodeId, seq, now);
        Packet pkt =
                Packet.makeDataWithJq(nodeId, group, seq, payload, params.joinQueryTtl, piggybacked);
        jrSent.remove(group);
        return List.of(pkt);
    }

    private List<Packet> handleDataOrJq(Packet packet, int previousHop, double now) {
        List<Packet> out = new ArrayList<>();
        boolean hasJq = packet.joinQuery != null || packet.kind == PacketKind.JOIN_QUERY;

        if (cache.contains(packet.source, packet.seq)) {
            return out;
        }
        cache.add(packet.source, packet.seq, now);

        if (hasJq) {
            routes.put(
                    packet.source,
                    new RouteEntry(previousHop, packet.seq, now + params.routeTimeout));
            if (members.contains(packet.group)) {
                deliver(packet, now);
                JoinReplyEntry entry = new JoinReplyEntry(packet.source, previousHop);
                double due = now + params.jrDelay;
                pendingJr.add(new PendingJR(packet.group, List.of(entry), due));
            }
            if (packet.ttl > 1) {
                Packet fwd = packet.copyForForward(nodeId);
                if (packet.joinQuery != null) {
                    fwd.joinQuery = new JoinQueryHeader(packet.joinQuery.piggybacked);
                }
                out.add(fwd);
            }
            return out;
        }

        if (members.contains(packet.group)) {
            deliver(packet, now);
        }
        if (isFg(packet.group, packet.source) && packet.ttl > 1) {
            out.add(packet.copyForForward(nodeId));
        }
        return out;
    }

    private List<Packet> handleJoinReply(Packet packet, int previousHop, double now) {
        List<JoinReplyEntry> matched = new ArrayList<>();
        for (JoinReplyEntry e : packet.entries) {
            if (e.nextHop == nodeId) {
                matched.add(e);
            }
        }
        if (matched.isEmpty()) {
            return List.of();
        }

        for (JoinReplyEntry m : matched) {
            if (m.sender == nodeId) {
                SourceSession sess = sessions.get(packet.group);
                if (sess != null) {
                    sess.meshEstablished = true;
                }
            }
        }

        List<JoinReplyEntry> forwardMatched = new ArrayList<>();
        for (JoinReplyEntry m : matched) {
            if (m.sender != nodeId) {
                forwardMatched.add(m);
            }
        }
        if (forwardMatched.isEmpty()) {
            return List.of();
        }

        FGEntry entry = fg.get(packet.group);
        if (entry == null) {
            entry = new FGEntry(now + params.fgTimeout, now);
            fg.put(packet.group, entry);
        } else {
            entry.expiresAt = now + params.fgTimeout;
            entry.lastRefresh = now;
        }
        for (JoinReplyEntry m : forwardMatched) {
            entry.refreshedBy.add(m.sender);
        }

        List<JoinReplyEntry> upstream = new ArrayList<>();
        for (JoinReplyEntry m : forwardMatched) {
            RouteEntry route = routes.get(m.sender);
            if (route == null) {
                continue;
            }
            upstream.add(new JoinReplyEntry(m.sender, route.nextHop));
        }
        if (upstream.isEmpty()) {
            return List.of();
        }

        Set<Long> sig = signature(upstream);
        if (Objects.equals(jrSent.get(packet.group), sig)) {
            return List.of();
        }
        return sendJoinReply(packet.group, upstream, now, true);
    }

    private List<Packet> sendJoinReply(
            String group, List<JoinReplyEntry> entries, double now, boolean fromFg) {
        Set<Long> sig = signature(entries);
        if (Objects.equals(jrSent.get(group), sig)) {
            return List.of();
        }
        jrSent.put(group, sig);
        jrSeq = SeqNum.nextSeq(jrSeq);
        boolean fromFgNode = fromFg || fg.containsKey(group);
        Packet pkt =
                Packet.makeJoinReply(
                        nodeId, group, jrSeq, nodeId, entries, fromFgNode, params.joinQueryTtl);
        return List.of(pkt);
    }

    private static Set<Long> signature(List<JoinReplyEntry> entries) {
        Set<Long> sig = new HashSet<>();
        for (JoinReplyEntry e : entries) {
            sig.add((((long) e.sender) << 32) | (e.nextHop & 0xffffffffL));
        }
        return sig;
    }

    private boolean isFg(String group, int source) {
        if ("source_group".equals(params.fgScope)) {
            String key = source + ":" + group;
            return fg.containsKey(key) || fg.containsKey(group);
        }
        return fg.containsKey(group);
    }

    private void deliver(Packet packet, double now) {
        if (packet.payload == null || packet.payload.length == 0) {
            return;
        }
        AppPayload app = AppPayload.decode(packet.payload);
        InboxItem item = new InboxItem();
        item.messageId = app.messageId;
        item.group = packet.group;
        item.source = packet.source;
        item.appKind = app.kind;
        item.body = app.body;
        item.transferId = app.transferId;
        item.index = app.index;
        item.total = app.total;
        item.t = now;
        inbox.add(item);
    }
}
