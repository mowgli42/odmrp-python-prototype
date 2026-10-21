import { api } from '../api'

export type TraceEvent = {
  t: number
  seq: number
  node: number
  kind: string
  [k: string]: unknown
}

export type NodeState = {
  id: number
  pos: { x: number; y: number }
  range: number
  members: string[]
  routes: Record<string, { next_hop: number; seq: number; expires_at: number }>
  forwarding_groups: Record<
    string,
    { expires_at: number; refreshed_by: number[]; last_refresh?: number }
  >
  inbox: Array<{ message_id: string; body?: string; group: string; source: number }>
  fg: string[]
  sessions: Array<{
    group: string
    next_seq: number
    mesh_established: boolean
    next_refresh_at?: number | null
    last_data_at?: number
  }>
  impl?: string
  log?: string
}

export type MeshHealth = 'idle' | 'forming' | 'established' | 'expiring'

class SimStore {
  sim = $state({ t: 0, mode: 'paused', speed: 1, seed: 42, scenario: null as string | null })
  topology = $state<{ nodes: Array<{ id: number; x: number; y: number; range: number }>; links: number[][] }>({
    nodes: [],
    links: [],
  })
  nodes = $state<Record<string, NodeState>>({})
  events = $state<TraceEvent[]>([])
  /** Bumps on every events mutation so Trace `$derived` always re-runs. */
  eventsEpoch = $state(0)
  selected = $state<number | null>(null)
  selectedGroup = $state('demo')
  packets = $state<Array<{ id: number; from: number; to: number; kind: string; born: number }>>([])
  connected = $state(false)
  error = $state<string | null>(null)
  lastMessageId = $state<string | null>(null)
  report = $state<any>(null)
  drops = $state({ duplicate: 0, not_fg: 0, other: 0 })
  deliveries = $state(0)
  lastEvent = $state<TraceEvent | null>(null)
  flashDrops = $state<Array<{ node: number; reason: string; born: number }>>([])
  scenarioName = $state('dynamic-mesh')
  scenarios = $state<Array<{ name: string; nodes: number; description: string; has_mobility: boolean; native_nodes: number }>>([])

  #ws: WebSocket | null = null
  #lastSeq = 0
  #wsGen = 0
  #seenSeq = new Set<number>()

  get memberIds(): number[] {
    const g = this.selectedGroup
    return Object.values(this.nodes)
      .filter((n) => n.members?.includes(g))
      .map((n) => n.id)
      .sort((a, b) => a - b)
  }

  get fgIds(): number[] {
    const g = this.selectedGroup
    return Object.values(this.nodes)
      .filter((n) => n.fg?.includes(g) || !!n.forwarding_groups?.[g])
      .map((n) => n.id)
      .sort((a, b) => a - b)
  }

  get sourceIds(): number[] {
    const g = this.selectedGroup
    return Object.values(this.nodes)
      .filter((n) => n.sessions?.some((s) => s.group === g))
      .map((n) => n.id)
      .sort((a, b) => a - b)
  }

  get nextRefreshAt(): number | null {
    const g = this.selectedGroup
    let soonest: number | null = null
    for (const n of Object.values(this.nodes)) {
      for (const s of n.sessions || []) {
        if (s.group !== g || s.next_refresh_at == null) continue
        if (soonest == null || s.next_refresh_at < soonest) soonest = s.next_refresh_at
      }
    }
    return soonest
  }

  get softestFgExpiresAt(): number | null {
    const g = this.selectedGroup
    let soonest: number | null = null
    for (const n of Object.values(this.nodes)) {
      const fg = n.forwarding_groups?.[g]
      if (!fg) continue
      if (soonest == null || fg.expires_at < soonest) soonest = fg.expires_at
    }
    return soonest
  }

  get meshHealth(): MeshHealth {
    const members = this.memberIds.length
    const fg = this.fgIds.length
    const sources = this.sourceIds.length
    if (sources === 0 && members === 0) return 'idle'
    if (sources > 0 && fg === 0) return 'forming'
    const soft = this.softestFgExpiresAt
    if (soft != null && soft - this.sim.t < 2.5) return 'expiring'
    if (fg > 0 || this.sourceIds.some((id) => {
      const n = this.nodes[String(id)]
      return n?.sessions?.some((s) => s.group === this.selectedGroup && s.mesh_established)
    })) {
      return 'established'
    }
    return 'forming'
  }

  get packetsInFlight(): number {
    const now = performance.now()
    return this.packets.filter((p) => now - p.born < 900).length
  }

  #clearTrace() {
    this.events = []
    this.eventsEpoch += 1
    this.packets = []
    this.report = null
    this.drops = { duplicate: 0, not_fg: 0, other: 0 }
    this.deliveries = 0
    this.lastEvent = null
    this.flashDrops = []
    this.#seenSeq.clear()
    this.#lastSeq = 0
  }

  async bootstrap() {
    try {
      const listed = await api.scenarios()
      this.scenarios = listed.scenarios
      await this.loadScenario(this.scenarioName)
    } catch (e) {
      this.error = String(e)
    }
  }

  async loadScenario(name: string) {
    this.scenarioName = name
    await api.loadScenario(name)
    const snap = await api.network()
    this.applySnapshot(snap)
    this.#clearTrace()
    // Replay the whole ring so the Trace panel shows mesh-formation events
    // that happened during scenario load (before the socket opened).
    this.connectWs()
  }

  applySnapshot(snap: any) {
    this.sim = snap.sim
    this.topology = snap.topology
    this.nodes = snap.nodes
  }

  connectWs() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${location.host}/ws?after_seq=${this.#lastSeq}`
    const gen = ++this.#wsGen
    const prev = this.#ws
    this.#ws = null
    // Drop prior socket without triggering its reconnect timer.
    if (prev) {
      prev.onclose = null
      prev.close()
    }
    const ws = new WebSocket(url)
    this.#ws = ws
    ws.onopen = () => {
      if (gen !== this.#wsGen) return
      this.connected = true
      this.error = null
    }
    ws.onclose = () => {
      if (gen !== this.#wsGen) return
      this.connected = false
      setTimeout(() => {
        if (gen === this.#wsGen) this.connectWs()
      }, 1500)
    }
    ws.onerror = () => {
      if (gen !== this.#wsGen) return
      this.error = 'WebSocket error'
    }
    ws.onmessage = (ev) => {
      if (gen !== this.#wsGen) return
      const msg = JSON.parse(ev.data)
      if (msg.type === 'snapshot') {
        this.applySnapshot(msg)
      } else if (msg.type === 'events') {
        this.ingestEvents(msg.events as TraceEvent[])
      } else if (msg.type === 'node') {
        this.nodes = { ...this.nodes, [String(msg.id)]: msg.state }
      } else if (msg.type === 'sim') {
        this.sim = msg.sim
      } else if (msg.type === 'topology') {
        this.topology = msg.topology
        this.nodes = msg.nodes
        if (msg.sim) this.sim = msg.sim
      }
    }
  }

  ingestEvents(events: TraceEvent[]) {
    if (!events.length) return
    const fresh = events.filter((e) => !this.#seenSeq.has(e.seq))
    if (!fresh.length) return
    for (const e of fresh) this.#seenSeq.add(e.seq)
    this.events = [...this.events, ...fresh].slice(-1200)
    this.eventsEpoch += 1
    for (const e of fresh) {
      this.#lastSeq = Math.max(this.#lastSeq, e.seq)
      this.lastEvent = e
      if (e.kind === 'tx' && e.packet && Array.isArray(e.neighbors)) {
        const pkt = e.packet as { id: number; kind: string }
        for (const nb of e.neighbors as number[]) {
          this.packets = [
            ...this.packets,
            { id: pkt.id, from: e.node, to: nb, kind: pkt.kind, born: performance.now() },
          ].slice(-80)
        }
      }
      if (e.kind === 'deliver') {
        this.deliveries += 1
      }
      if (e.kind === 'drop') {
        const reason = String(e.reason ?? 'other')
        if (reason === 'duplicate') this.drops = { ...this.drops, duplicate: this.drops.duplicate + 1 }
        else if (reason === 'not_fg') this.drops = { ...this.drops, not_fg: this.drops.not_fg + 1 }
        else this.drops = { ...this.drops, other: this.drops.other + 1 }
        this.flashDrops = [
          ...this.flashDrops,
          { node: e.node, reason, born: performance.now() },
        ].slice(-24)
      }
      // topology frames arrive via WS `type: topology` (see connectWs)
    }
  }

  async step(dt = 0.1) {
    const snap = await api.step(dt)
    this.applySnapshot(snap)
  }

  async run() {
    await api.run()
    this.sim = { ...this.sim, mode: 'running' }
  }

  async pause() {
    await api.pause()
    this.sim = { ...this.sim, mode: 'paused' }
  }

  async reset() {
    await api.reset()
    await this.loadScenario(this.scenarioName)
  }

  async send(text: string) {
    const source = this.sourceIds[0] ?? 0
    const res = await api.sendText(source, this.selectedGroup, text)
    this.lastMessageId = res.message_id
    this.report = await api.report(res.message_id)
    const snap = await api.network()
    this.applySnapshot(snap)
  }

  select(id: number | null) {
    this.selected = id
  }
}

export const sim = new SimStore()
