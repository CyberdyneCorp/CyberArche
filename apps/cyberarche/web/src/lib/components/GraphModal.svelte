<script lang="ts">
	/** Obsidian-style link graph (wikilink-graph-view): a modal force-directed
	 * graph of a teamspace/folder's documents and their `[[…]]` links. Zoom with
	 * the wheel, drag to pan (or drag a node to move it), double-click a node to
	 * open its document. Rendered with a small self-contained force simulation. */
	import { goto } from '$app/navigation';
	import { folderGraph, teamspaceGraph, type LinkGraph } from '$lib/api/links';
	import { graphView } from '$lib/viewmodels/graph-view.svelte';

	let { workspaceId }: { workspaceId: string } = $props();

	const scope = $derived(graphView.current);

	interface SimNode {
		id: string;
		title: string;
		x: number;
		y: number;
		vx: number;
		vy: number;
		r: number;
	}
	// Simulation state is plain (non-reactive) and mutated every frame; a bumped
	// `frame` counter drives re-render, so 60fps updates don't thrash proxies.
	const sim: { nodes: SimNode[]; edges: { source: SimNode; target: SimNode }[] } = {
		nodes: [],
		edges: []
	};
	let frame = $state(0);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let empty = $state(false);

	// Pan/zoom transform (screen space).
	let tx = $state(0);
	let ty = $state(0);
	let scale = $state(1);

	let svgEl = $state<SVGSVGElement | null>(null);
	let width = $state(900);
	let height = $state(600);
	let raf = 0;
	let alpha = 0;

	const rendered = $derived.by(() => {
		void frame;
		return {
			nodes: sim.nodes.map((n) => ({ id: n.id, title: n.title, x: n.x, y: n.y, r: n.r })),
			edges: sim.edges.map((e) => ({ x1: e.source.x, y1: e.source.y, x2: e.target.x, y2: e.target.y }))
		};
	});

	function stop(): void {
		if (raf) cancelAnimationFrame(raf);
		raf = 0;
	}

	async function load(kind: 'teamspace' | 'folder', id: string): Promise<void> {
		stop();
		loading = true;
		error = null;
		empty = false;
		try {
			const graph: LinkGraph = kind === 'teamspace'
				? await teamspaceGraph(id)
				: await folderGraph(id);
			build(graph);
			empty = sim.nodes.length === 0;
		} catch {
			error = 'Could not load the graph.';
		} finally {
			loading = false;
		}
	}

	function build(graph: LinkGraph): void {
		const cx = width / 2;
		const cy = height / 2;
		const degree = new Map<string, number>();
		for (const e of graph.edges) {
			degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
			degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
		}
		const byId = new Map<string, SimNode>();
		graph.nodes.forEach((n, i) => {
			const angle = (2 * Math.PI * i) / Math.max(graph.nodes.length, 1);
			const node: SimNode = {
				id: n.id,
				title: n.title || 'Untitled',
				x: cx + Math.cos(angle) * 180 + (i % 3),
				y: cy + Math.sin(angle) * 180,
				vx: 0,
				vy: 0,
				r: 7 + Math.min(degree.get(n.id) ?? 0, 8) * 1.6
			};
			byId.set(n.id, node);
		});
		sim.nodes = [...byId.values()];
		sim.edges = graph.edges
			.map((e) => ({ source: byId.get(e.source)!, target: byId.get(e.target)! }))
			.filter((e) => e.source && e.target);
		tx = 0;
		ty = 0;
		scale = 1;
		alpha = 1;
		frame++;
		tick();
	}

	// One force step: pairwise repulsion, edge springs, gravity toward centre.
	const REPULSION = 5000;
	const SPRING = 0.03;
	const REST = 90;
	const GRAVITY = 0.015;
	const DAMPING = 0.85;

	function tick(): void {
		const nodes = sim.nodes;
		const cx = width / 2;
		const cy = height / 2;
		for (const n of nodes) {
			let fx = (cx - n.x) * GRAVITY;
			let fy = (cy - n.y) * GRAVITY;
			for (const m of nodes) {
				if (m === n) continue;
				const dx = n.x - m.x;
				const dy = n.y - m.y;
				const d2 = dx * dx + dy * dy + 0.01;
				const f = REPULSION / d2;
				const d = Math.sqrt(d2);
				fx += (dx / d) * f;
				fy += (dy / d) * f;
			}
			n.vx = (n.vx + fx) * DAMPING;
			n.vy = (n.vy + fy) * DAMPING;
		}
		for (const e of sim.edges) {
			const dx = e.target.x - e.source.x;
			const dy = e.target.y - e.source.y;
			const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
			const f = SPRING * (d - REST);
			const ux = (dx / d) * f;
			const uy = (dy / d) * f;
			e.source.vx += ux;
			e.source.vy += uy;
			e.target.vx -= ux;
			e.target.vy -= uy;
		}
		for (const n of nodes) {
			if (n === dragging) continue; // a dragged node is pinned to the cursor
			n.x += n.vx * alpha;
			n.y += n.vy * alpha;
		}
		alpha *= 0.985;
		frame++;
		if (alpha > 0.02 || dragging) raf = requestAnimationFrame(tick);
		else raf = 0;
	}

	function reheat(): void {
		alpha = Math.max(alpha, 0.3);
		if (!raf) raf = requestAnimationFrame(tick);
	}

	// Load whenever the scope opens/changes; stop the sim when it closes.
	$effect(() => {
		const s = scope;
		if (!s) {
			stop();
			return;
		}
		void load(s.kind, s.id);
		return stop;
	});

	$effect(() => {
		if (!svgEl) return;
		const ro = new ResizeObserver((entries) => {
			const r = entries[0]?.contentRect;
			if (r) {
				width = r.width;
				height = r.height;
			}
		});
		ro.observe(svgEl);
		return () => ro.disconnect();
	});

	// ---- pan / zoom / drag ----
	function toGraph(clientX: number, clientY: number): { x: number; y: number } {
		const rect = svgEl!.getBoundingClientRect();
		return { x: (clientX - rect.left - tx) / scale, y: (clientY - rect.top - ty) / scale };
	}

	function onWheel(e: WheelEvent): void {
		e.preventDefault();
		const rect = svgEl!.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const my = e.clientY - rect.top;
		const gx = (mx - tx) / scale;
		const gy = (my - ty) / scale;
		scale = Math.min(4, Math.max(0.2, scale * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
		tx = mx - gx * scale;
		ty = my - gy * scale;
	}

	let panning = false;
	let panX = 0;
	let panY = 0;
	let dragging: SimNode | null = null;

	function onNodeDown(e: PointerEvent, node: SimNode): void {
		e.stopPropagation();
		svgEl!.setPointerCapture(e.pointerId);
		dragging = node;
		reheat();
	}
	function onBgDown(e: PointerEvent): void {
		svgEl!.setPointerCapture(e.pointerId);
		panning = true;
		panX = e.clientX;
		panY = e.clientY;
	}
	function onMove(e: PointerEvent): void {
		if (dragging) {
			const p = toGraph(e.clientX, e.clientY);
			dragging.x = p.x;
			dragging.y = p.y;
			dragging.vx = 0;
			dragging.vy = 0;
			frame++;
			return;
		}
		if (panning) {
			tx += e.clientX - panX;
			ty += e.clientY - panY;
			panX = e.clientX;
			panY = e.clientY;
		}
	}
	function onUp(e: PointerEvent): void {
		svgEl?.releasePointerCapture(e.pointerId);
		dragging = null;
		panning = false;
	}

	function openDocument(id: string): void {
		graphView.close();
		void goto(`/w/${workspaceId}/d/${id}`);
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && scope && graphView.close()} />

{#if scope}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="scrim" role="presentation" onclick={() => graphView.close()}>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="panel"
			role="dialog"
			aria-label="Link graph"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
		>
			<header>
				<div class="title">
					<span class="ico">◕</span>
					<span>Graph — {scope.name}</span>
				</div>
				<div class="right">
					<span class="count">{sim.nodes.length} docs · {sim.edges.length} links</span>
					<button class="close" aria-label="Close" onclick={() => graphView.close()}>✕</button>
				</div>
			</header>

			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<svg
				bind:this={svgEl}
				class="canvas"
				data-testid="graph-canvas"
				onwheel={onWheel}
				onpointerdown={onBgDown}
				onpointermove={onMove}
				onpointerup={onUp}
				onpointercancel={onUp}
			>
				<g transform={`translate(${tx} ${ty}) scale(${scale})`}>
					{#each rendered.edges as e, i (i)}
						<line class="edge" x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} />
					{/each}
					{#each rendered.nodes as n (n.id)}
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<g
							class="node"
							transform={`translate(${n.x} ${n.y})`}
							onpointerdown={(e) => onNodeDown(e, sim.nodes.find((s) => s.id === n.id)!)}
							ondblclick={() => openDocument(n.id)}
						>
							<circle r={n.r} />
							<text y={n.r + 13} text-anchor="middle">{n.title}</text>
						</g>
					{/each}
				</g>
			</svg>

			{#if loading}
				<p class="hint">Loading graph…</p>
			{:else if error}
				<p class="hint error">{error}</p>
			{:else if empty}
				<p class="hint">No documents here yet, or none are linked with [[…]].</p>
			{:else}
				<p class="hint">Scroll to zoom · drag to pan · double-click a node to open it</p>
			{/if}
		</div>
	</div>
{/if}

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 80;
		display: grid;
		place-items: center;
		background: color-mix(in srgb, var(--bg1) 55%, transparent);
		backdrop-filter: blur(3px);
	}
	.panel {
		width: min(92vw, 1040px);
		height: min(88vh, 760px);
		display: flex;
		flex-direction: column;
		background: var(--bg2);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		box-shadow: var(--sh3);
		overflow: hidden;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 16px;
		border-bottom: 1px solid var(--line);
	}
	.title {
		display: flex;
		align-items: center;
		gap: 8px;
		font-weight: 600;
		color: var(--tx);
	}
	.ico {
		color: var(--acc);
	}
	.right {
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.count {
		font-size: 12px;
		color: var(--tx2);
		font-variant-numeric: tabular-nums;
	}
	.close {
		width: 28px;
		height: 28px;
		border-radius: var(--r-control);
		color: var(--tx2);
	}
	.close:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.canvas {
		flex: 1;
		width: 100%;
		background: var(--bg1);
		touch-action: none;
		cursor: grab;
	}
	.canvas:active {
		cursor: grabbing;
	}
	.edge {
		stroke: var(--line);
		stroke-width: 1.2;
	}
	.node {
		cursor: pointer;
	}
	.node circle {
		fill: var(--acc);
		stroke: var(--bg1);
		stroke-width: 2;
		transition: fill 0.12s;
	}
	.node:hover circle {
		fill: var(--acc-strong);
	}
	.node text {
		fill: var(--tx2);
		font-size: 11px;
		font-family: var(--font-ui);
		pointer-events: none;
		user-select: none;
	}
	.hint {
		margin: 0;
		padding: 8px 16px;
		border-top: 1px solid var(--line);
		font-size: 12px;
		color: var(--tx2);
		text-align: center;
	}
	.hint.error {
		color: var(--rose);
	}
</style>
