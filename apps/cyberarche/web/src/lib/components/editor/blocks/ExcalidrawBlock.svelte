<script lang="ts">
	/** Native Excalidraw block (native-excalidraw-canvas spec).
	 *
	 * Wraps the headless `@cyberdynecorp/excalidraw-svelte` `EditorStore` in a
	 * canvas host (render loop + pointer/pan/zoom) and a toolbar, and binds it to
	 * the document's shared Y.Doc via `@cyberdynecorp/excalidraw-yjs` — elements
	 * live in a per-block root map `excalidraw:<blockId>`, so they co-edit live
	 * and persist through the existing realtime transport with no backend change.
	 * The scene JSON is mirrored (debounced) into `data.scene` for export/agent. */
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';
	import { EditorStore } from '@cyberdynecorp/excalidraw-svelte';
	import { Point } from '@cyberdynecorp/excalidraw-svelte/math';
	import type { PointerType, Tool } from '@cyberdynecorp/excalidraw-svelte/editor';
	import { YjsCollab } from '@cyberdynecorp/excalidraw-yjs';

	let { block, editor }: BlockComponentProps = $props();
	const vm = editor as EditorVM;

	const store = new EditorStore();
	const collab = new YjsCollab(store, vm.doc, { elementsKey: `excalidraw:${block.id}` });

	// Seed from a mirrored/agent-authored scene before the doc hydrates, so a
	// scene stored only in `data.scene` (e.g. agent-created) shows on first open.
	// Element ids are stable, so re-seeding a persisted board merges idempotently.
	const seed = typeof block.data.scene === 'string' ? block.data.scene : '';
	if (seed) {
		try {
			store.loadDocument(seed);
		} catch {
			/* malformed scene: fall back to whatever the doc holds */
		}
	}

	// The whiteboard always renders on a light/white canvas (Excalidraw's default),
	// independent of the app's light/dark theme, so drawings read consistently.
	store.setTheme('light');
	collab.start();

	// Mirror local edits into `data.scene` (debounced) for export/agent/snapshot.
	// onChange fires on local edits only (not on applied remote elements), so
	// each editing client — and only it — writes the merged scene it now holds.
	const MIRROR_MS = 500;
	let mirrorTimer: ReturnType<typeof setTimeout> | null = null;
	const unsubscribe = store.onChange(() => {
		if (vm.readOnly) return;
		if (mirrorTimer) clearTimeout(mirrorTimer);
		mirrorTimer = setTimeout(
			() => vm.updateData(block.id, { scene: store.documentJSON() }),
			MIRROR_MS
		);
	});

	// The store is plain TS (non-reactive); poll its revision so the canvas
	// redraws and the toolbar re-derives after every local or remote change.
	let rev = $state(0);
	$effect(() => {
		const id = setInterval(() => (rev = store.revision), 40);
		return () => clearInterval(id);
	});
	const view = $derived.by(() => {
		void rev;
		return {
			tool: store.activeTool,
			canUndo: store.canUndo,
			canRedo: store.canRedo,
			zoom: store.zoomPercent,
			editing: store.editingText,
			selectedCount: store.selectedCount
		};
	});

	$effect(() => () => {
		unsubscribe();
		if (mirrorTimer) clearTimeout(mirrorTimer);
		collab.stop();
	});

	// ---- Canvas host (ported from the excalidraw-native demo) ----
	let canvas = $state<HTMLCanvasElement | null>(null);
	let wrapper = $state<HTMLDivElement | null>(null);
	let width = $state(800);
	let height = $state(420);
	let expanded = $state(false);
	let down = false;
	let panning = false;
	let lastPanX = 0;
	let lastPanY = 0;

	// Bitmap cache: the pure renderer delegates image drawing to the host.
	const imageCache = new Map<string, HTMLImageElement>();
	function imageFor(fileId: string): CanvasImageSource | null {
		const cached = imageCache.get(fileId);
		if (cached !== undefined) return cached.complete && cached.naturalWidth > 0 ? cached : null;
		const file = store.scene.files[fileId];
		if (file === undefined) return null;
		const img = new Image();
		img.onload = () => draw();
		img.src = file.dataURL;
		imageCache.set(fileId, img);
		return null;
	}

	function draw(): void {
		if (!canvas) return;
		const dpr = window.devicePixelRatio || 1;
		canvas.width = Math.floor(width * dpr);
		canvas.height = Math.floor(height * dpr);
		const ctx = canvas.getContext('2d');
		if (ctx === null) return;
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		const rc = ctx as unknown as Parameters<EditorStore['render']>[0];
		store.render(rc, width, height, imageFor);
		store.renderOverlay(rc, width, height);
	}

	$effect(() => {
		void rev;
		void width;
		void height;
		draw();
	});

	// Animate fading laser/eraser trails while one is active.
	$effect(() => {
		void rev;
		if (store.activeTool !== 'laser' && store.activeTool !== 'eraser') return;
		let raf = 0;
		const tick = (): void => {
			draw();
			raf = requestAnimationFrame(tick);
		};
		raf = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(raf);
	});

	$effect(() => {
		if (!wrapper) return;
		const ro = new ResizeObserver((entries) => {
			const r = entries[0]?.contentRect;
			if (r !== undefined) {
				width = r.width;
				height = r.height;
			}
		});
		ro.observe(wrapper);
		return () => ro.disconnect();
	});

	function toScene(e: PointerEvent): Point {
		const r = canvas!.getBoundingClientRect();
		return new Point(e.clientX - r.left, e.clientY - r.top);
	}
	function opts(e: PointerEvent) {
		return {
			type: (e.pointerType === 'pen' ? 'pen' : e.pointerType === 'touch' ? 'touch' : 'mouse') as PointerType,
			pressure: e.pressure || 0.5,
			shift: e.shiftKey,
			alt: e.altKey,
			toggle: e.metaKey || e.ctrlKey
		};
	}
	function startPan(e: PointerEvent): void {
		panning = true;
		lastPanX = e.clientX;
		lastPanY = e.clientY;
		canvas!.setPointerCapture(e.pointerId);
	}
	function onPointerDown(e: PointerEvent): void {
		if (e.button === 1 || vm.readOnly) {
			e.preventDefault();
			startPan(e);
			return;
		}
		if (e.button === 2) return; // reserve right button
		down = true;
		canvas!.setPointerCapture(e.pointerId);
		store.pointer('down', toScene(e), opts(e));
	}
	function onPointerMove(e: PointerEvent): void {
		if (panning) {
			store.panZoom(e.clientX - lastPanX, e.clientY - lastPanY, 1);
			lastPanX = e.clientX;
			lastPanY = e.clientY;
			return;
		}
		if (!down) return;
		store.pointer('move', toScene(e), opts(e));
	}
	function onPointerUp(e: PointerEvent): void {
		if (panning) {
			panning = false;
			canvas!.releasePointerCapture(e.pointerId);
			return;
		}
		if (!down) return;
		down = false;
		store.pointer('up', toScene(e), opts(e));
	}
	function onDblClick(e: MouseEvent): void {
		if (vm.readOnly) return;
		const r = canvas!.getBoundingClientRect();
		store.doubleClickAt(new Point(e.clientX - r.left, e.clientY - r.top));
	}
	function onWheel(e: WheelEvent): void {
		e.preventDefault();
		const r = canvas!.getBoundingClientRect();
		if (e.shiftKey && !e.ctrlKey && !e.metaKey) {
			store.panZoom(-(e.deltaY || e.deltaX), 0, 1);
			return;
		}
		store.zoomAtScreenPoint(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.1 : 1 / 1.1);
	}

	function importImage(e: Event): void {
		const file = (e.currentTarget as HTMLInputElement).files?.[0];
		(e.currentTarget as HTMLInputElement).value = '';
		if (file === undefined) return;
		const reader = new FileReader();
		reader.onload = () => {
			const dataURL = reader.result as string;
			const img = new Image();
			img.onload = () => store.insertImage(dataURL, file.type, img.naturalWidth, img.naturalHeight);
			img.src = dataURL;
		};
		reader.readAsDataURL(file);
	}

	let fileInput = $state<HTMLInputElement | null>(null);
	const MERMAID_SAMPLE = 'flowchart TD\n  A[Start] --> B{OK?}\n  B -->|Yes| C[Ship]\n  B -->|No| D[Fix]';

	const TOOLS: { tool: Tool; icon: string; title: string }[] = [
		{ tool: 'selection', icon: '⇱', title: 'Select' },
		{ tool: 'rectangle', icon: '▭', title: 'Rectangle' },
		{ tool: 'diamond', icon: '◇', title: 'Diamond' },
		{ tool: 'ellipse', icon: '◯', title: 'Ellipse' },
		{ tool: 'arrow', icon: '→', title: 'Arrow' },
		{ tool: 'line', icon: '／', title: 'Line' },
		{ tool: 'freedraw', icon: '✎', title: 'Draw' },
		{ tool: 'text', icon: 'T', title: 'Text' },
		{ tool: 'eraser', icon: '⌫', title: 'Erase' },
		{ tool: 'hand', icon: '✋', title: 'Pan' }
	];
</script>

<div class="excali" class:expanded data-testid="excalidraw-block">
	{#if !vm.readOnly}
		<header class="bar">
			<div class="tools" role="toolbar">
				{#each TOOLS as t (t.tool)}
					<button
						class:active={view.tool === t.tool}
						title={t.title}
						aria-label={t.title}
						data-testid={`ex-tool-${t.tool}`}
						onclick={() => store.selectTool(t.tool)}>{t.icon}</button
					>
				{/each}
			</div>
			<div class="actions">
				<button class="mini" title="Sticky note" onclick={() => store.insertStickyNote()}>▤</button>
				<button class="mini" title="Table" onclick={() => store.insertTable()}>▦</button>
				<button class="mini" title="Mermaid diagram" onclick={() => store.insertMermaid(MERMAID_SAMPLE)}>⿻</button>
				<button class="mini" title="Insert image" onclick={() => fileInput?.click()}>🖼</button>
				<input bind:this={fileInput} type="file" accept="image/*" hidden onchange={importImage} />
				<span class="sep"></span>
				<button class="mini" title="Undo" disabled={!view.canUndo} onclick={() => store.undo()}>↶</button>
				<button class="mini" title="Redo" disabled={!view.canRedo} onclick={() => store.redo()}>↷</button>
				<button class="mini" title="Duplicate" disabled={!view.selectedCount} onclick={() => store.duplicate()}>⧉</button>
				<button class="mini" title="Delete" disabled={!view.selectedCount} onclick={() => store.deleteSelected()}>🗑</button>
				<span class="sep"></span>
				<button class="mini" title="Zoom out" onclick={() => store.zoomOut()}>−</button>
				<button class="mini" title="Reset zoom" onclick={() => store.resetZoom()}>{view.zoom}%</button>
				<button class="mini" title="Zoom in" onclick={() => store.zoomIn()}>＋</button>
				<button
					class="mini"
					data-testid="ex-expand"
					title={expanded ? 'Collapse' : 'Expand'}
					onclick={() => (expanded = !expanded)}>{expanded ? '⤡' : '⤢'}</button
				>
			</div>
		</header>
	{/if}

	<div bind:this={wrapper} class="stage">
		<canvas
			bind:this={canvas}
			data-testid="ex-canvas"
			style="width:{width}px;height:{height}px"
			onpointerdown={onPointerDown}
			onpointermove={onPointerMove}
			onpointerup={onPointerUp}
			onpointercancel={onPointerUp}
			ondblclick={onDblClick}
			onwheel={onWheel}
		></canvas>
		{#if view.editing !== null}
			<!-- svelte-ignore a11y_autofocus -->
			<textarea
				class="text-editor"
				data-testid="ex-text-editor"
				autofocus
				style="left:{view.editing.viewX}px;top:{view.editing.viewY}px{view.editing.viewW
					? `;width:${view.editing.viewW}px;min-width:0;height:${view.editing.viewH}px`
					: ''}"
				value={view.editing.value}
				oninput={(e) => store.setEditingText((e.currentTarget as HTMLTextAreaElement).value)}
				onblur={() => store.commitText()}
				onkeydown={(e) => {
					if (e.key === 'Enter' && !e.shiftKey) {
						e.preventDefault();
						store.commitText();
					}
				}}
			></textarea>
		{/if}
	</div>
</div>

<style>
	.excali {
		background: var(--bg2);
		border-radius: var(--r-block);
		overflow: hidden;
		position: relative;
	}
	.excali.expanded {
		position: fixed;
		inset: 24px;
		z-index: 60;
		box-shadow: var(--sh3);
	}
	.bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		padding: 6px 10px;
		border-bottom: 1px solid var(--line);
		flex-wrap: wrap;
	}
	.tools,
	.actions {
		display: flex;
		gap: 2px;
		align-items: center;
	}
	.tools button,
	.mini {
		padding: 3px 8px;
		border-radius: var(--r-control);
		color: var(--tx2);
		font-size: 12px;
	}
	.tools button:hover:not(:disabled),
	.mini:hover:not(:disabled) {
		background: var(--bg3);
		color: var(--tx);
	}
	.tools button.active {
		background: var(--accbg2);
		color: var(--acc-strong);
	}
	.mini:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.sep {
		width: 1px;
		align-self: stretch;
		background: var(--line);
		margin: 0 4px;
	}
	.stage {
		position: relative;
	}
	canvas {
		display: block;
		width: 100%;
		height: 420px;
		/* The engine paints a white scene background; match it so no dark app
		   background shows through before the first frame. */
		background: #ffffff;
		touch-action: none;
	}
	.expanded .stage {
		height: calc(100% - 45px);
	}
	.expanded canvas {
		height: 100%;
	}
	.text-editor {
		position: absolute;
		min-width: 120px;
		min-height: 28px;
		font: 20px 'Excalifont', 'Virgil', 'Comic Sans MS', 'Segoe Print', cursive;
		border: 1px dashed var(--acc);
		background: transparent;
		color: var(--tx);
		resize: none;
		outline: none;
		padding: 0;
	}
</style>
