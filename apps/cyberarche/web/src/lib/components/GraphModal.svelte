<script lang="ts">
	/** Wikilink graph explorer (wikilink-graph-view + graph-explorer): a modal
	 * force-directed graph of a teamspace/folder's documents and their `[[…]]`
	 * links. Scroll to zoom, drag to pan (or drag a node), click a node to
	 * inspect it (degree, neighbours, open), double-click to open its document.
	 * Metrics are computed client-side from the returned nodes + directed edges. */
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
		inDeg: number;
		outDeg: number;
	}
	const sim: { nodes: SimNode[]; edges: { source: SimNode; target: SimNode }[] } = {
		nodes: [],
		edges: []
	};
	const neighbours = new Map<string, Set<string>>();
	let frame = $state(0);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let empty = $state(false);
	let isolated = $state(0);
	let selectedId = $state<string | null>(null);
	let query = $state('');

	let tx = $state(0);
	let ty = $state(0);
	let scale = $state(1);
	let svgEl = $state<SVGSVGElement | null>(null);
	let width = $state(900);
	let height = $state(560);
	let raf = 0;
	let alpha = 0;
	let fitPending = false;

	const selected = $derived(sim.nodes.find((n) => n.id === selectedId) ?? null);
	const selectedNeighbours = $derived(selectedId ? (neighbours.get(selectedId) ?? new Set()) : null);

	const rendered = $derived.by(() => {
		void frame;
		const active = selectedNeighbours;
		return {
			nodes: sim.nodes.map((n) => ({
				id: n.id,
				title: n.title,
				x: n.x,
				y: n.y,
				r: n.r,
				dim: !!active && n.id !== selectedId && !active.has(n.id),
				sel: n.id === selectedId,
				match: query.trim().length > 0 && n.title.toLowerCase().includes(query.trim().toLowerCase())
			})),
			edges: sim.edges.map((e) => {
				const dx = e.target.x - e.source.x;
				const dy = e.target.y - e.source.y;
				const d = Math.sqrt(dx * dx + dy * dy) || 1;
				const ux = dx / d;
				const uy = dy / d;
				const hot = e.source.id === selectedId || e.target.id === selectedId;
				return {
					x1: e.source.x + ux * e.source.r,
					y1: e.source.y + uy * e.source.r,
					x2: e.target.x - ux * (e.target.r + 6),
					y2: e.target.y - uy * (e.target.r + 6),
					hot,
					dim: !!active && !hot
				};
			})
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
		selectedId = null;
		query = '';
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
		const inDeg = new Map<string, number>();
		const outDeg = new Map<string, number>();
		neighbours.clear();
		for (const n of graph.nodes) neighbours.set(n.id, new Set());
		for (const e of graph.edges) {
			outDeg.set(e.source, (outDeg.get(e.source) ?? 0) + 1);
			inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
			neighbours.get(e.source)?.add(e.target);
			neighbours.get(e.target)?.add(e.source);
		}
		const byId = new Map<string, SimNode>();
		graph.nodes.forEach((n, i) => {
			const deg = (inDeg.get(n.id) ?? 0) + (outDeg.get(n.id) ?? 0);
			const angle = (2 * Math.PI * i) / Math.max(graph.nodes.length, 1);
			byId.set(n.id, {
				id: n.id,
				title: n.title || 'Untitled',
				x: cx + Math.cos(angle) * 200 + (i % 3),
				y: cy + Math.sin(angle) * 200,
				vx: 0,
				vy: 0,
				r: 9 + Math.min(deg, 10) * 1.8,
				inDeg: inDeg.get(n.id) ?? 0,
				outDeg: outDeg.get(n.id) ?? 0
			});
		});
		sim.nodes = [...byId.values()];
		sim.edges = graph.edges
			.map((e) => ({ source: byId.get(e.source)!, target: byId.get(e.target)! }))
			.filter((e) => e.source && e.target);
		isolated = sim.nodes.filter((n) => n.inDeg + n.outDeg === 0).length;
		tx = 0;
		ty = 0;
		scale = 1;
		alpha = 1;
		fitPending = true;
		frame++;
		tick();
	}

	const REPULSION = 6500;
	const SPRING = 0.03;
	const REST = 110;
	const GRAVITY = 0.012;
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
			if (n === dragging) continue;
			n.x += n.vx * alpha;
			n.y += n.vy * alpha;
		}
		alpha *= 0.985;
		frame++;
		if (fitPending && alpha < 0.2) {
			fitPending = false;
			fitView();
		}
		if (alpha > 0.02 || dragging) raf = requestAnimationFrame(tick);
		else raf = 0;
	}

	function reheat(): void {
		alpha = Math.max(alpha, 0.3);
		if (!raf) raf = requestAnimationFrame(tick);
	}

	function fitView(): void {
		if (!sim.nodes.length) return;
		let minX = Infinity;
		let minY = Infinity;
		let maxX = -Infinity;
		let maxY = -Infinity;
		for (const n of sim.nodes) {
			minX = Math.min(minX, n.x - n.r);
			minY = Math.min(minY, n.y - n.r);
			maxX = Math.max(maxX, n.x + n.r);
			maxY = Math.max(maxY, n.y + n.r);
		}
		const pad = 80;
		const gw = maxX - minX || 1;
		const gh = maxY - minY || 1;
		scale = Math.min(2, Math.max(0.3, Math.min((width - pad) / gw, (height - pad) / gh)));
		tx = width / 2 - ((minX + maxX) / 2) * scale;
		ty = height / 2 - ((minY + maxY) / 2) * scale;
		frame++;
	}

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

	// ---- pan / zoom / drag / click ----
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
		scale = Math.min(4, Math.max(0.15, scale * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
		tx = mx - gx * scale;
		ty = my - gy * scale;
	}
	function zoomBy(factor: number): void {
		const gx = (width / 2 - tx) / scale;
		const gy = (height / 2 - ty) / scale;
		scale = Math.min(4, Math.max(0.15, scale * factor));
		tx = width / 2 - gx * scale;
		ty = height / 2 - gy * scale;
	}

	let panning = false;
	let panX = 0;
	let panY = 0;
	let dragging: SimNode | null = null;
	let moved = false;
	// Manual double-click: pointer capture on a node swallows the browser's
	// dblclick, so detect two quick taps on the same node ourselves.
	let lastTap = { id: '', t: 0 };

	function onNodeDown(e: PointerEvent, node: SimNode): void {
		e.stopPropagation();
		if (lastTap.id === node.id && e.timeStamp - lastTap.t < 350) {
			lastTap = { id: '', t: 0 };
			openDocument(node.id);
			return;
		}
		lastTap = { id: node.id, t: e.timeStamp };
		svgEl!.setPointerCapture(e.pointerId);
		dragging = node;
		moved = false;
		reheat();
	}
	function onBgDown(e: PointerEvent): void {
		svgEl!.setPointerCapture(e.pointerId);
		panning = true;
		moved = false;
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
			moved = true;
			frame++;
			return;
		}
		if (panning) {
			tx += e.clientX - panX;
			ty += e.clientY - panY;
			panX = e.clientX;
			panY = e.clientY;
			moved = true;
		}
	}
	function onUp(e: PointerEvent): void {
		svgEl?.releasePointerCapture(e.pointerId);
		if (dragging && !moved) selectedId = dragging.id; // a click selects
		else if (panning && !moved) selectedId = null; // click on empty deselects
		dragging = null;
		panning = false;
	}

	function openDocument(id: string): void {
		graphView.close();
		void goto(`/w/${workspaceId}/d/${id}`);
	}
	function focusNode(id: string): void {
		selectedId = id;
		const n = sim.nodes.find((s) => s.id === id);
		if (!n) return;
		scale = Math.min(2, Math.max(scale, 1));
		tx = width / 2 - n.x * scale;
		ty = height / 2 - n.y * scale;
	}
	function runSearch(): void {
		const q = query.trim().toLowerCase();
		if (!q) return;
		const hit = sim.nodes.find((n) => n.title.toLowerCase().includes(q));
		if (hit) focusNode(hit.id);
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && scope && graphView.close()} />

{#if scope}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="scrim" role="presentation" onclick={() => graphView.close()}>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="panel" role="dialog" aria-label="Link graph" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<header>
				<div class="title"><span class="ico">◕</span><span>Graph — {scope.name}</span></div>
				<div class="tools">
					<input
						class="search"
						placeholder="Search documents…"
						bind:value={query}
						data-testid="graph-search"
						onkeydown={(e) => e.key === 'Enter' && runSearch()}
					/>
					<button class="tbtn" title="Fit to view" data-testid="graph-fit" onclick={fitView}>⤢ Fit</button>
					<button class="close" aria-label="Close" onclick={() => graphView.close()}>✕</button>
				</div>
			</header>

			<div class="body">
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
					<defs>
						<marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
							<path d="M0,0 L10,5 L0,10 z" fill="var(--tx3)" />
						</marker>
					</defs>
					<g transform={`translate(${tx} ${ty}) scale(${scale})`}>
						{#each rendered.edges as e, i (i)}
							<line
								class="edge"
								class:hot={e.hot}
								class:dim={e.dim}
								x1={e.x1}
								y1={e.y1}
								x2={e.x2}
								y2={e.y2}
								marker-end="url(#graph-arrow)"
							/>
						{/each}
						{#each rendered.nodes as n (n.id)}
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<g
								class="node"
								class:sel={n.sel}
								class:dim={n.dim}
								class:match={n.match}
								transform={`translate(${n.x} ${n.y})`}
								onpointerdown={(e) => onNodeDown(e, sim.nodes.find((s) => s.id === n.id)!)}
							>
								<circle r={n.r} />
								<text y={n.r + 14} text-anchor="middle">{n.title}</text>
							</g>
						{/each}
					</g>
				</svg>

				{#if selected}
					<aside class="inspector" data-testid="graph-inspector">
						<div class="insp-head">
							<span class="doc-ico">▤</span>
							<div>
								<div class="insp-title">{selected.title}</div>
								<div class="insp-sub">Document</div>
							</div>
						</div>
						<dl class="metrics">
							<div><dt>Incoming</dt><dd>{selected.inDeg}</dd></div>
							<div><dt>Outgoing</dt><dd>{selected.outDeg}</dd></div>
							<div><dt>Connections</dt><dd>{selected.inDeg + selected.outDeg}</dd></div>
						</dl>
						{#if selectedNeighbours && selectedNeighbours.size > 0}
							<div class="insp-section">Connected to</div>
							<div class="neighbours">
								{#each sim.nodes.filter((n) => selectedNeighbours.has(n.id)) as nb (nb.id)}
									<button class="nb" onclick={() => focusNode(nb.id)}>{nb.title}</button>
								{/each}
							</div>
						{:else}
							<p class="insp-note">No links yet — this document is isolated.</p>
						{/if}
						<div class="insp-actions">
							<button class="primary" data-testid="graph-open" onclick={() => openDocument(selected!.id)}>Open document ↗</button>
							<button class="ghost" onclick={() => focusNode(selected!.id)}>Focus</button>
						</div>
					</aside>
				{/if}
			</div>

			<footer class="status">
				{#if loading}
					<span>Loading graph…</span>
				{:else if error}
					<span class="err">{error}</span>
				{:else if empty}
					<span>No documents here yet, or none linked with [[…]].</span>
				{:else}
					<span class="stat">{sim.nodes.length} documents · {sim.edges.length} links{isolated ? ` · ${isolated} isolated` : ''}</span>
					<span class="spacer"></span>
					<span class="hint">Click a node to inspect · double-click to open · scroll to zoom · drag to pan</span>
				{/if}
				<span class="spacer"></span>
				<div class="zoom">
					<button aria-label="Zoom out" onclick={() => zoomBy(1 / 1.2)}>−</button>
					<button aria-label="Zoom in" onclick={() => zoomBy(1.2)}>+</button>
				</div>
			</footer>
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
		width: min(94vw, 1180px);
		height: min(90vh, 820px);
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
		gap: 12px;
		padding: 10px 14px;
		border-bottom: 1px solid var(--line);
	}
	.title {
		display: flex;
		align-items: center;
		gap: 8px;
		font-weight: 600;
		color: var(--tx);
		white-space: nowrap;
	}
	.ico {
		color: var(--acc);
	}
	.tools {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.search {
		width: 200px;
		padding: 5px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg1);
		color: var(--tx);
		font-size: 12.5px;
	}
	.tbtn {
		padding: 5px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		color: var(--tx2);
		font-size: 12.5px;
	}
	.tbtn:hover {
		background: var(--bg3);
		color: var(--tx);
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
	.body {
		flex: 1;
		display: flex;
		min-height: 0;
	}
	.canvas {
		flex: 1;
		background: var(--bg1);
		touch-action: none;
		cursor: grab;
	}
	.canvas:active {
		cursor: grabbing;
	}
	.edge {
		stroke: var(--line2, var(--line));
		stroke-width: 1.3;
		transition: opacity 0.15s;
	}
	.edge.hot {
		stroke: var(--acc);
		stroke-width: 2;
	}
	.edge.dim {
		opacity: 0.15;
	}
	.node {
		cursor: pointer;
	}
	.node circle {
		fill: var(--acc);
		stroke: var(--bg1);
		stroke-width: 2.5;
		transition: opacity 0.15s;
	}
	.node:hover circle,
	.node.sel circle {
		fill: var(--acc-strong);
	}
	.node.sel circle {
		stroke: var(--acc-strong);
	}
	.node.match circle {
		fill: #f59e0b;
	}
	.node.dim {
		opacity: 0.28;
	}
	.node text {
		fill: var(--tx2);
		font-size: 12px;
		font-family: var(--font-ui);
		pointer-events: none;
		user-select: none;
	}
	.node.sel text {
		fill: var(--tx);
		font-weight: 600;
	}
	.inspector {
		width: 288px;
		min-width: 288px;
		border-left: 1px solid var(--line);
		background: var(--bg2);
		padding: 16px;
		overflow-y: auto;
	}
	.insp-head {
		display: flex;
		gap: 10px;
		align-items: center;
		margin-bottom: 14px;
	}
	.doc-ico {
		display: grid;
		place-items: center;
		width: 34px;
		height: 34px;
		border-radius: 9px;
		background: var(--accbg2);
		color: var(--acc-strong);
	}
	.insp-title {
		font-weight: 600;
		color: var(--tx);
		line-height: 1.25;
	}
	.insp-sub {
		font-size: 11.5px;
		color: var(--tx3);
	}
	.metrics {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 8px;
		margin: 0 0 14px;
	}
	.metrics div {
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		padding: 8px;
		text-align: center;
	}
	.metrics dt {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--tx3);
	}
	.metrics dd {
		margin: 2px 0 0;
		font-size: 18px;
		font-weight: 600;
		color: var(--tx);
		font-variant-numeric: tabular-nums;
	}
	.insp-section {
		font-size: 10.5px;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--tx3);
		margin-bottom: 6px;
	}
	.neighbours {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin-bottom: 14px;
	}
	.nb {
		text-align: left;
		padding: 6px 9px;
		border-radius: var(--r-control);
		background: var(--bg1);
		border: 1px solid var(--line);
		color: var(--tx);
		font-size: 12.5px;
	}
	.nb:hover {
		border-color: var(--acc);
	}
	.insp-note {
		font-size: 12.5px;
		color: var(--tx2);
		margin: 0 0 14px;
	}
	.insp-actions {
		display: flex;
		gap: 8px;
	}
	.insp-actions .primary {
		flex: 1;
		padding: 8px;
		border-radius: var(--r-control);
		background: var(--acc);
		color: #fff;
		font-weight: 600;
		font-size: 12.5px;
	}
	.insp-actions .ghost {
		padding: 8px 12px;
		border-radius: var(--r-control);
		border: 1px solid var(--line);
		color: var(--tx2);
		font-size: 12.5px;
	}
	.insp-actions .ghost:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.status {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 7px 14px;
		border-top: 1px solid var(--line);
		font-size: 12px;
		color: var(--tx2);
	}
	.status .err {
		color: var(--rose);
	}
	.status .stat {
		font-variant-numeric: tabular-nums;
		color: var(--tx);
	}
	.status .hint {
		color: var(--tx3);
	}
	.spacer {
		flex: 1;
	}
	.zoom {
		display: flex;
		gap: 2px;
	}
	.zoom button {
		width: 26px;
		height: 24px;
		border-radius: var(--r-control);
		border: 1px solid var(--line);
		color: var(--tx2);
	}
	.zoom button:hover {
		background: var(--bg3);
		color: var(--tx);
	}
</style>
