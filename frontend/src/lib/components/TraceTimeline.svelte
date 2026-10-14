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

  const recent = $derived([...sim.events].slice(-60).reverse())
</script>

<section class="trace">
  <h2>Trace</h2>
  <ol>
    {#each recent as e, i (`${e.seq}-${e.kind}-${e.node}-${i}`)}
      <li>
        <span class="t">{e.t.toFixed(3)}</span>
        <span class="kind">{e.kind}</span>
        <span class="node">n{e.node}</span>
        <span class="detail">{summarize(e)}</span>
      </li>
    {/each}
  </ol>
</section>

<style>
  .trace {
    padding: 0.75rem 1.1rem;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
    background: #080c14;
    max-height: 11rem;
    overflow: auto;
  }
  h2 {
    margin: 0 0 0.4rem;
    font-family: 'Syne', sans-serif;
    font-size: 0.95rem;
    color: #8aa4b8;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
  }
  li {
    display: grid;
    grid-template-columns: 4.2rem 7.5rem 2.4rem 1fr;
    gap: 0.55rem;
    padding: 0.18rem 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.08);
    color: #b6c5d4;
  }
  .t { color: #6b7c8f; }
  .kind { color: #93c5fd; }
  .node { color: #f48c54; }
  .detail { color: #c5d0db; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
