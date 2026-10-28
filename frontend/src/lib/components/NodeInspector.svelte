<script lang="ts">
  import { api } from '../api'
  import { sim } from '../stores/sim.svelte'

  const node = $derived(sim.selected == null ? null : sim.nodes[String(sim.selected)])
  const fg = $derived(
    node ? node.forwarding_groups?.[sim.selectedGroup] ?? null : null,
  )
  const fgLeft = $derived(fg ? Math.max(0, fg.expires_at - sim.sim.t) : null)
  const bookEntry = $derived.by(() => {
    const nodes = sim.overlay.address_book?.nodes
    if (!node || !Array.isArray(nodes)) return null
    return nodes.find((n: { node_id: number }) => n.node_id === node.id) ?? null
  })
  const role = $derived.by(() => {
    if (!node) return []
    const tags: string[] = []
    if (node.sessions?.some((s) => s.group === sim.selectedGroup)) tags.push('source')
    if (node.members?.includes(sim.selectedGroup)) tags.push('member')
    if (node.fg?.includes(sim.selectedGroup) || fg) tags.push('FG')
    if (node.impl && node.impl !== 'python') tags.push(node.impl)
    if (bookEntry?.capabilities?.is_super_node) tags.push('super')
    return tags
  })
  let logLines = $state<string[]>([])
  let logPath = $state<string | null>(null)
  let logBusy = $state(false)

  $effect(() => {
    const id = sim.selected
    const hasLog = !!node?.log
    if (id == null || !hasLog) {
      logLines = []
      logPath = null
      return
    }
    let cancelled = false
    const pull = async () => {
      try {
        const res = await api.nodeLog(id, 60)
        if (cancelled) return
        logPath = res.path
        logLines = res.lines
      } catch {
        if (!cancelled) logLines = []
      }
    }
    void pull()
    const timer = setInterval(() => void pull(), 1500)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  })

  async function join() {
    if (!node) return
    await api.join(node.id, sim.selectedGroup)
    sim.applySnapshot(await api.network())
  }
  async function leave() {
    if (!node) return
    await api.leave(node.id, sim.selectedGroup)
    sim.applySnapshot(await api.network())
  }
  async function refreshLog() {
    if (!node?.log) return
    logBusy = true
    try {
      const res = await api.nodeLog(node.id, 80)
      logPath = res.path
      logLines = res.lines
    } finally {
      logBusy = false
    }
  }
</script>

<aside class="insp">
  <header>
    <h2>Node inspector</h2>
    {#if node}
      <p class="id">Node {node.id}</p>
    {/if}
  </header>

  {#if !node}
    <p class="empty">Select a node on the map to see routes, FG soft-state, and inbox.</p>
  {:else}
    <div class="roles" aria-label="Node roles">
      {#if role.length === 0}
        <span class="tag muted">relay / idle</span>
      {:else}
        {#each role as r}
          <span class="tag" data-role={r}>{r}</span>
        {/each}
      {/if}
    </div>

    <dl>
      <div>
        <dt>Impl</dt>
        <dd class="mono">{node.impl ?? 'python'}</dd>
      </div>
      {#if bookEntry}
        <div>
          <dt>Callsign</dt>
          <dd>{bookEntry.callsign}</dd>
        </div>
        <div>
          <dt>Tunnel</dt>
          <dd class="mono trunc" title={bookEntry.tunnel_endpoint}>{bookEntry.tunnel_endpoint || '—'}</dd>
        </div>
      {/if}
      <div>
        <dt>Position</dt>
        <dd>({node.pos.x.toFixed(0)}, {node.pos.y.toFixed(0)})</dd>
      </div>
      <div>
        <dt>Range</dt>
        <dd>{node.range}</dd>
      </div>
      <div>
        <dt>Groups</dt>
        <dd>{node.members.join(', ') || '—'}</dd>
      </div>
      <div>
        <dt>FG soft-state</dt>
        <dd>
          {#if fgLeft == null}
            —
          {:else}
            {fgLeft.toFixed(1)}s
            <span class="bar" aria-hidden="true"><i style={`width: ${Math.min(100, (fgLeft / 9) * 100)}%`}></i></span>
          {/if}
        </dd>
      </div>
    </dl>

    {#if bookEntry?.neighbors?.length}
      <h3>Logical neighbors</h3>
      <table>
        <thead>
          <tr><th>peer</th><th>pri</th><th>status</th><th>reason</th></tr>
        </thead>
        <tbody>
          {#each bookEntry.neighbors as nb}
            <tr>
              <td>{nb.peer_id}</td>
              <td>{nb.priority}</td>
              <td>{nb.status}</td>
              <td>{nb.reason}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Routes</h3>
    {#if Object.keys(node.routes || {}).length === 0}
      <p class="empty">No reverse-path entries yet</p>
    {:else}
      <table>
        <thead>
          <tr><th>src</th><th>next</th><th>seq</th><th>exp</th></tr>
        </thead>
        <tbody>
          {#each Object.entries(node.routes) as [src, r]}
            <tr>
              <td>{src}</td>
              <td>{r.next_hop}</td>
              <td>{r.seq}</td>
              <td>{Math.max(0, r.expires_at - sim.sim.t).toFixed(1)}s</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Inbox</h3>
    {#if !(node.inbox?.length)}
      <p class="empty">No deliveries yet</p>
    {:else}
      <ul>
        {#each node.inbox.slice(-8) as item}
          <li>
            <span class="mono">{item.source}→</span>
            {item.body ?? item.message_id}
          </li>
        {/each}
      </ul>
    {/if}

    {#if node.log}
      <h3>Native log</h3>
      <p class="log-path mono" title={logPath ?? node.log}>{logPath ?? node.log}</p>
      <pre class="log" aria-label="Native node log tail">{logLines.join('\n') || '(log empty — traffic will append NDJSON lines)'}</pre>
      <button type="button" class="ghost" disabled={logBusy} onclick={refreshLog}>
        {logBusy ? 'Refreshing…' : 'Refresh log'}
      </button>
    {/if}

    <div class="actions">
      <button type="button" class="primary" onclick={join}>Join {sim.selectedGroup}</button>
      <button type="button" onclick={leave}>Leave</button>
    </div>
  {/if}
</aside>

<style>
  .insp {
    padding: 1rem 1.05rem;
    background: var(--panel);
    border-left: 1px solid var(--line);
    overflow: auto;
    height: 100%;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }
  h2,
  h3 {
    font-family: var(--display);
    font-weight: 600;
    margin: 0;
    color: var(--ink);
  }
  h2 {
    font-size: 1rem;
  }
  h3 {
    margin: 1rem 0 0.45rem;
    font-size: 0.82rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .id {
    margin: 0;
    font-family: var(--mono);
    font-size: 1.05rem;
    font-weight: 500;
    color: var(--blue);
  }
  .roles {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.75rem;
  }
  .tag {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.2rem 0.45rem;
    border: 1px solid var(--line);
    background: var(--panel-elev);
  }
  .tag[data-role='source'] {
    background: rgba(29, 78, 216, 0.1);
    border-color: rgba(29, 78, 216, 0.35);
    color: var(--blue);
  }
  .tag[data-role='member'] {
    background: rgba(15, 118, 110, 0.1);
    border-color: rgba(15, 118, 110, 0.35);
    color: var(--member);
  }
  .tag[data-role='FG'] {
    background: rgba(180, 83, 9, 0.1);
    border-color: rgba(180, 83, 9, 0.35);
    color: var(--fg);
  }
  .tag[data-role='native'],
  .tag[data-role='external'],
  .tag[data-role='java'],
  .tag[data-role='super'] {
    background: rgba(15, 118, 110, 0.12);
    border-color: rgba(15, 118, 110, 0.4);
    color: var(--teal);
  }
  .trunc {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tag.muted {
    color: var(--muted);
  }
  .log-path {
    margin: 0 0 0.35rem;
    font-size: 0.68rem;
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .log {
    margin: 0 0 0.45rem;
    padding: 0.45rem 0.5rem;
    max-height: 9rem;
    overflow: auto;
    background: #0f172a;
    color: #e2e8f0;
    font-family: var(--mono);
    font-size: 0.65rem;
    line-height: 1.35;
    border: 1px solid var(--line);
    white-space: pre-wrap;
    word-break: break-all;
  }
  dl {
    display: grid;
    gap: 0.4rem;
    margin: 0;
  }
  dl > div {
    display: grid;
    grid-template-columns: 6.2rem 1fr;
    gap: 0.5rem;
    font-size: 0.84rem;
    align-items: center;
  }
  dt {
    color: var(--muted);
    font-weight: 600;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  dd {
    margin: 0;
    color: var(--ink);
    font-family: var(--mono);
    font-size: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .bar {
    display: inline-block;
    width: 3rem;
    height: 0.3rem;
    background: var(--paper-2);
    overflow: hidden;
  }
  .bar i {
    display: block;
    height: 100%;
    background: var(--amber);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--mono);
    font-size: 0.74rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.28rem 0.3rem;
    border-bottom: 1px solid var(--line);
  }
  th {
    color: var(--muted);
    font-weight: 600;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  li {
    padding: 0.35rem 0;
    border-bottom: 1px solid var(--line);
    font-size: 0.84rem;
    color: var(--ink-soft);
  }
  .mono {
    font-family: var(--mono);
    color: var(--muted);
    margin-right: 0.35rem;
  }
  .empty {
    color: var(--muted);
    font-size: 0.84rem;
    margin: 0.25rem 0;
  }
  .actions {
    display: flex;
    gap: 0.45rem;
    margin-top: 1rem;
  }
  button {
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.4rem 0.7rem;
    background: var(--panel-elev);
    color: var(--ink);
    border: 1px solid var(--line);
  }
  button.primary {
    background: var(--teal);
    border-color: var(--teal);
    color: #fff;
  }
  button.ghost {
    background: transparent;
    margin-bottom: 0.35rem;
  }
</style>
