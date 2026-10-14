<script lang="ts">
  import { sim } from '../stores/sim.svelte'

  const node = $derived(sim.selected == null ? null : sim.nodes[String(sim.selected)])
</script>

<aside class="insp">
  <h2>Node inspector</h2>
  {#if !node}
    <p class="empty">Select a node on the map.</p>
  {:else}
    <div class="id">Node {node.id}</div>
    <dl>
      <div><dt>Position</dt><dd>({node.pos.x.toFixed(0)}, {node.pos.y.toFixed(0)})</dd></div>
      <div><dt>Range</dt><dd>{node.range}</dd></div>
      <div><dt>Members</dt><dd>{node.members.join(', ') || '—'}</dd></div>
      <div><dt>FG</dt><dd>{node.fg?.join(', ') || Object.keys(node.forwarding_groups || {}).join(', ') || '—'}</dd></div>
    </dl>
    <h3>Routes</h3>
    {#if Object.keys(node.routes || {}).length === 0}
      <p class="empty">No routes</p>
    {:else}
      <table>
        <thead><tr><th>src</th><th>next</th><th>seq</th><th>exp</th></tr></thead>
        <tbody>
          {#each Object.entries(node.routes) as [src, r]}
            <tr>
              <td>{src}</td>
              <td>{r.next_hop}</td>
              <td>{r.seq}</td>
              <td>{r.expires_at.toFixed(1)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
    <h3>Inbox</h3>
    {#if !(node.inbox?.length)}
      <p class="empty">Empty</p>
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
    <div class="actions">
      <button
        type="button"
        onclick={() =>
          import('../api').then(({ api }) =>
            api.join(node.id, sim.selectedGroup).then(() => api.network()).then((s) => sim.applySnapshot(s)),
          )}
      >
        Join {sim.selectedGroup}
      </button>
      <button
        type="button"
        onclick={() =>
          import('../api').then(({ api }) =>
            api.leave(node.id, sim.selectedGroup).then(() => api.network()).then((s) => sim.applySnapshot(s)),
          )}
      >
        Leave
      </button>
    </div>
  {/if}
</aside>

<style>
  .insp {
    padding: 1rem 1.1rem;
    background: rgba(10, 14, 22, 0.95);
    border-left: 1px solid rgba(148, 163, 184, 0.18);
    overflow: auto;
    height: 100%;
  }
  h2, h3 {
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    margin: 0 0 0.6rem;
    color: #e8eef5;
  }
  h3 { margin-top: 1rem; font-size: 0.95rem; color: #8aa4b8; }
  .id {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.2rem;
    color: #93c5fd;
    margin-bottom: 0.75rem;
  }
  dl {
    display: grid;
    gap: 0.35rem;
    margin: 0;
  }
  dl > div {
    display: grid;
    grid-template-columns: 5.5rem 1fr;
    gap: 0.5rem;
    font-size: 0.85rem;
  }
  dt { color: #8aa4b8; }
  dd { margin: 0; color: #e8eef5; font-family: 'IBM Plex Mono', monospace; }
  table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
  }
  th, td {
    text-align: left;
    padding: 0.25rem 0.35rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  }
  th { color: #8aa4b8; font-weight: 500; }
  ul { list-style: none; padding: 0; margin: 0; }
  li {
    padding: 0.35rem 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    font-size: 0.85rem;
    color: #d5dee8;
  }
  .mono { font-family: 'IBM Plex Mono', monospace; color: #8aa4b8; margin-right: 0.35rem; }
  .empty { color: #6b7c8f; font-size: 0.85rem; }
  .actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
  button {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.8rem;
    padding: 0.35rem 0.7rem;
    background: #152033;
    color: #e8eef5;
    border: 1px solid rgba(148, 163, 184, 0.35);
    cursor: pointer;
  }
</style>
