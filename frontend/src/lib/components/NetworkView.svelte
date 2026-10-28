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
  function fgOpacity(id: number) {
    const n = sim.nodes[String(id)]
    const fg = n?.forwarding_groups?.[sim.selectedGroup]
    if (!fg) return 0
    const left = Math.max(0, fg.expires_at - sim.sim.t)
    return Math.min(1, left / 9)
  }
  function inMesh(id: number) {
    return isSource(id) || isFg(id) || isMember(id)
  }
  function isNative(id: number) {
    const impl = sim.nodes[String(id)]?.impl
    return impl === 'native' || impl === 'external' || impl === 'java'
  }
  function isSuper(id: number) {
    return sim.superNodeIds.includes(id)
  }

  const logicalLinks = $derived(sim.showLogicalLinks ? sim.logicalLinks : [])
  const recFlashes = $derived(sim.flashRecs.filter((r) => performance.now() - r.born < 1200))

  const meshLinks = $derived(
    sim.topology.links.filter(([a, b]) => inMesh(a) && inMesh(b)),
  )

  const animPackets = $derived(sim.packets.filter((p) => performance.now() - p.born < 900))
  const drops = $derived(sim.flashDrops.filter((d) => performance.now() - d.born < 700))

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
    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
      <path d="M 28 0 L 0 0 0 28" fill="none" stroke="rgba(15, 118, 110, 0.08)" stroke-width="1" />
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#grid)" />

  {#each sim.topology.links as [a, b]}
    {@const na = sim.topology.nodes.find((n) => n.id === a)}
    {@const nb = sim.topology.nodes.find((n) => n.id === b)}
    {#if na && nb}
      <line class="link" x1={sx(na.x)} y1={sy(na.y)} x2={sx(nb.x)} y2={sy(nb.y)} />
    {/if}
  {/each}

  {#each logicalLinks as [a, b]}
    {@const na = sim.topology.nodes.find((n) => n.id === a)}
    {@const nb = sim.topology.nodes.find((n) => n.id === b)}
    {#if na && nb}
      <line class="logical" x1={sx(na.x)} y1={sy(na.y)} x2={sx(nb.x)} y2={sy(nb.y)} />
    {/if}
  {/each}

  {#each meshLinks as [a, b]}
    {@const na = sim.topology.nodes.find((n) => n.id === a)}
    {@const nb = sim.topology.nodes.find((n) => n.id === b)}
    {#if na && nb}
      <line class="mesh" x1={sx(na.x)} y1={sy(na.y)} x2={sx(nb.x)} y2={sy(nb.y)} />
    {/if}
  {/each}

  {#each recFlashes as r (r.from + '-' + r.to + '-' + r.born)}
    {@const na = sim.topology.nodes.find((n) => n.id === r.from)}
    {@const nb = sim.topology.nodes.find((n) => n.id === r.to)}
    {#if na && nb}
      {@const u = Math.min(1, (now - r.born) / 1100)}
      <line
        class="rec"
        x1={sx(na.x)}
        y1={sy(na.y)}
        x2={sx(nb.x)}
        y2={sy(nb.y)}
        opacity={1 - u}
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
        class:data={p.kind === 'DATA'}
        cx={x}
        cy={y}
        r="4.5"
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
    {@const native = isNative(n.id)}
    {@const sup = isSuper(n.id)}
    {@const sel = sim.selected === n.id}
    {@const op = fgOpacity(n.id)}
    {#if fg}
      <circle class="fg-halo" cx={x} cy={y} r="26" opacity={0.15 + op * 0.55} />
    {/if}
    {#if sup}
      <circle class="super-halo" cx={x} cy={y} r="30" />
    {/if}
    {#if src}
      <rect
        class="node source"
        class:member={mem}
        class:fg
        class:native
        class:super={sup}
        class:selected={sel}
        x={x - 13}
        y={y - 13}
        width="26"
        height="26"
        role="button"
        tabindex="0"
        onclick={() => sim.select(n.id)}
        onkeydown={(e) => e.key === 'Enter' && sim.select(n.id)}
      />
    {:else}
      <circle
        class="node"
        class:fg
        class:member={mem}
        class:native
        class:super={sup}
        class:selected={sel}
        cx={x}
        cy={y}
        r="13"
        role="button"
        tabindex="0"
        onclick={() => sim.select(n.id)}
        onkeydown={(e) => e.key === 'Enter' && sim.select(n.id)}
      />
    {/if}
    <text class="label" class:on-source={src} x={x} y={y + 4} text-anchor="middle">{n.id}</text>
    {#if fg}
      <text class="badge" x={x + 16} y={y - 14}>FG</text>
    {/if}
    {#if native}
      <text class="badge native-badge" x={x + 16} y={y + (fg ? 0 : -14)}>NAT</text>
    {/if}
    {#if sup}
      <text class="badge super-badge" x={x - 28} y={y - 14}>SUPER</text>
    {/if}
  {/each}

  {#each drops as d (d.node + '-' + d.born)}
    {@const n = sim.topology.nodes.find((nn) => nn.id === d.node)}
    {#if n}
      {@const x = sx(n.x)}
      {@const y = sy(n.y)}
      {@const fade = 1 - Math.min(1, (now - d.born) / 700)}
      <g opacity={fade}>
        <text class="drop-x" x={x + 18} y={y + 6}>×</text>
        <text class="drop-r" x={x + 18} y={y + 18}>{d.reason}</text>
      </g>
    {/if}
  {/each}
</svg>

<style>
  .net {
    width: 100%;
    height: 100%;
    display: block;
    background: linear-gradient(165deg, #f8fafc 0%, #eef2f6 55%, #e8eef3 100%);
  }
  .link {
    stroke: #94a3b8;
    stroke-width: 1.4;
    opacity: 0.55;
  }
  .mesh {
    stroke: var(--amber);
    stroke-width: 3.2;
    opacity: 0.75;
  }
  .logical {
    stroke: var(--teal);
    stroke-width: 1.6;
    stroke-dasharray: 5 4;
    opacity: 0.7;
  }
  .rec {
    stroke: var(--coral);
    stroke-width: 2.4;
    stroke-dasharray: 2 3;
  }
  .super-halo {
    fill: none;
    stroke: var(--teal);
    stroke-width: 1.5;
    stroke-dasharray: 4 3;
    opacity: 0.55;
    pointer-events: none;
  }
  .node {
    fill: #fff;
    stroke: #64748b;
    stroke-width: 2;
    cursor: pointer;
    transition: stroke 120ms ease, fill 120ms ease;
  }
  .node:hover {
    stroke: var(--ink);
  }
  .node.source {
    fill: var(--source);
    stroke: #93c5fd;
  }
  .node.member {
    stroke: var(--member);
    stroke-width: 3;
  }
  .node.fg {
    stroke: var(--fg);
    stroke-width: 3;
  }
  .node.selected {
    filter: drop-shadow(0 0 0 2px rgba(21, 32, 43, 0.25));
  }
  .node.native {
    stroke-dasharray: 3 2;
  }
  .fg-halo {
    fill: var(--amber);
    pointer-events: none;
  }
  .label {
    fill: var(--ink);
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 500;
    pointer-events: none;
  }
  .label.on-source {
    fill: #fff;
  }
  .badge {
    fill: var(--amber);
    font-family: var(--sans);
    font-size: 9px;
    font-weight: 700;
    pointer-events: none;
  }
  .badge.native-badge {
    fill: var(--teal);
  }
  .badge.super-badge {
    fill: var(--teal);
    font-size: 8px;
  }
  .node.super {
    stroke: var(--teal);
  }
  .pkt {
    fill: var(--ink);
  }
  .pkt.jq {
    fill: var(--blue);
  }
  .pkt.jr {
    fill: var(--amber);
  }
  .pkt.data {
    fill: var(--teal);
  }
  .drop-x {
    fill: var(--coral);
    font-size: 16px;
    font-weight: 700;
    font-family: var(--sans);
  }
  .drop-r {
    fill: var(--coral);
    font-size: 9px;
    font-family: var(--mono);
  }
</style>
