<script lang="ts">
	/** The violet right rail (design: everything the AI touches is violet). */
	import type { AgentPanelVM } from '$lib/viewmodels/agent.svelte';
	import type { ConnectorsVM } from '$lib/viewmodels/connectors.svelte';

	let {
		agent,
		connectors = null,
		workspaceId = '',
		onclose
	}: {
		agent: AgentPanelVM;
		connectors?: ConnectorsVM | null;
		workspaceId?: string;
		onclose: () => void;
	} = $props();

	let toolsOpen = $state(false);
	const enabledConnectors = $derived(
		(connectors?.items ?? []).filter((c) => c.enabled).length
	);

	let prompt = $state('');
	let showRuns = $state(false);
	let dragOver = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		const text = prompt.trim();
		if (!text || agent.busy) return;
		prompt = '';
		await agent.ask(text);
	}

	function onDrop(event: DragEvent) {
		event.preventDefault();
		dragOver = false;
		const file = event.dataTransfer?.files?.[0];
		if (file) agent.ingest(file);
	}

	async function pickFile(event: Event) {
		const file = (event.target as HTMLInputElement).files?.[0];
		if (file) await agent.ingest(file);
	}
</script>

<aside
	class="panel"
	class:drag-over={dragOver}
	data-testid="agent-panel"
	ondragover={(event) => {
		event.preventDefault();
		dragOver = true;
	}}
	ondragleave={() => (dragOver = false)}
	ondrop={onDrop}
>
	<header class="head">
		<div class="who">
			<span class="spark">✦</span>
			<strong>Agent</strong>
			<span class="grounded">● Grounded · workspace index</span>
		</div>
		<div class="head-actions">
			<button
				class="ghost"
				title="Run history"
				data-testid="agent-runs-toggle"
				onclick={async () => {
					showRuns = !showRuns;
					if (showRuns) await agent.loadRuns();
				}}>↻</button
			>
			<button class="ghost" title="Close" aria-label="Close agent panel" onclick={onclose}
				>✕</button
			>
		</div>
	</header>

	<div class="quick">
		<button class="chip-btn" data-testid="agent-summarize" onclick={() => agent.summarize()}
			>Summarize</button
		>
		<button
			class="chip-btn"
			onclick={() => agent.draft('a section continuing this document')}
			>Draft section</button
		>
		<label class="chip-btn ingest">
			Ingest a file
			<input type="file" accept=".pdf,.csv,.xlsx,.md,.txt" onchange={pickFile} hidden />
		</label>
	</div>

	{#if showRuns}
		<section class="runs" data-testid="agent-runs">
			<h3>Recent runs</h3>
			{#each agent.runs as run (run.id)}
				<div class="run">
					<span class="run-prompt">{run.prompt}</span>
					<span class="run-meta"
						>{run.model}{run.tools_used.length ? ` · ${run.tools_used.join(', ')}` : ''}</span
					>
				</div>
			{:else}
				<p class="empty">No runs yet</p>
			{/each}
		</section>
	{/if}

	<div class="thread" data-testid="agent-thread">
		{#each agent.messages as message, index (index)}
			{#if message.role === 'user'}
				<div class="bubble user">{message.text}</div>
			{:else}
				<div class="bubble agent">
					<span class="tag">✦ Agent</span>
					<p class="answer">{message.text}</p>
					{#if message.blocks?.length}
						<div class="actions">
							<button
								class="btn btn-ai"
								data-testid="insert-as-block"
								disabled={message.inserted}
								onclick={() => agent.insert(message)}
							>
								{message.inserted ? 'Inserted ✓' : 'Insert as block'}
							</button>
						</div>
					{/if}
				</div>
			{/if}
		{/each}
		{#if agent.busy}
			<div class="bubble agent thinking" data-testid="agent-thinking">
				<span class="tag">✦ Agent</span>
				<p class="answer">Thinking…</p>
			</div>
		{/if}
		{#if agent.error}
			<p class="error" role="alert">{agent.error}</p>
		{/if}
		{#if agent.ingesting === 'uploading'}
			<p class="ingest-state">Uploading → processing…</p>
		{/if}
	</div>

	{#if connectors}
		<section class="tools-bar">
			<button
				class="tools-summary"
				data-testid="agent-tools-toggle"
				onclick={() => (toolsOpen = !toolsOpen)}
			>
				<span>{toolsOpen ? '▾' : '▸'} Tools</span>
				<span class="tools-meta"
					>{connectors.tools.length} external · {enabledConnectors} MCP</span
				>
			</button>
			{#if toolsOpen}
				<div class="tools-list" data-testid="agent-tools">
					{#each connectors.items as connector (connector.id)}
						<label class="tool-row">
							<input
								type="checkbox"
								checked={connector.enabled}
								onchange={(event) =>
									connectors!.setEnabled(
										connector.id,
										(event.target as HTMLInputElement).checked
									)}
							/>
							<span class="tool-name">{connector.name}</span>
							<span class="tool-count"
								>{connectors.toolsOf(connector).length} tool(s)</span
							>
						</label>
					{:else}
						<p class="tools-empty">No external MCP servers attached.</p>
					{/each}
					<a class="manage" href={`/w/${workspaceId}/settings`}>Manage connectors →</a>
				</div>
			{/if}
		</section>
	{/if}

	<form class="composer" onsubmit={submit}>
		<input
			class="input ask"
			placeholder="Ask, or describe an edit…"
			bind:value={prompt}
			data-testid="agent-prompt"
			disabled={agent.busy}
		/>
		<button class="send" type="submit" disabled={agent.busy} aria-label="Send">↑</button>
	</form>
	<p class="dropzone-hint">Drop PDF / CSV / XLSX here to ingest into the doc</p>
</aside>

<style>
	.panel {
		display: flex;
		flex-direction: column;
		width: 320px;
		min-width: 320px;
		height: 100vh;
		background: var(--bg0);
		border-left: 1px solid var(--line);
	}
	.panel.drag-over {
		outline: 2px dashed var(--ai);
		outline-offset: -6px;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 12px 14px 8px;
	}
	.who {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.spark {
		color: var(--ai);
	}
	.grounded {
		color: var(--tx3);
		font-size: 10.5px;
	}
	.ghost {
		color: var(--tx3);
		padding: 3px 6px;
		border-radius: var(--r-control);
	}
	.ghost:hover {
		background: var(--bg2);
		color: var(--tx);
	}
	.quick {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		padding: 0 14px 10px;
	}
	.chip-btn {
		padding: 4px 11px;
		border: 1px solid var(--line2);
		border-radius: var(--r-pill);
		background: var(--bg1);
		font-size: 12px;
		cursor: pointer;
	}
	.chip-btn:hover {
		background: var(--aibg);
		border-color: var(--ai);
	}
	.runs {
		border-top: 1px solid var(--line);
		padding: 8px 14px;
		max-height: 180px;
		overflow-y: auto;
	}
	.runs h3 {
		margin: 0 0 6px;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--tx3);
	}
	.run {
		display: flex;
		flex-direction: column;
		padding: 4px 0;
		border-bottom: 1px solid var(--line);
	}
	.run-prompt {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.run-meta {
		color: var(--tx3);
		font-size: 10.5px;
		font-family: var(--font-mono);
	}
	.thread {
		flex: 1;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 10px 14px;
	}
	.bubble.user {
		align-self: flex-end;
		background: var(--bg2);
		border-radius: var(--r-block);
		padding: 9px 12px;
		max-width: 90%;
	}
	.bubble.agent {
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		padding: 10px 12px;
		box-shadow: var(--sh1);
	}
	.tag {
		color: var(--ai);
		font-size: 10.5px;
		font-weight: 600;
	}
	.answer {
		margin: 6px 0 0;
		white-space: pre-wrap;
		font-size: 13px;
		line-height: 1.55;
	}
	.thinking .answer {
		color: var(--tx3);
	}
	.actions {
		margin-top: 8px;
		display: flex;
		gap: 6px;
	}
	.error {
		color: var(--rose);
	}
	.ingest-state {
		color: var(--ai);
		font-size: 12px;
	}
	.empty {
		color: var(--tx3);
	}
	.tools-bar {
		border-top: 1px solid var(--line);
		padding: 6px 14px;
	}
	.tools-summary {
		display: flex;
		justify-content: space-between;
		width: 100%;
		font-size: 12px;
		color: var(--tx2);
		padding: 3px 0;
	}
	.tools-meta {
		font-family: var(--font-mono);
		font-size: 10.5px;
		color: var(--tx3);
	}
	.tools-list {
		padding: 4px 0 2px;
	}
	.tool-row {
		display: flex;
		align-items: center;
		gap: 7px;
		padding: 3px 0;
		font-size: 12px;
	}
	.tool-name {
		flex: 1;
	}
	.tool-count {
		color: var(--tx3);
		font-size: 10.5px;
	}
	.tools-empty {
		color: var(--tx3);
		font-size: 12px;
		margin: 4px 0;
	}
	.manage {
		display: block;
		margin-top: 4px;
		font-size: 11.5px;
		color: var(--ai);
		text-decoration: none;
	}
	.composer {
		display: flex;
		gap: 6px;
		padding: 8px 14px 4px;
		border-top: 1px solid var(--line);
	}
	.ask {
		flex: 1;
	}
	.send {
		width: 32px;
		border-radius: 50%;
		background: var(--ai);
		color: #fff;
	}
	.send[disabled] {
		opacity: 0.5;
	}
	.dropzone-hint {
		margin: 0;
		padding: 4px 14px 10px;
		color: var(--tx3);
		font-size: 10.5px;
		text-align: center;
	}
</style>
