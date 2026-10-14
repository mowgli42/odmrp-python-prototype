<script lang="ts">
  import { onMount } from 'svelte'
  import Toolbar from './lib/components/Toolbar.svelte'
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
  {#if sim.error}
    <div class="banner" role="alert">{sim.error}</div>
  {/if}
  <main class="stage">
    <div class="map">
      <NetworkView />
      <div class="legend" aria-hidden="true">
        <span><i class="src"></i> source</span>
        <span><i class="mem"></i> member</span>
        <span><i class="fg"></i> forwarding group</span>
        <span><i class="lnk"></i> link</span>
      </div>
    </div>
    <NodeInspector />
  </main>
  <MessagingPanel />
  <TraceTimeline />
</div>

<style>
  .shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto auto 1fr auto auto;
    background:
      radial-gradient(1200px 500px at 10% -10%, rgba(29, 78, 216, 0.18), transparent 60%),
      radial-gradient(900px 400px at 90% 0%, rgba(244, 140, 84, 0.1), transparent 55%),
      #070b12;
  }
  .banner {
    padding: 0.5rem 1.25rem;
    background: #7f1d1d;
    color: #fecaca;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.85rem;
  }
  .stage {
    display: grid;
    grid-template-columns: 1fr minmax(16rem, 20rem);
    min-height: 0;
  }
  .map {
    position: relative;
    min-height: 28rem;
  }
  .legend {
    position: absolute;
    left: 0.85rem;
    bottom: 0.85rem;
    display: flex;
    gap: 0.85rem;
    padding: 0.4rem 0.65rem;
    background: rgba(8, 12, 20, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.2);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.72rem;
    color: #b6c5d4;
  }
  .legend i {
    display: inline-block;
    width: 0.65rem;
    height: 0.65rem;
    margin-right: 0.3rem;
    border-radius: 50%;
    vertical-align: -1px;
  }
  .legend .src { background: #1d4ed8; }
  .legend .mem { background: transparent; box-shadow: inset 0 0 0 2px #34d399; }
  .legend .fg { background: #f48c54; }
  .legend .lnk {
    width: 0.9rem;
    height: 2px;
    border-radius: 0;
    background: #3d6f8c;
    vertical-align: 3px;
  }
  @media (max-width: 860px) {
    .stage {
      grid-template-columns: 1fr;
      grid-template-rows: 22rem auto;
    }
  }
</style>
