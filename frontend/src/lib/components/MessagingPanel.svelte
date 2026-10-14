<script lang="ts">
  import { sim } from '../stores/sim.svelte'

  let text = $state('ODMRP works')
  let busy = $state(false)
  let feedback = $state<string | null>(null)

  async function send() {
    if (!text.trim() || busy) return
    busy = true
    feedback = null
    try {
      await sim.send(text.trim())
      const to = (sim.report?.delivered_to || []).join(', ')
      feedback = to ? `Delivered to nodes ${to}` : 'Sent — waiting for deliveries'
    } catch (e) {
      feedback = `Send failed: ${e}`
    } finally {
      busy = false
    }
  }
</script>

<section class="msg">
  <h2>Messaging</h2>
  <p class="help">Inject a text payload from source node 0 into the selected group.</p>
  <div class="row">
    <label class="grow">
      Text
      <input
        bind:value={text}
        disabled={busy}
        onkeydown={(e) => e.key === 'Enter' && send()}
        aria-describedby="msg-help"
      />
    </label>
    <button type="button" class="primary" disabled={busy || !text.trim()} onclick={send}>
      {busy ? 'Sending…' : 'Send'}
    </button>
  </div>
  <p id="msg-help" class="sr" hidden>Press Enter to send</p>
  {#if feedback}
    <div class="report" class:ok={!feedback.startsWith('Send failed')} role="status">
      {feedback}
      {#if sim.lastMessageId}
        <code>{sim.lastMessageId.slice(0, 8)}</code>
      {/if}
    </div>
  {/if}
  {#if sim.memberIds.length}
    <p class="expect">
      Current members of <strong>{sim.selectedGroup}</strong>:
      <span class="mono">[{sim.memberIds.join(', ')}]</span>
    </p>
  {/if}
</section>

<style>
  .msg {
    padding: 0.85rem 1rem;
    border-right: 1px solid var(--line);
  }
  h2 {
    margin: 0;
    font-family: var(--display);
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--ink);
  }
  .help {
    margin: 0.25rem 0 0.55rem;
    font-size: 0.72rem;
    color: var(--muted);
  }
  .row {
    display: flex;
    gap: 0.55rem;
    align-items: end;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .grow {
    flex: 1;
  }
  input {
    font-size: 0.9rem;
    font-weight: 500;
    padding: 0.45rem 0.55rem;
    background: var(--panel-elev);
    border: 1px solid var(--line);
    color: var(--ink);
    text-transform: none;
    letter-spacing: normal;
  }
  button {
    font-weight: 600;
    padding: 0.48rem 0.95rem;
    background: var(--panel-elev);
    color: var(--ink);
    border: 1px solid var(--line);
    height: 2.3rem;
  }
  button.primary {
    background: var(--coral);
    border-color: var(--coral);
    color: #fff;
  }
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .report {
    margin-top: 0.55rem;
    display: flex;
    gap: 0.65rem;
    align-items: center;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--err);
  }
  .report.ok {
    color: var(--ok);
  }
  code {
    color: var(--ink-soft);
    font-size: 0.72rem;
  }
  .expect {
    margin: 0.45rem 0 0;
    font-size: 0.72rem;
    color: var(--muted);
  }
  .mono {
    font-family: var(--mono);
    color: var(--ink-soft);
  }
  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
  }
</style>
