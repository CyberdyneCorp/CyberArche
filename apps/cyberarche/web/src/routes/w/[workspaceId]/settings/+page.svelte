<script lang="ts">
	import { page } from '$app/state';
	import { createConnectors, type ConnectorsVM } from '$lib/viewmodels/connectors.svelte';

	const workspaceId = $derived(page.params.workspaceId!);

	let connectors = $state<ConnectorsVM | null>(null);
	let name = $state('');
	let endpoint = $state('');
	let credentials = $state('');

	$effect(() => {
		const vm = createConnectors(workspaceId);
		connectors = vm;
		vm.load();
	});

	async function register(event: SubmitEvent) {
		event.preventDefault();
		if (!connectors || !name.trim() || !endpoint.trim()) return;
		if (await connectors.register(name.trim(), endpoint.trim(), credentials)) {
			name = '';
			endpoint = '';
			credentials = '';
		}
	}
</script>

<div class="settings">
	<header class="head">
		<h1>Settings &amp; connectors</h1>
		<p class="sub">
			Attach external MCP servers to give the agent extra tools. Tools are namespaced by
			connector; credentials are encrypted at rest and never shown again.
		</p>
	</header>

	{#if connectors}
		<section class="card">
			<h2>Attach an MCP server</h2>
			<form class="add" onsubmit={register}>
				<input
					class="input"
					placeholder="Name (e.g. Ticketing)"
					bind:value={name}
					data-testid="connector-name"
				/>
				<input
					class="input grow"
					placeholder="Endpoint, e.g. https://tools.example/mcp/"
					bind:value={endpoint}
					data-testid="connector-endpoint"
				/>
				<input
					class="input"
					type="password"
					placeholder="Bearer credential (optional)"
					bind:value={credentials}
					autocomplete="off"
					data-testid="connector-credentials"
				/>
				<button class="btn btn-primary" type="submit" disabled={connectors.busy} data-testid="connector-add">
					{connectors.busy ? 'Checking…' : 'Attach'}
				</button>
			</form>
			<p class="hint">
				Registration performs a live MCP handshake — unreachable servers are rejected.
			</p>
			{#if connectors.error}
				<p class="error" role="alert" data-testid="connector-error">{connectors.error}</p>
			{/if}
		</section>

		<section class="card">
			<h2>Connected servers</h2>
			{#each connectors.items as connector (connector.id)}
				<div class="connector" data-testid="connector-row">
					<div class="info">
						<div class="title-line">
							<strong>{connector.name}</strong>
							<span class="chip">{connector.slug}</span>
							<span class="chip" class:chip-accent={connector.enabled}>
								{connector.enabled ? 'enabled' : 'disabled'}
							</span>
						</div>
						<code class="endpoint">{connector.endpoint}</code>
						{#if connectors.toolsOf(connector).length > 0}
							<div class="tools">
								{#each connectors.toolsOf(connector) as tool (tool.name)}
									<span class="chip chip-ai" title={tool.description} data-testid="connector-tool"
										>{tool.name}</span
									>
								{/each}
							</div>
						{:else if connector.enabled}
							<p class="none">No tools advertised</p>
						{/if}
					</div>
					<div class="actions">
						<label class="toggle">
							<input
								type="checkbox"
								checked={connector.enabled}
								data-testid="connector-toggle"
								onchange={(event) =>
									connectors!.setEnabled(
										connector.id,
										(event.target as HTMLInputElement).checked
									)}
							/>
							<span>Enabled</span>
						</label>
						<button
							class="remove"
							data-testid="connector-remove"
							onclick={() => connectors!.remove(connector.id)}>Remove</button
						>
					</div>
				</div>
			{:else}
				<p class="none" data-testid="no-connectors">No external MCP servers attached yet.</p>
			{/each}
		</section>
	{/if}
</div>

<style>
	.settings {
		width: min(720px, 92%);
		margin: 0 auto;
		padding: 40px 0 120px;
		overflow-y: auto;
		height: 100%;
	}
	.head h1 {
		margin: 0;
		font-size: 24px;
	}
	.sub {
		color: var(--tx2);
		margin: 6px 0 0;
	}
	.card {
		margin-top: 22px;
		background: var(--bg0);
		border: 1px solid var(--line);
		border-radius: var(--r-block);
		padding: 16px 18px;
	}
	.card h2 {
		margin: 0 0 12px;
		font-size: 13px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--tx3);
	}
	.add {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.grow {
		flex: 1;
		min-width: 220px;
	}
	.hint {
		color: var(--tx3);
		font-size: 11.5px;
		margin: 8px 0 0;
	}
	.error {
		color: var(--rose);
		margin: 8px 0 0;
	}
	.connector {
		display: flex;
		justify-content: space-between;
		gap: 14px;
		padding: 12px 0;
		border-top: 1px solid var(--line);
	}
	.connector:first-of-type {
		border-top: none;
	}
	.title-line {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.endpoint {
		display: block;
		margin-top: 4px;
		font-size: 11px;
		color: var(--tx2);
	}
	.tools {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 8px;
	}
	.none {
		color: var(--tx3);
	}
	.actions {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 6px;
	}
	.toggle {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 12px;
		color: var(--tx2);
	}
	.remove {
		font-size: 11.5px;
		color: var(--rose);
	}
</style>
