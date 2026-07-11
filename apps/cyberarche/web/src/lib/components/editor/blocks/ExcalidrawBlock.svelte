<script lang="ts">
	/** Native Excalidraw block (native-excalidraw-canvas spec).
	 *
	 * Wraps the headless `@cyberdynecorp/excalidraw-svelte` `EditorStore` (0.7.x)
	 * in a canvas host (render loop + pointer/pan/zoom, hover-driven
	 * click-to-connect, double-click bound labels) and an excalidraw-style
	 * floating toolbar island, bound to the document's shared Y.Doc via
	 * `@cyberdynecorp/excalidraw-yjs` (per-block root map `excalidraw:<blockId>`)
	 * for element-level collaborative merge over the existing realtime transport.
	 * The scene JSON is mirrored (debounced) into `data.scene` for export/agent. */
	import type { BlockComponentProps } from '$lib/editor/registry';
	import type { EditorVM } from '$lib/viewmodels/editor.svelte';
	import { theme } from '$lib/viewmodels/theme.svelte';
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
	collab.start();

	// Follow the app's light/dark theme (0.7 remaps element colours so dark mode
	// is legible; files/exports keep canonical colours).
	$effect(() => store.setTheme(theme.mode));

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

	// ---- Canvas host ----
	let canvas = $state<HTMLCanvasElement | null>(null);
	let wrapper = $state<HTMLDivElement | null>(null);
	let width = $state(800);
	let height = $state(460);
	let expanded = $state(false);
	let hovered = $state(false);
	let moreOpen = $state(false);
	let down = false;
	let panning = false;
	let lastPanX = 0;
	let lastPanY = 0;

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
		void theme.mode;
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
		moreOpen = false;
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
		// Hover tracking drives the binding highlight + click-to-connect preview.
		store.trackPointer(toScene(e));
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

	let fileInput = $state<HTMLInputElement | null>(null);
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
	const MERMAID_SAMPLE = 'flowchart TD\n  A[Start] --> B{OK?}\n  B -->|Yes| C[Ship]\n  B -->|No| D[Fix]';

	// ---- Toolbar composition ----
	// The block hosts the editor in a document, so its chrome is trimmed to fit.
	// The engine keeps every capability regardless; these flags only control what
	// the toolbar exposes — flip one line to show/hide a group.
	const SHOW_IMAGE = false; // image-insert button (badge 9)
	const SHOW_MORE_TOOLS = false; // ⧉ menu: Frame, Laser + generators
	const SHOW_HINT = false; // helper line under the toolbar
	const SHOW_ZOOM_HISTORY = true; // bottom-left zoom + undo/redo island

	// ---- Keyboard shortcuts (scoped to hover so typing in other blocks is safe) ----
	const toolKeys: Record<string, Tool> = {
		v: 'selection', r: 'rectangle', d: 'diamond', o: 'ellipse', a: 'arrow',
		l: 'line', p: 'freedraw', t: 'text', e: 'eraser', h: 'hand',
		'1': 'selection', '2': 'rectangle', '3': 'diamond', '4': 'ellipse', '5': 'arrow',
		'6': 'line', '7': 'freedraw', '8': 'text', '0': 'eraser',
		// Frame/Laser are only reachable when their menu is shown.
		...(SHOW_MORE_TOOLS ? { f: 'frame' as Tool, k: 'laser' as Tool } : {})
	};
	function handleModifierKey(e: KeyboardEvent, key: string): boolean {
		if (key === 'z') {
			e.preventDefault();
			e.shiftKey ? store.redo() : store.undo();
			return true;
		}
		if (key === 'd') {
			e.preventDefault();
			store.duplicate();
			return true;
		}
		if (key === 'a') {
			e.preventDefault();
			store.selectAll();
			return true;
		}
		return true; // swallow other Cmd/Ctrl combos so they don't switch tools
	}
	function onKeydown(e: KeyboardEvent): void {
		if (!hovered || vm.readOnly) return;
		if (e.key === 'Escape') {
			if (moreOpen) moreOpen = false;
			else if (view.editing !== null) store.commitText();
			else store.cancelPendingArrow();
			return;
		}
		if (view.editing !== null) return; // the text editor owns every other key
		const tag = (e.target as HTMLElement | null)?.tagName ?? '';
		if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
		if (e.metaKey || e.ctrlKey) {
			handleModifierKey(e, e.key.toLowerCase());
			return;
		}
		if (e.key === 'Backspace' || e.key === 'Delete') {
			store.deleteSelected();
			return;
		}
		if (SHOW_IMAGE && e.key === '9') {
			fileInput?.click();
			return;
		}
		const tool = toolKeys[e.key.toLowerCase()];
		if (tool !== undefined) store.selectTool(tool);
	}

	// ---- Toolbar ----
	const svg = (body: string) =>
		`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
	const icons: Record<string, string> = {
		hand: svg('<path d="M8 11.5V5.7a1.45 1.45 0 0 1 2.9 0V10"/><path d="M10.9 10V4.2a1.45 1.45 0 0 1 2.9 0V10"/><path d="M13.8 10.3V5.4a1.45 1.45 0 0 1 2.9 0v6.1"/><path d="M16.7 9.9a1.45 1.45 0 0 1 2.9 0v4.6a7 7 0 0 1-7 7h-1.1c-1.9 0-3.4-.6-4.6-1.8l-3.3-3.4a1.55 1.55 0 0 1 2.2-2.2L8 16.2v-4.7"/>'),
		selection: svg('<path d="M6 3.5 18.5 12l-6 1.3L10 19.5z"/>'),
		rectangle: svg('<rect x="4" y="5" width="16" height="14" rx="2"/>'),
		diamond: svg('<path d="M12 3l8.5 9-8.5 9-8.5-9z"/>'),
		ellipse: svg('<circle cx="12" cy="12" r="8.5"/>'),
		arrow: svg('<path d="M5 19 19 5"/><path d="M11.5 5H19v7.5"/>'),
		line: svg('<path d="M5 17h14"/>'),
		freedraw: svg('<path d="M4.5 19.5l1-4L16.7 4.3a2 2 0 0 1 2.9 3L8.5 18.5l-4 1z"/>'),
		text: svg('<path d="M5.5 6V4.5h13V6"/><path d="M12 4.5v15"/><path d="M9.5 19.5h5"/>'),
		image: svg('<rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9.2" cy="10" r="1.4"/><path d="M5 17l4.5-4.5 3.5 3.5 2.3-2.3L19 17"/>'),
		eraser: svg('<path d="M7.5 20h11"/><path d="M5 14.5 12.8 6.7a2 2 0 0 1 2.8 0l2.7 2.7a2 2 0 0 1 0 2.8L13.5 17H9.8z"/>'),
		frame: svg('<path d="M4.5 8h15M4.5 16h15M8 4.5v15M16 4.5v15"/>'),
		laser: svg('<circle cx="12" cy="12" r="2.6"/><path d="M12 4.5V6M12 18v1.5M4.5 12H6M18 12h1.5M6.7 6.7l1.1 1.1M16.2 16.2l1.1 1.1M17.3 6.7l-1.1 1.1M7.8 16.2l-1.1 1.1"/>'),
		note: svg('<path d="M5 4.5h14v9.5l-4.5 5.5H5z"/><path d="M14.5 19.5V14H19"/>'),
		table: svg('<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M4 10h16M10 10v9M15 10v9"/>'),
		chart: svg('<path d="M4.5 4.5v15h15"/><path d="M8 16v-4M12 16V8M16 16v-6"/>'),
		mermaid: svg('<rect x="4" y="4" width="7.5" height="5" rx="1"/><rect x="12.5" y="15" width="7.5" height="5" rx="1"/><path d="M7.75 9v4.5a2 2 0 0 0 2 2h2.75M16.25 15v-3"/>'),
		shapes: svg('<rect x="4" y="4" width="8.5" height="8.5" rx="1.5"/><circle cx="16" cy="16" r="4.5"/><path d="M16 4.5v6M13 7.5h6"/>'),
		undo: svg('<path d="M9 7 4.5 11.5 9 16"/><path d="M4.5 11.5H14a5.5 5.5 0 0 1 0 11h-2"/>'),
		redo: svg('<path d="M15 7l4.5 4.5L15 16"/><path d="M19.5 11.5H10a5.5 5.5 0 0 0 0 11h2"/>'),
		trash: svg('<path d="M5 6.5h14M9.5 6.5V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.5M7 6.5l.8 12a1 1 0 0 0 1 .9h6.4a1 1 0 0 0 1-.9l.8-12"/>'),
		expand: svg('<path d="M9 4.5H4.5V9M15 4.5h4.5V9M9 19.5H4.5V15M15 19.5h4.5V15"/>'),
		collapse: svg('<path d="M4.5 9H9V4.5M19.5 9H15V4.5M4.5 15H9v4.5M19.5 15H15v4.5"/>')
	};
	const toolDefs: { tool: Tool; badge: string; title: string }[] = [
		{ tool: 'hand', badge: 'H', title: 'Hand (pan) — H' },
		{ tool: 'selection', badge: '1', title: 'Select — 1 or V' },
		{ tool: 'rectangle', badge: '2', title: 'Rectangle — 2 or R' },
		{ tool: 'diamond', badge: '3', title: 'Diamond — 3 or D' },
		{ tool: 'ellipse', badge: '4', title: 'Ellipse — 4 or O' },
		{ tool: 'arrow', badge: '5', title: 'Arrow — 5 or A' },
		{ tool: 'line', badge: '6', title: 'Line — 6 or L' },
		{ tool: 'freedraw', badge: '7', title: 'Draw — 7 or P' },
		{ tool: 'text', badge: '8', title: 'Text — 8 or T' },
		{ tool: 'eraser', badge: '0', title: 'Eraser — 0 or E' }
	];
	function pick(tool: Tool): void {
		store.selectTool(tool);
		moreOpen = false;
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div
	class="excali"
	class:expanded
	data-theme={theme.mode}
	data-testid="excalidraw-block"
	role="group"
	onpointerenter={() => (hovered = true)}
	onpointerleave={() => (hovered = false)}
>
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

		{#if !vm.readOnly}
			<!-- Floating tool island (excalidraw-style) -->
			<div class="top-center">
				<div class="island toolbar" role="toolbar" aria-label="Drawing tools">
					{#each toolDefs as t (t.tool)}
						<button
							class="tool"
							class:active={view.tool === t.tool}
							title={t.title}
							aria-label={t.title}
							data-testid={`ex-tool-${t.tool}`}
							onclick={() => pick(t.tool)}
						>
							<!-- eslint-disable-next-line svelte/no-at-html-tags -->
							{@html icons[t.tool]}
							<span class="badge">{t.badge}</span>
						</button>
					{/each}
					{#if SHOW_IMAGE || SHOW_MORE_TOOLS}
						<span class="divider"></span>
					{/if}
					{#if SHOW_IMAGE}
						<button
							class="tool"
							title="Insert image — 9"
							aria-label="Insert image — 9"
							data-testid="ex-gen-image"
							onclick={() => fileInput?.click()}
						>
							{@html icons.image}<span class="badge">9</span>
						</button>
					{/if}
					{#if SHOW_MORE_TOOLS}
						<button
							class="tool"
							title="More tools"
							aria-label="More tools"
							aria-expanded={moreOpen}
							data-testid="ex-more"
							class:active={moreOpen || view.tool === 'frame' || view.tool === 'laser'}
							onclick={() => (moreOpen = !moreOpen)}
						>
							{@html icons.shapes}
						</button>
						{#if moreOpen}
							<div class="island more-menu" role="menu">
								<button class="menu-item" class:active={view.tool === 'frame'} onclick={() => pick('frame')}>
									<span class="mi-icon">{@html icons.frame}</span>Frame<kbd>F</kbd>
								</button>
								<button class="menu-item" class:active={view.tool === 'laser'} onclick={() => pick('laser')}>
									<span class="mi-icon">{@html icons.laser}</span>Laser pointer<kbd>K</kbd>
								</button>
								<div class="menu-head">Generate</div>
								<button class="menu-item" onclick={() => { store.insertStickyNote(); moreOpen = false; }}>
									<span class="mi-icon">{@html icons.note}</span>Sticky note
								</button>
								<button class="menu-item" onclick={() => { store.insertTable(); moreOpen = false; }}>
									<span class="mi-icon">{@html icons.table}</span>Table
								</button>
								<button class="menu-item" onclick={() => { store.insertChart([10, 20, 15, 30]); moreOpen = false; }}>
									<span class="mi-icon">{@html icons.chart}</span>Chart
								</button>
								<button class="menu-item" onclick={() => { store.insertMermaid(MERMAID_SAMPLE); moreOpen = false; }}>
									<span class="mi-icon">{@html icons.mermaid}</span>Mermaid diagram
								</button>
							</div>
						{/if}
					{/if}
				</div>
				{#if SHOW_HINT}
					<p class="hint">
						To pan, hold <kbd>Middle mouse</kbd> or use the hand tool. Double-click a shape to label it.
					</p>
				{/if}
			</div>
			{#if SHOW_IMAGE}
				<input bind:this={fileInput} type="file" accept="image/*" hidden onchange={importImage} />
			{/if}

			<!-- Bottom-left: zoom + history island -->
			{#if SHOW_ZOOM_HISTORY}
			<div class="island corner bottom-left">
				<button class="mini" title="Zoom out" aria-label="Zoom out" onclick={() => store.zoomOut()}>−</button>
				<button class="mini zoom" title="Reset zoom" aria-label="Reset zoom" onclick={() => store.resetZoom()}>{view.zoom}%</button>
				<button class="mini" title="Zoom in" aria-label="Zoom in" onclick={() => store.zoomIn()}>+</button>
				<span class="divider"></span>
				<button class="mini icon" title="Undo" aria-label="Undo" disabled={!view.canUndo} onclick={() => store.undo()}>{@html icons.undo}</button>
				<button class="mini icon" title="Redo" aria-label="Redo" disabled={!view.canRedo} onclick={() => store.redo()}>{@html icons.redo}</button>
			</div>
			{/if}

			<!-- Bottom-right: selection + expand island -->
			<div class="island corner bottom-right">
				<button class="mini icon" title="Delete" aria-label="Delete" disabled={!view.selectedCount} onclick={() => store.deleteSelected()}>{@html icons.trash}</button>
				<button class="mini icon" title={expanded ? 'Collapse' : 'Expand'} aria-label={expanded ? 'Collapse' : 'Expand'} data-testid="ex-expand" onclick={() => (expanded = !expanded)}>{@html expanded ? icons.collapse : icons.expand}</button>
			</div>
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
	.stage {
		position: relative;
		height: 460px;
	}
	.excali.expanded .stage {
		height: 100%;
	}
	canvas {
		display: block;
		width: 100%;
		height: 100%;
		/* The engine paints the scene background from the theme; match it so no
		   app background shows through before the first frame. */
		background: #ffffff;
		touch-action: none;
	}
	.excali[data-theme='dark'] canvas {
		background: #121212;
	}

	/* Floating islands — excalidraw-style rounded chrome. */
	.island {
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 12px;
		box-shadow: var(--sh2, 0 2px 10px rgba(0, 0, 0, 0.12));
		padding: 4px;
	}
	.top-center {
		position: absolute;
		top: 12px;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		max-width: calc(100% - 24px);
		z-index: 5;
	}
	.toolbar {
		display: flex;
		align-items: center;
		gap: 2px;
		flex-wrap: wrap;
		justify-content: center;
		position: relative;
	}
	.tool {
		position: relative;
		width: 34px;
		height: 34px;
		display: grid;
		place-items: center;
		border-radius: 9px;
		color: var(--tx2);
	}
	.tool :global(svg) {
		width: 19px;
		height: 19px;
	}
	.tool:hover {
		background: var(--bg3);
		color: var(--tx);
	}
	.tool.active {
		background: var(--accbg2);
		color: var(--acc-strong);
	}
	.badge {
		position: absolute;
		right: 3px;
		bottom: 1px;
		font-size: 9px;
		line-height: 1;
		color: var(--tx3, var(--tx2));
		pointer-events: none;
	}
	.divider {
		width: 1px;
		align-self: stretch;
		margin: 3px 3px;
		background: var(--line);
	}
	.hint {
		font-size: 11.5px;
		color: var(--tx2);
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 8px;
		padding: 3px 10px;
		text-align: center;
		opacity: 0.92;
	}
	.hint kbd {
		font-size: 10.5px;
		padding: 1px 4px;
		border: 1px solid var(--line);
		border-radius: 4px;
		background: var(--bg2);
	}

	.more-menu {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		display: flex;
		flex-direction: column;
		min-width: 190px;
		padding: 5px;
		z-index: 6;
	}
	.menu-item {
		display: flex;
		align-items: center;
		gap: 9px;
		padding: 7px 9px;
		border-radius: 8px;
		color: var(--tx);
		font-size: 13px;
		text-align: left;
	}
	.menu-item:hover {
		background: var(--bg3);
	}
	.menu-item.active {
		background: var(--accbg2);
		color: var(--acc-strong);
	}
	.mi-icon {
		display: grid;
		place-items: center;
		color: var(--tx2);
	}
	.mi-icon :global(svg) {
		width: 17px;
		height: 17px;
	}
	.menu-item kbd {
		margin-left: auto;
		font-size: 10.5px;
		color: var(--tx2);
		border: 1px solid var(--line);
		border-radius: 4px;
		padding: 1px 5px;
	}
	.menu-head {
		font-size: 10.5px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--tx2);
		padding: 6px 9px 3px;
	}

	.corner {
		position: absolute;
		bottom: 12px;
		display: flex;
		align-items: center;
		gap: 2px;
		z-index: 5;
	}
	.bottom-left {
		left: 12px;
	}
	.bottom-right {
		right: 12px;
	}
	.mini {
		min-width: 30px;
		height: 30px;
		padding: 0 6px;
		display: grid;
		place-items: center;
		border-radius: 8px;
		color: var(--tx2);
		font-size: 13px;
	}
	.mini.zoom {
		min-width: 46px;
		font-variant-numeric: tabular-nums;
	}
	.mini.icon :global(svg) {
		width: 18px;
		height: 18px;
	}
	.mini:hover:not(:disabled) {
		background: var(--bg3);
		color: var(--tx);
	}
	.mini:disabled {
		opacity: 0.35;
		cursor: default;
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
		z-index: 7;
	}
</style>
