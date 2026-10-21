const BASE = ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${path}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export type ScenarioInfo = {
  name: string
  file: string
  nodes: number
  description: string
  has_mobility: boolean
  native_nodes: number
}

export const api = {
  health: () => req<{ t: number; mode: string; version: string }>('/api/health'),
  network: () => req<any>('/api/network'),
  scenarios: () => req<{ scenarios: ScenarioInfo[] }>('/api/scenarios'),
  loadScenario: (name = 'dynamic-mesh') =>
    req<any>(`/api/network/scenario?name=${encodeURIComponent(name)}`, { method: 'POST' }),
  createNetwork: (body: unknown) =>
    req<any>('/api/network', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  step: (dt: number) =>
    req<any>('/api/sim/step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dt }),
    }),
  run: () => req('/api/sim/run', { method: 'POST' }),
  pause: () => req('/api/sim/pause', { method: 'POST' }),
  reset: () => req<any>('/api/sim/reset', { method: 'POST' }),
  speed: (multiplier: number) =>
    req('/api/sim/speed', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ multiplier }),
    }),
  join: (node: number, group: string) =>
    req(`/api/nodes/${node}/groups`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group }),
    }),
  leave: (node: number, group: string) =>
    req(`/api/nodes/${node}/groups/${encodeURIComponent(group)}`, { method: 'DELETE' }),
  sendText: (source: number, group: string, text: string) =>
    req<{ message_id: string }>('/api/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, group, text }),
    }),
  moveNode: (id: number, x: number, y: number) =>
    req(`/api/nodes/${id}/position`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ x, y }),
    }),
  node: (id: number) => req<any>(`/api/nodes/${id}`),
  nodeLog: (id: number, tail = 80) =>
    req<{
      node: number
      path: string
      impl: string
      lines: string[]
      exists: boolean
      total_lines?: number
    }>(`/api/nodes/${id}/log?tail=${tail}`),
  report: (messageId: string) => req<any>(`/api/messages/${messageId}/report`),
}
