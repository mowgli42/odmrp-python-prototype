<script lang="ts">
  import { sim } from '../stores/sim.svelte'

  const PAD = 40
  let width = $state(900)
  let height = $state(520)

  const bounds = $derived.by(() => {
    const ns = sim.topology.nodes
    if (!ns.length) return { minX: 0, minY: 0, maxX: 500, maxY: 400 }
    const xs = ns.map((n) => n.x)
    const ys = ns.map((n) => n.y)
    return {
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
    }
  })

  function sx(x: number) {
    const { minX, maxX } = bounds
    const span = Math.max(maxX - minX, 1)
    return PAD + ((x - minX) / span) * (width - 2 * PAD)
  }
  function sy(y: number) {
    const { minY, maxY } = bounds
    const span = Math.max(maxY - minY, 1)
    return PAD + ((y - minY) / span) * (height - 2 * PAD)
  }

  function isFg(id: number) {
    const n = sim.nodes[String(id)]
    return n?.fg?.includes(sim.selectedGroup) || !!n?.forwarding_groups?.[sim.selectedGroup]
  }
  function isMember(id: number) {
    return !!sim.nodes[String(id)]?.members?.includes(sim.selectedGroup)
  }
  function isSource(id: number) {
    const n = sim.nodes[String(id)]
    return !!n?.sessions?.some((s) => s.group === sim.selectedGroup)
  }

  const animPackets = $derived(
    sim.packets.filter((p) => performance.now() - p.born < 900),
  )

  let now = $state(performance.now())
  $effect(() => {
    const id = setInterval(() => {
      now = performance.now()
    }, 32)
    return () => clearInterval(id)
  })
</script>

<svg
  class="net"
  viewBox={`0 0 ${width} ${height}`}
  bind:clientWidth={width}
  bind:clientHeight={height}
  role="img"
  aria-label="ODMRP network topology"
>
  <defs>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
      <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(148,163,184,0.08)" stroke-width="1" />
    </pattern>
    <radialGradient id="fgGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(244, 140, 84, 0.45)" />
      <stop offset="100%" stop-color="rgba(244, 140, 84, 0)" />
    </radialGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#grid)" />

  {#each sim.topology.links as [a, b]}
    {@const na = sim.topology.nodes.find((n) => n.id === a)}
    {@const nb = sim.topology.nodes.find((n) => n.id === b)}
    {#if na && nb}
      <line
        class="link"
        x1={sx(na.x)}
        y1={sy(na.y)}
        x2={sx(nb.x)}
        y2={sy(nb.y)}
      />
    {/if}
  {/each}

  {#each animPackets as p (p.id + '-' + p.to + '-' + p.born)}
    {@const na = sim.topology.nodes.find((n) => n.id === p.from)}
    {@const nb = sim.topology.nodes.find((n) => n.id === p.to)}
    {#if na && nb}
      {@const u = Math.min(1, (now - p.born) / 800)}
      {@const x = sx(na.x) + (sx(nb.x) - sx(na.x)) * u}
      {@const y = sy(na.y) + (sy(nb.y) - sy(na.y)) * u}
      <circle
        class="pkt"
        class:jq={p.kind === 'JOIN_QUERY'}
        class:jr={p.kind === 'JOIN_REPLY'}
        cx={x}
        cy={y}
        r="4"
        opacity={1 - u * 0.85}
      />
    {/if}
  {/each}

  {#each sim.topology.nodes as n}
    {@const x = sx(n.x)}
    {@const y = sy(n.y)}
    {@const fg = isFg(n.id)}
    {@const mem = isMember(n.id)}
    {@const src = isSource(n.id)}
    {@const sel = sim.selected === n.id}
    {#if fg}
      <circle class="fg-halo" cx={x} cy={y} r="28" fill="url(#fgGlow)" />
    {/if}
    <circle
      class="node"
      class:fg
      class:member={mem}
      class:source={src}
      class:selected={sel}
      cx={x}
      cy={y}
      r="14"
      role="button"
      tabindex="0"
      onclick={() => sim.select(n.id)}
      onkeydown={(e) => e.key === 'Enter' && sim.select(n.id)}
    />
    <text class="label" x={x} y={y + 4} text-anchor="middle">{n.id}</text>
  {/each}
</svg>

<style>
  .net {
    width: 100%;
    height: 100%;
    display: block;
    background: linear-gradient(160deg, #0b1220 0%, #121a2b 55%, #0e1624 100%);
    border-radius: 0;
  }
  .link {
    stroke: #3d6f8c;
    stroke-width: 1.5;
    opacity: 0.7;
  }
  .node {
    fill: #1c2738;
    stroke: #8aa4b8;
    stroke-width: 2;
    cursor: pointer;
    transition: stroke 120ms ease, fill 120ms ease;
  }
  .node:hover {
    stroke: #e8eef5;
  }
  .node.source {
    fill: #1d4ed8;
    stroke: #93c5fd;
  }
  .node.member {
    stroke: #34d399;
    stroke-width: 3;
  }
  .node.fg {
    stroke: #f48c54;
    stroke-width: 3;
  }
  .node.selected {
    filter: drop-shadow(0 0 6px rgba(232, 238, 245, 0.55));
  }
  .label {
    fill: #e8eef5;
    font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 11px;
    pointer-events: none;
  }
  .pkt {
    fill: #e8eef5;
  }
  .pkt.jq {
    fill: #60a5fa;
  }
  .pkt.jr {
    fill: #f48c54;
  }
</style>
