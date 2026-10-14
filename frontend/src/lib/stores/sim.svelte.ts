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
  forwarding_groups: Record<string, { expires_at: number; refreshed_by: number[] }>
  inbox: Array<{ message_id: string; body?: string; group: string; source: number }>
  fg: string[]
  sessions: Array<{ group: string; next_seq: number; mesh_established: boolean }>
}

class SimStore {
  sim = $state({ t: 0, mode: 'paused', speed: 1, seed: 42, scenario: null as string | null })
  topology = $state<{ nodes: Array<{ id: number; x: number; y: number; range: number }>; links: number[][] }>({
    nodes: [],
    links: [],
  })
  nodes = $state<Record<string, NodeState>>({})
  events = $state<TraceEvent[]>([])
  selected = $state<number | null>(null)
  selectedGroup = $state('demo')
  packets = $state<Array<{ id: number; from: number; to: number; kind: string; born: number }>>([])
  connected = $state(false)
  error = $state<string | null>(null)
  lastMessageId = $state<string | null>(null)
  report = $state<any>(null)

  #ws: WebSocket | null = null
  #lastSeq = 0

  async bootstrap() {
    try {
      await api.loadScenario('basic-mesh')
      const snap = await api.network()
      this.applySnapshot(snap)
      this.connectWs()
    } catch (e) {
      this.error = String(e)
    }
  }

  applySnapshot(snap: any) {
    this.sim = snap.sim
    this.topology = snap.topology
    this.nodes = snap.nodes
    this.#lastSeq = snap.last_seq ?? 0
  }

  connectWs() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${location.host}/ws?after_seq=${this.#lastSeq}`
    this.#ws?.close()
    const ws = new WebSocket(url)
    this.#ws = ws
    ws.onopen = () => {
      this.connected = true
      this.error = null
    }
    ws.onclose = () => {
      this.connected = false
      setTimeout(() => this.connectWs(), 1500)
    }
    ws.onerror = () => {
      this.error = 'WebSocket error'
    }
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'snapshot') {
        this.applySnapshot(msg)
      } else if (msg.type === 'events') {
        this.ingestEvents(msg.events as TraceEvent[])
      } else if (msg.type === 'node') {
        this.nodes = { ...this.nodes, [String(msg.id)]: msg.state }
      } else if (msg.type === 'sim') {
        this.sim = msg.sim
      }
    }
  }

  ingestEvents(events: TraceEvent[]) {
    this.events = [...this.events, ...events].slice(-500)
    for (const e of events) {
      this.#lastSeq = Math.max(this.#lastSeq, e.seq)
      if (e.kind === 'tx' && e.packet && Array.isArray(e.neighbors)) {
        const pkt = e.packet as { id: number; kind: string }
        for (const nb of e.neighbors as number[]) {
          this.packets = [
            ...this.packets,
            { id: pkt.id, from: e.node, to: nb, kind: pkt.kind, born: performance.now() },
          ].slice(-80)
        }
      }
      if (e.kind === 'topology') {
        // refresh topology from REST lightly
        api.network().then((snap) => {
          this.topology = snap.topology
          this.nodes = snap.nodes
          this.sim = snap.sim
        })
      }
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
    await api.loadScenario('basic-mesh')
    const snap = await api.network()
    this.applySnapshot(snap)
    this.events = []
    this.packets = []
    this.report = null
  }

  async send(text: string) {
    const source = 0
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
