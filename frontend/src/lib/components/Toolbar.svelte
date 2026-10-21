<script lang="ts">
  import { api } from '../api'
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

  <div class="controls" role="toolbar" aria-label="Simulation controls">
    <button type="button" class="primary" onclick={toggle}>
      {sim.sim.mode === 'running' ? 'Pause' : 'Run'}
    </button>
    <button type="button" onclick={() => sim.step(0.1)} title="Advance 0.1 simulated seconds">
      Step 0.1s
    </button>
    <button type="button" class="ghost" onclick={() => sim.reset()} title="Reload current scenario">
      Reset
    </button>
    <label class="scenario">
      <span>Scenario</span>
      <select
        aria-label="Scenario"
        value={sim.scenarioName}
        onchange={(e) => {
          const name = (e.target as HTMLSelectElement).value
          void sim.loadScenario(name)
        }}
      >
        {#if sim.scenarios.length === 0}
          <option value={sim.scenarioName}>{sim.scenarioName}</option>
        {:else}
          {#each sim.scenarios as s}
            <option value={s.name}>
              {s.name} ({s.nodes}n{s.has_mobility ? ', mobile' : ''}{s.native_nodes ? `, ${s.native_nodes} native` : ''})
            </option>
          {/each}
        {/if}
      </select>
    </label>
    <label class="speed">
      <span>Speed</span>
      <input
        type="range"
        min="0.25"
        max="8"
        step="0.25"
        value={sim.sim.speed}
        aria-valuetext={`${sim.sim.speed}×`}
        oninput={(e) => {
          const v = Number((e.target as HTMLInputElement).value)
          sim.sim = { ...sim.sim, speed: v }
          void api.speed(v)
        }}
      />
      <span class="mono">{sim.sim.speed}×</span>
    </label>
    <label class="group">
      <span>Group</span>
      <input bind:value={sim.selectedGroup} aria-label="Selected multicast group" />
    </label>
  </div>

  <p class="hint">
    Pick a scenario · Click a node to inspect · Native nodes expose a live log file
  </p>
</header>

<style>
  .bar {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 1rem;
    align-items: center;
    padding: 0.7rem 1rem;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
  }
  .brand {
    display: flex;
    flex-direction: column;
    line-height: 1.05;
    min-width: 7.5rem;
  }
  .mark {
    font-family: var(--display);
    font-weight: 700;
    font-size: 1.35rem;
    letter-spacing: 0.02em;
    color: var(--ink);
  }
  .sub {
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--muted);
    letter-spacing: 0.02em;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    align-items: center;
  }
  button {
    font-size: 0.84rem;
    font-weight: 600;
    padding: 0.42rem 0.85rem;
    border: 1px solid var(--line);
    background: var(--panel-elev);
    color: var(--ink);
    transition: background 120ms ease, border-color 120ms ease, transform 80ms ease;
  }
  button:hover {
    border-color: var(--ink-soft);
  }
  button:active {
    transform: translateY(1px);
  }
  button.primary {
    background: var(--teal);
    border-color: var(--teal);
    color: #fff;
  }
  button.primary:hover {
    background: var(--teal-bright);
    border-color: var(--teal-bright);
  }
  button.ghost {
    background: transparent;
  }
  .speed,
  .group,
  .scenario {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
    color: var(--muted);
    font-size: 0.75rem;
    font-weight: 600;
    margin-left: 0.25rem;
  }
  .speed input[type='range'] {
    width: 6.5rem;
    accent-color: var(--teal);
  }
  .group input,
  .scenario select {
    width: 5.5rem;
    padding: 0.3rem 0.45rem;
    border: 1px solid var(--line);
    background: var(--panel);
    color: var(--ink);
    font-size: 0.84rem;
  }
  .scenario select {
    width: auto;
    min-width: 11rem;
    max-width: 16rem;
  }
  .mono {
    font-family: var(--mono);
    color: var(--ink);
    min-width: 2.2rem;
  }
  .hint {
    margin: 0;
    font-size: 0.72rem;
    color: var(--muted);
    max-width: 16rem;
    text-align: right;
    line-height: 1.3;
  }
  @media (max-width: 960px) {
    .bar {
      grid-template-columns: 1fr;
    }
    .hint {
      text-align: left;
      max-width: none;
    }
  }
</style>
