<script lang="ts">
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';
	import {
		arrowEndpoints,
		createWhiteboard,
		type WhiteboardElement,
		type WhiteboardVM
	} from '$lib/viewmodels/whiteboard.svelte';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;

	type Tool = 'select' | 'rect' | 'ellipse' | 'diamond' | 'text' | 'pen' | 'connect';
	let tool = $state<Tool>('select');
	let expanded = $state(false);
	let connectFrom = $state<string | null>(null);
	let editingLabel = $state<string | null>(null);

	// One whiteboard VM per block instance, over the shared Y.Doc.
	const board: WhiteboardVM = createWhiteboard(vm.doc, block.id, {
		initialElements: (block.data.elements ?? undefined) as
			| Record<string, WhiteboardElement>
			| undefined,
		onMirror: (elements) => vm.updateData(block.id, { elements })
	});
	$effect(() => () => board.destroy());

	let svg = $state<SVGSVGElement | null>(null);
	let drag: { id: string; lastX: number; lastY: number } | null = null;
	let stroke = $state<number[][]>([]);

	function point(event: PointerEvent): { x: number; y: number } {
		const rect = svg!.getBoundingClientRect();
		return { x: event.clientX - rect.left, y: event.clientY - rect.top };
	}

	function onCanvasPointerDown(event: PointerEvent) {
		const at = point(event);
		if (tool === 'pen') {
			stroke = [[at.x, at.y]];
			svg?.setPointerCapture(event.pointerId);
			return;
		}
		if (tool === 'rect' || tool === 'ellipse' || tool === 'diamond' || tool === 'text') {
			const shape = board.addShape(tool, at.x - 66, at.y - 23);
			editingLabel = shape.id;
			tool = 'select';
			return;
		}
		board.select(null);
		connectFrom = null;
	}

	function onCanvasPointerMove(event: PointerEvent) {
		if (stroke.length > 0 && tool === 'pen') {
			const at = point(event);
			stroke = [...stroke, [at.x, at.y]];
			return;
		}
		if (drag) {
			const at = point(event);
			board.moveBy(drag.id, at.x - drag.lastX, at.y - drag.lastY);
			drag = { ...drag, lastX: at.x, lastY: at.y };
		}
	}

	function onCanvasPointerUp() {
		if (tool === 'pen' && stroke.length > 1) {
			board.addPen(stroke);
		}
		stroke = [];
		drag = null;
	}

	function onShapePointerDown(event: PointerEvent, element: WhiteboardElement) {
		event.stopPropagation();
		if (tool === 'connect') {
			if (connectFrom === null) {
				connectFrom = element.id;
			} else if (connectFrom !== element.id) {
				board.connect(connectFrom, element.id);
				connectFrom = null;
				tool = 'select';
			}
			return;
		}
		board.select(element.id);
		const at = point(event);
		drag = { id: element.id, lastX: at.x, lastY: at.y };
		svg?.setPointerCapture(event.pointerId);
	}

	const shapes = $derived(board.elements.filter((e) => e.kind !== 'arrow'));
	const arrows = $derived(board.elements.filter((e) => e.kind === 'arrow'));

	const TOOLS: { id: Tool; icon: string; title: string }[] = [
		{ id: 'select', icon: '⇱', title: 'Select / move' },
		{ id: 'rect', icon: '▭', title: 'Rectangle' },
		{ id: 'ellipse', icon: '◯', title: 'Ellipse' },
		{ id: 'diamond', icon: '◇', title: 'Diamond' },
		{ id: 'text', icon: 'T', title: 'Text' },
		{ id: 'pen', icon: '✎', title: 'Freehand' },
		{ id: 'connect', icon: '→', title: 'Connect shapes' }
	];
</script>

<div class="whiteboard" class:expanded data-testid="whiteboard-block">
	<header class="bar">
		<div class="tools" role="toolbar">
			{#each TOOLS as item (item.id)}
				<button
					class:active={tool === item.id}
					title={item.title}
					aria-label={item.title}
					data-testid={`wb-tool-${item.id}`}
					onclick={() => {
						tool = item.id;
						connectFrom = null;
					}}>{item.icon}</button
				>
			{/each}
		</div>
		<div class="right-tools">
			{#if board.selectedId}
				<button
					class="mini"
					data-testid="wb-add-child"
					title="Add child node (mind map)"
					onclick={() => board.addChild(board.selectedId!)}>＋ child</button
				>
				<button
					class="mini"
					title="Delete element"
					onclick={() => board.remove(board.selectedId!)}>🗑</button
				>
			{/if}
			<button
				class="mini"
				title={expanded ? 'Collapse' : 'Expand'}
				data-testid="wb-expand"
				onclick={() => (expanded = !expanded)}>{expanded ? '⤡' : '⤢'}</button
			>
		</div>
	</header>

	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<svg
		bind:this={svg}
		class="canvas"
		role="application"
		aria-label="Whiteboard canvas"
		data-testid="wb-canvas"
		onpointerdown={onCanvasPointerDown}
		onpointermove={onCanvasPointerMove}
		onpointerup={onCanvasPointerUp}
	>
		<defs>
			<marker id="wb-arrow-{block.id}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
				<path d="M0,0 L8,4 L0,8 z" fill="var(--tx2)" />
			</marker>
		</defs>

		{#each arrows as arrow (arrow.id)}
			{@const line = arrowEndpoints(arrow, (id) => board.byId(id))}
			<line
				class="arrow"
				data-testid="wb-arrow"
				x1={line.x1}
				y1={line.y1}
				x2={line.x2}
				y2={line.y2}
				marker-end="url(#wb-arrow-{block.id})"
			/>
		{/each}

		{#each shapes as element (element.id)}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<g
				class="shape"
				class:selected={board.selectedId === element.id}
				class:connect-source={connectFrom === element.id}
				data-testid="wb-shape"
				data-kind={element.kind}
				onpointerdown={(event) => onShapePointerDown(event, element)}
				ondblclick={() => (editingLabel = element.id)}
			>
				{#if element.kind === 'rect'}
					<rect x={element.x} y={element.y} width={element.w} height={element.h} rx="8" />
				{:else if element.kind === 'ellipse'}
					<ellipse
						cx={element.x + element.w / 2}
						cy={element.y + element.h / 2}
						rx={element.w / 2}
						ry={element.h / 2}
					/>
				{:else if element.kind === 'diamond'}
					<polygon
						points={`${element.x + element.w / 2},${element.y} ${element.x + element.w},${element.y + element.h / 2} ${element.x + element.w / 2},${element.y + element.h} ${element.x},${element.y + element.h / 2}`}
					/>
				{:else if element.kind === 'pen'}
					<polyline
						class="pen"
						points={(element.points ?? []).map((p) => p.join(',')).join(' ')}
					/>
				{/if}
				{#if element.kind !== 'pen'}
					<text
						x={element.x + element.w / 2}
						y={element.y + element.h / 2 + 4}
						text-anchor="middle">{element.label}</text
					>
				{/if}
			</g>
		{/each}

		{#if stroke.length > 1}
			<polyline class="pen live" points={stroke.map((p) => p.join(',')).join(' ')} />
		{/if}
	</svg>

	{#if editingLabel}
		{@const target = board.byId(editingLabel)}
		{#if target}
			<input
				class="label-input input"
				style:left={`${target.x}px`}
				style:top={`${target.y + target.h + 46}px`}
				value={target.label}
				data-testid="wb-label-input"
				oninput={(event) =>
					board.setLabel(editingLabel!, (event.target as HTMLInputElement).value)}
				onblur={() => (editingLabel = null)}
				onkeydown={(event) => event.key === 'Enter' && (editingLabel = null)}
			/>
		{/if}
	{/if}
</div>

<style>
	.whiteboard {
		background: var(--bg2);
		border-radius: var(--r-block);
		overflow: hidden;
		position: relative;
	}
	.whiteboard.expanded {
		position: fixed;
		inset: 24px;
		z-index: 60;
		box-shadow: var(--sh3);
	}
	.bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 6px 10px;
		border-bottom: 1px solid var(--line);
	}
	.tools {
		display: flex;
		gap: 2px;
	}
	.tools button,
	.mini {
		padding: 3px 8px;
		border-radius: var(--r-control);
		color: var(--tx2);
		font-size: 12px;
	}
	.tools button:hover,
	.mini:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.tools button.active {
		background: var(--accbg2);
		color: var(--acc-strong);
	}
	.right-tools {
		display: flex;
		gap: 4px;
	}
	.canvas {
		display: block;
		width: 100%;
		height: 420px;
		background: var(--bg1);
		touch-action: none;
		cursor: crosshair;
	}
	.expanded .canvas {
		height: calc(100% - 37px);
	}
	.shape {
		cursor: grab;
	}
	.shape rect,
	.shape ellipse,
	.shape polygon {
		fill: var(--accbg);
		stroke: var(--acc);
		stroke-width: 1.6;
	}
	.shape.selected rect,
	.shape.selected ellipse,
	.shape.selected polygon {
		stroke: var(--acc-strong);
		stroke-width: 2.4;
	}
	.shape.connect-source rect,
	.shape.connect-source ellipse,
	.shape.connect-source polygon {
		stroke-dasharray: 4 3;
	}
	.shape text {
		fill: var(--tx);
		font-size: 12.5px;
		font-family: var(--font-ui);
		user-select: none;
		pointer-events: none;
	}
	.pen {
		fill: none;
		stroke: var(--tx2);
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.pen.live {
		stroke: var(--acc);
	}
	.arrow {
		stroke: var(--tx2);
		stroke-width: 1.6;
	}
	.label-input {
		position: absolute;
		width: 150px;
		font-size: 12px;
		z-index: 5;
	}
</style>
