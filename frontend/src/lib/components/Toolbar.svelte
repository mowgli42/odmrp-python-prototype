<script lang="ts">
  import { sim } from '../stores/sim.svelte'

  async function toggle() {
    if (sim.sim.mode === 'running') await sim.pause()
    else await sim.run()
  }
</script>

<header class="bar">
  <div class="brand">
    <span class="mark">ODMRP</span>
    <span class="sub">mesh laboratory</span>
  </div>
  <div class="controls">
    <button type="button" class="primary" onclick={toggle}>
      {sim.sim.mode === 'running' ? 'Pause' : 'Run'}
    </button>
    <button type="button" onclick={() => sim.step(0.1)}>Step 0.1s</button>
    <button type="button" onclick={() => sim.reset()}>Reset scenario</button>
    <label class="speed">
      Speed
      <input
        type="range"
        min="0.25"
        max="8"
        step="0.25"
        value={sim.sim.speed}
        oninput={(e) => {
          const v = Number((e.target as HTMLInputElement).value)
          sim.sim = { ...sim.sim, speed: v }
          import('../api').then(({ api }) => api.speed(v))
        }}
      />
      <span>{sim.sim.speed}×</span>
    </label>
  </div>
  <div class="status" aria-live="polite">
    <span class:ok={sim.connected} class="dot"></span>
    <span>t = {sim.sim.t.toFixed(3)} s</span>
    <span class="mode">{sim.sim.mode}</span>
    <span class="scenario">{sim.sim.scenario ?? '—'}</span>
  </div>
</header>

<style>
  .bar {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 1.25rem;
    align-items: center;
    padding: 0.75rem 1.25rem;
    background: rgba(8, 12, 20, 0.92);
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
    backdrop-filter: blur(8px);
  }
  .brand {
    display: flex;
    flex-direction: column;
    line-height: 1.1;
  }
  .mark {
    font-family: 'Syne', 'Arial Narrow', sans-serif;
    font-weight: 700;
    font-size: 1.35rem;
    letter-spacing: 0.04em;
    color: #e8eef5;
  }
  .sub {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.72rem;
    color: #8aa4b8;
    text-transform: lowercase;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }
  button {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.85rem;
    padding: 0.4rem 0.85rem;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: #152033;
    color: #e8eef5;
    cursor: pointer;
  }
  button.primary {
    background: #1d4ed8;
    border-color: #3b82f6;
  }
  button:hover {
    border-color: #e8eef5;
  }
  .speed {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
    color: #8aa4b8;
    font-size: 0.8rem;
  }
  .status {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #b6c5d4;
  }
  .dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: #f87171;
  }
  .dot.ok {
    background: #34d399;
  }
  .mode {
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
</style>
