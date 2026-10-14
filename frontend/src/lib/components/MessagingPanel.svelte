<script lang="ts">
  import { sim } from '../stores/sim.svelte'

  let text = $state('ODMRP works')
  let busy = $state(false)

  async function send() {
    if (!text.trim() || busy) return
    busy = true
    try {
      await sim.send(text.trim())
    } finally {
      busy = false
    }
  }
</script>

<section class="msg">
  <h2>Messaging</h2>
  <div class="row">
    <label>
      Group
      <input bind:value={sim.selectedGroup} />
    </label>
    <label class="grow">
      Text from node 0
      <input bind:value={text} onkeydown={(e) => e.key === 'Enter' && send()} />
    </label>
    <button type="button" class="primary" disabled={busy} onclick={send}>Send</button>
  </div>
  {#if sim.report}
    <div class="report">
      <span>message <code>{sim.lastMessageId?.slice(0, 8)}</code></span>
      <span>delivered → [{(sim.report.delivered_to || []).join(', ')}]</span>
    </div>
  {/if}
</section>

<style>
  .msg {
    padding: 0.85rem 1.1rem;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(8, 12, 20, 0.9);
  }
  h2 {
    margin: 0 0 0.55rem;
    font-family: 'Syne', sans-serif;
    font-size: 0.95rem;
    color: #8aa4b8;
  }
  .row {
    display: flex;
    gap: 0.65rem;
    align-items: end;
    flex-wrap: wrap;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.72rem;
    color: #8aa4b8;
  }
  .grow { flex: 1; min-width: 12rem; }
  input {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.9rem;
    padding: 0.4rem 0.55rem;
    background: #0f1724;
    border: 1px solid rgba(148, 163, 184, 0.3);
    color: #e8eef5;
  }
  button {
    font-family: 'IBM Plex Sans', sans-serif;
    padding: 0.45rem 0.9rem;
    background: #152033;
    color: #e8eef5;
    border: 1px solid rgba(148, 163, 184, 0.35);
    cursor: pointer;
    height: 2.15rem;
  }
  button.primary {
    background: #0f766e;
    border-color: #14b8a6;
  }
  button:disabled { opacity: 0.5; }
  .report {
    margin-top: 0.55rem;
    display: flex;
    gap: 1rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #b6c5d4;
  }
  code { color: #93c5fd; }
</style>
