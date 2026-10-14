<script lang="ts">
  import { sim } from '../stores/sim.svelte'
  import { summarize } from './TraceTimeline.svelte'

  let nowTick = $state(0)
  $effect(() => {
    const id = setInterval(() => {
      nowTick += 1
    }, 200)
    return () => clearInterval(id)
  })

  const health = $derived(sim.meshHealth)
  const healthLabel = $derived(
    (
      {
        idle: 'Idle — no active session',
        forming: 'Forming — Join Query in flight',
        established: 'Mesh up — FG forwarding',
        expiring: 'Soft-state fading — refresh soon',
      } as const
    )[health],
  )

  const refreshLeft = $derived.by(() => {
    void nowTick
    const at = sim.nextRefreshAt
    if (at == null) return null
    return Math.max(0, at - sim.sim.t)
  })

  const fgLeft = $derived.by(() => {
    void nowTick
    const at = sim.softestFgExpiresAt
    if (at == null) return null
    return Math.max(0, at - sim.sim.t)
  })

  const dropTotal = $derived(sim.drops.duplicate + sim.drops.not_fg + sim.drops.other)
  const last = $derived(sim.lastEvent)
</script>

<section class="status" aria-label="Network status" aria-live="polite">
  <div class="cluster primary">
    <div class="pill conn" class:live={sim.connected} title="WebSocket feed">
      <span class="glyph" aria-hidden="true">{sim.connected ? '●' : '○'}</span>
      <span class="label">{sim.connected ? 'Live' : 'Reconnecting'}</span>
    </div>
    <div class="pill mode" data-mode={sim.sim.mode}>
      <span class="glyph" aria-hidden="true">{sim.sim.mode === 'running' ? '▶' : 'Ⅱ'}</span>
      <span class="label">{sim.sim.mode === 'running' ? 'Running' : 'Paused'}</span>
    </div>
    <div class="pill clock" title="Simulation clock">
      <span class="k">t</span>
      <span class="v mono">{sim.sim.t.toFixed(3)} s</span>
    </div>
    <div class="pill scenario" title="Loaded scenario">
      <span class="k">Scenario</span>
      <span class="v">{sim.sim.scenario ?? 'none'}</span>
    </div>
  </div>

  <div class="cluster mesh" data-health={health}>
    <div class="health" title={healthLabel}>
      <span class="health-dot" aria-hidden="true"></span>
      <div class="health-copy">
        <span class="k">Mesh</span>
        <span class="v">{healthLabel}</span>
      </div>
    </div>
    <div class="stat" title="Nodes in topology">
      <span class="k">Nodes</span>
      <span class="v mono">{sim.topology.nodes.length}</span>
    </div>
    <div class="stat" title="Neighbour links">
      <span class="k">Links</span>
      <span class="v mono">{sim.topology.links.length}</span>
    </div>
    <div class="stat" title="Group members for selected group">
      <span class="k">Members</span>
      <span class="v mono">{sim.memberIds.length}</span>
      {#if sim.memberIds.length}
        <span class="hint mono">[{sim.memberIds.join(',')}]</span>
      {/if}
    </div>
    <div class="stat" title="Forwarding-group nodes">
      <span class="k">FG</span>
      <span class="v mono">{sim.fgIds.length}</span>
      {#if sim.fgIds.length}
        <span class="hint mono">[{sim.fgIds.join(',')}]</span>
      {/if}
    </div>
    <div class="stat" title="Time until softest FG entry expires">
      <span class="k">FG soft-state</span>
      <span class="v mono">{fgLeft == null ? '—' : `${fgLeft.toFixed(1)}s`}</span>
      {#if fgLeft != null}
        <span class="bar" aria-hidden="true">
          <i style={`width: ${Math.min(100, (fgLeft / 9) * 100)}%`}></i>
        </span>
      {/if}
    </div>
    <div class="stat" title="Countdown to next source Join Query">
      <span class="k">Next Join Query</span>
      <span class="v mono">{refreshLeft == null ? '—' : `${refreshLeft.toFixed(1)}s`}</span>
    </div>
  </div>

  <div class="cluster feedback">
    <div class="stat" title="Animated packets currently on links">
      <span class="k">In flight</span>
      <span class="v mono">{sim.packetsInFlight}</span>
    </div>
    <div class="stat ok" title="Local deliveries observed">
      <span class="k">Delivered</span>
      <span class="v mono">{sim.deliveries}</span>
    </div>
    <div class="stat" class:warn={dropTotal > 0} title="Suppressed packets (duplicate / not FG)">
      <span class="k">Drops</span>
      <span class="v mono">{dropTotal}</span>
      {#if dropTotal}
        <span class="hint mono">dup {sim.drops.duplicate} · !fg {sim.drops.not_fg}</span>
      {/if}
    </div>
    <div class="stat last" title="Most recent trace event">
      <span class="k">Last event</span>
      {#if last}
        <span class="v mono">{last.kind}</span>
        <span class="hint">{summarize(last)}</span>
      {:else}
        <span class="v muted">waiting…</span>
      {/if}
    </div>
  </div>
</section>

<style>
  .status {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.65rem 1rem;
    align-items: stretch;
    padding: 0.55rem 1rem;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
  }
  .cluster {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 0.55rem;
    align-items: center;
  }
  .pill,
  .stat,
  .health {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.28rem 0.55rem;
    background: var(--panel-elev);
    border: 1px solid var(--line);
    min-height: 1.85rem;
  }
  .k {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .v {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--ink);
  }
  .mono {
    font-family: var(--mono);
    font-weight: 500;
  }
  .hint {
    font-size: 0.68rem;
    color: var(--muted);
    max-width: 10rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .muted {
    color: var(--muted);
    font-weight: 500;
  }
  .glyph {
    font-size: 0.7rem;
    line-height: 1;
  }
  .label {
    font-size: 0.78rem;
    font-weight: 600;
  }
  .conn {
    color: var(--err);
  }
  .conn.live {
    color: var(--ok);
    border-color: rgba(15, 118, 110, 0.35);
    background: rgba(15, 118, 110, 0.08);
  }
  .mode[data-mode='running'] {
    border-color: rgba(29, 78, 216, 0.35);
    background: rgba(29, 78, 216, 0.08);
    color: var(--blue);
  }
  .mode[data-mode='paused'] {
    color: var(--ink-soft);
  }
  .health {
    gap: 0.5rem;
    min-width: 11rem;
  }
  .health-copy {
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
    line-height: 1.15;
  }
  .health-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: var(--idle);
    box-shadow: 0 0 0 3px rgba(100, 116, 139, 0.15);
  }
  .mesh[data-health='forming'] .health-dot {
    background: var(--blue);
    box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.18);
    animation: pulse 1.2s ease-in-out infinite;
  }
  .mesh[data-health='established'] .health-dot {
    background: var(--ok);
    box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.18);
  }
  .mesh[data-health='expiring'] .health-dot {
    background: var(--warn);
    box-shadow: 0 0 0 3px rgba(180, 83, 9, 0.18);
    animation: pulse 0.9s ease-in-out infinite;
  }
  .stat.ok .v {
    color: var(--ok);
  }
  .stat.warn {
    border-color: rgba(232, 93, 76, 0.35);
    background: rgba(232, 93, 76, 0.06);
  }
  .bar {
    display: inline-block;
    width: 2.6rem;
    height: 0.28rem;
    background: var(--paper-2);
    overflow: hidden;
  }
  .bar i {
    display: block;
    height: 100%;
    background: var(--amber);
    transition: width 200ms linear;
  }
  .last {
    max-width: 16rem;
  }
  @keyframes pulse {
    0%,
    100% {
      transform: scale(1);
      opacity: 1;
    }
    50% {
      transform: scale(0.85);
      opacity: 0.65;
    }
  }
  @media (max-width: 1100px) {
    .status {
      grid-template-columns: 1fr;
    }
  }
</style>
