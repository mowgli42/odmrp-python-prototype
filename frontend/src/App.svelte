<script lang="ts">
  import { onMount } from 'svelte'
  import Toolbar from './lib/components/Toolbar.svelte'
  import NetworkStatus from './lib/components/NetworkStatus.svelte'
  import NetworkView from './lib/components/NetworkView.svelte'
  import NodeInspector from './lib/components/NodeInspector.svelte'
  import MessagingPanel from './lib/components/MessagingPanel.svelte'
  import TraceTimeline from './lib/components/TraceTimeline.svelte'
  import { sim } from './lib/stores/sim.svelte'

  onMount(() => {
    sim.bootstrap()
  })
</script>

<div class="shell">
  <Toolbar />
  <NetworkStatus />
  {#if sim.error}
    <div class="banner" role="alert">
      <strong>Something went wrong</strong>
      <span>{sim.error}</span>
      <button type="button" onclick={() => sim.bootstrap()}>Retry connection</button>
    </div>
  {/if}
  <main class="stage">
    <div class="map">
      <NetworkView />
      <div class="legend" aria-label="Map legend">
        <span><i class="src"></i> source</span>
        <span><i class="mem"></i> member</span>
        <span><i class="fg"></i> forwarding group</span>
        <span><i class="mesh"></i> mesh link</span>
        <span><i class="drop"></i> drop</span>
      </div>
    </div>
    <NodeInspector />
  </main>
  <div class="bottom">
    <MessagingPanel />
    <TraceTimeline />
  </div>
</div>

<style>
  .shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto auto auto 1fr auto;
  }
  .banner {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    align-items: center;
    padding: 0.55rem 1rem;
    background: rgba(232, 93, 76, 0.12);
    border-bottom: 1px solid rgba(232, 93, 76, 0.35);
    color: var(--err);
    font-size: 0.85rem;
  }
  .banner strong {
    font-weight: 700;
  }
  .banner button {
    margin-left: auto;
    padding: 0.3rem 0.7rem;
    border: 1px solid rgba(232, 93, 76, 0.45);
    background: #fff;
    color: var(--err);
    font-weight: 600;
    font-size: 0.8rem;
  }
  .stage {
    display: grid;
    grid-template-columns: 1fr minmax(17rem, 21rem);
    min-height: 0;
    border-bottom: 1px solid var(--line);
  }
  .map {
    position: relative;
    min-height: 28rem;
    background: var(--panel);
  }
  .legend {
    position: absolute;
    left: 0.75rem;
    bottom: 0.75rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
    padding: 0.4rem 0.65rem;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid var(--line);
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--ink-soft);
    backdrop-filter: blur(4px);
  }
  .legend i {
    display: inline-block;
    width: 0.7rem;
    height: 0.7rem;
    margin-right: 0.28rem;
    vertical-align: -1px;
  }
  .legend .src {
    background: var(--source);
  }
  .legend .mem {
    background: transparent;
    box-shadow: inset 0 0 0 2px var(--member);
    border-radius: 50%;
  }
  .legend .fg {
    background: var(--fg);
    border-radius: 50%;
    box-shadow: 0 0 0 3px rgba(180, 83, 9, 0.2);
  }
  .legend .mesh {
    width: 0.95rem;
    height: 3px;
    background: var(--amber);
    vertical-align: 3px;
  }
  .legend .drop {
    background: transparent;
    color: var(--coral);
    font-style: normal;
    width: auto;
    height: auto;
  }
  .legend .drop::before {
    content: '×';
    font-weight: 700;
  }
  .bottom {
    display: grid;
    grid-template-columns: minmax(16rem, 22rem) 1fr;
    background: var(--panel);
  }
  @media (max-width: 960px) {
    .stage {
      grid-template-columns: 1fr;
      grid-template-rows: 22rem auto;
    }
    .bottom {
      grid-template-columns: 1fr;
    }
  }
</style>
