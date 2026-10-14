<script lang="ts" module>
  export function summarize(e: { kind: string; [k: string]: unknown }): string {
    if (e.kind === 'tx') {
      const p = e.packet as { kind?: string; seq?: number } | undefined
      return `${p?.kind ?? '?'} seq=${p?.seq ?? '?'}`
    }
    if (e.kind === 'rx') return `from ${e.from} ${e.pkind}`
    if (e.kind === 'drop') return String(e.reason)
    if (e.kind === 'deliver') return `${e.group} ${e.message_id}`
    if (e.kind === 'state.fg') return `${e.op} ${e.group}`
    if (e.kind === 'state.route') return `${e.op} src=${e.source}→${e.next_hop}`
    if (e.kind === 'sim') return String(e.op)
    return ''
  }
</script>

<script lang="ts">
  import { sim } from '../stores/sim.svelte'

  let filter = $state<'all' | 'tx' | 'state.fg' | 'deliver' | 'drop'>('all')
  const recent = $derived(
    [...sim.events]
      .filter((e) => filter === 'all' || e.kind === filter || e.kind.startsWith(filter))
      .slice(-80)
      .reverse(),
  )

  function selectFromEvent(e: { node: number }) {
    if (e.node >= 0) sim.select(e.node)
  }
</script>

<section class="trace">
  <div class="head">
    <h2>Trace</h2>
    <div class="chips" role="tablist" aria-label="Filter events">
      {#each ['all', 'tx', 'state.fg', 'deliver', 'drop'] as f}
        <button
          type="button"
          role="tab"
          aria-selected={filter === f}
          class:on={filter === f}
          onclick={() => (filter = f as typeof filter)}
        >
          {f}
        </button>
      {/each}
    </div>
  </div>
  {#if recent.length === 0}
    <p class="empty">No events yet — press Run or Step.</p>
  {:else}
    <ol>
      {#each recent as e (e.seq)}
        <li>
          <button type="button" class="row" onclick={() => selectFromEvent(e)}>
            <span class="t">{e.t.toFixed(3)}</span>
            <span class="kind" data-kind={e.kind}>{e.kind}</span>
            <span class="node">n{e.node}</span>
            <span class="detail">{summarize(e)}</span>
          </button>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .trace {
    padding: 0.75rem 1rem;
    max-height: 14rem;
    overflow: auto;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.85rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.45rem;
  }
  h2 {
    margin: 0;
    font-family: var(--display);
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--ink);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }
  .chips button {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    padding: 0.2rem 0.45rem;
    border: 1px solid var(--line);
    background: var(--panel-elev);
    color: var(--muted);
  }
  .chips button.on {
    background: var(--ink);
    border-color: var(--ink);
    color: #fff;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    font-family: var(--mono);
    font-size: 0.72rem;
  }
  li {
    border-bottom: 1px solid var(--line);
  }
  .row {
    display: grid;
    grid-template-columns: 4.2rem 7.2rem 2.4rem 1fr;
    gap: 0.5rem;
    width: 100%;
    padding: 0.22rem 0;
    border: 0;
    background: transparent;
    text-align: left;
    color: var(--ink-soft);
  }
  .row:hover {
    background: rgba(15, 118, 110, 0.06);
  }
  .t {
    color: var(--muted);
  }
  .kind {
    color: var(--blue);
    font-weight: 500;
  }
  .kind[data-kind='deliver'] {
    color: var(--ok);
  }
  .kind[data-kind='drop'] {
    color: var(--coral);
  }
  .kind[data-kind='state.fg'] {
    color: var(--amber);
  }
  .node {
    color: var(--amber);
  }
  .detail {
    color: var(--ink-soft);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .empty {
    margin: 0.35rem 0;
    color: var(--muted);
    font-size: 0.8rem;
  }
</style>
