<script lang="ts">
	import { page } from '$app/state';
	import { createApiKeys, type ApiKeysVM } from '$lib/viewmodels/api-keys.svelte';
	import { createConnectors, type ConnectorsVM } from '$lib/viewmodels/connectors.svelte';
	import {
		createAgentPersona,
		type AgentPersonaVM
	} from '$lib/viewmodels/agentPersona.svelte';
	import {
		createAgentSkills,
		type AgentSkillsVM
	} from '$lib/viewmodels/agentSkills.svelte';
	import {
		createScheduledAgents,
		type ScheduledAgentsVM
	} from '$lib/viewmodels/scheduledAgents.svelte';
	import { createGoogle, GOOGLE_GROUPS, type GoogleVM } from '$lib/viewmodels/google.svelte';
	import {
		createNotificationPrefs,
		type NotificationPrefsVM
	} from '$lib/viewmodels/notificationPrefs.svelte';
	import { settingsModal } from '$lib/viewmodels/settingsModal.svelte';

	let { workspaceId }: { workspaceId: string } = $props();

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') settingsModal.close();
	}

	let google = $state<GoogleVM | null>(null);
	let googleGroups = $state<string[]>(['gmail_read', 'calendar', 'drive']);

	let persona = $state<AgentPersonaVM | null>(null);
	let newMemory = $state('');

	let skills = $state<AgentSkillsVM | null>(null);
	let skillName = $state('');
	let skillInstruction = $state('');

	let tasks = $state<ScheduledAgentsVM | null>(null);
	let taskName = $state('');
	let taskInstruction = $state('');
	let taskCron = $state('0 9 * * *');

	let connectors = $state<ConnectorsVM | null>(null);
	let name = $state('');
	let endpoint = $state('');
	let credentials = $state('');

	let notificationPrefs = $state<NotificationPrefsVM | null>(null);

	let apiKeys = $state<ApiKeysVM | null>(null);
	let keyName = $state('');
	let copiedSecret = $state(false);

	const NOTIFICATION_TOGGLES: { key: 'email_enabled' | 'push_enabled' | 'mentions_enabled' | 'agent_results_enabled'; label: string; hint: string }[] = [
		{ key: 'email_enabled', label: 'Email notifications', hint: 'Deliver notifications to your email (when configured on this deployment).' },
		{ key: 'push_enabled', label: 'Push notifications', hint: 'Deliver notifications as push (when configured on this deployment).' },
		{ key: 'mentions_enabled', label: 'Mentions & comments', hint: 'When someone @mentions you in a comment.' },
		{ key: 'agent_results_enabled', label: 'Agent task results', hint: 'When a scheduled agent task finishes.' }
	];

	const mcpUrl = $derived(`${page.url.origin.replace(':5173', ':8100')}/mcp/`);

	type TabId = 'connectors' | 'integrations' | 'agent' | 'notifications' | 'keys';
	const TABS: { id: TabId; label: string; icon: string; title: string; sub: string }[] = [
		{
			id: 'connectors',
			label: 'Connectors',
			icon: '🔌',
			title: 'Connectors',
			sub: 'Attach external MCP servers so the agent gains their tools. Credentials are encrypted at rest and never shown again.'
		},
		{
			id: 'integrations',
			label: 'Integrations',
			icon: '🔗',
			title: 'Integrations',
			sub: 'Connect first-party services so the agent can use them — read-only, except creating Calendar events.'
		},
		{
			id: 'agent',
			label: 'Agent',
			icon: '🤖',
			title: 'Agent',
			sub: "Shape this workspace's agent — instructions, durable memory, reusable skills, and scheduled background runs."
		},
		{
			id: 'notifications',
			label: 'Notifications',
			icon: '🔔',
			title: 'Notifications',
			sub: 'Choose how you get notified. In-app notifications are always on; email/push deliver only when configured on this deployment.'
		},
		{
			id: 'keys',
			label: 'API keys',
			icon: '🔑',
			title: 'API keys',
			sub: 'Personal keys let external MCP clients (Claude, ChatGPT) act as you against CyberArche.'
		}
	];
	let activeTab = $state<TabId>('connectors');
	const activeMeta = $derived(TABS.find((tab) => tab.id === activeTab) ?? TABS[0]);

	$effect(() => {
		const vm = createConnectors(workspaceId);
		connectors = vm;
		vm.load();
		const keysVm = createApiKeys();
		apiKeys = keysVm;
		keysVm.load();
		const personaVm = createAgentPersona(workspaceId);
		persona = personaVm;
		personaVm.load();
		const skillsVm = createAgentSkills(workspaceId);
		skills = skillsVm;
		skillsVm.load();
		const tasksVm = createScheduledAgents(workspaceId);
		tasks = tasksVm;
		tasksVm.load();
		const googleVm = createGoogle(workspaceId);
		google = googleVm;
		googleVm.load();
		const notificationsVm = createNotificationPrefs();
		notificationPrefs = notificationsVm;
		notificationsVm.load();
	});

	function toggleGroup(id: string) {
		googleGroups = googleGroups.includes(id)
			? googleGroups.filter((g) => g !== id)
			: [...googleGroups, id];
	}

	async function addTask(event: SubmitEvent) {
		event.preventDefault();
		if (tasks && (await tasks.create(taskName.trim(), taskInstruction.trim(), taskCron.trim()))) {
			taskName = '';
			taskInstruction = '';
		}
	}

	async function addMemory(event: SubmitEvent) {
		event.preventDefault();
		if (persona && (await persona.addMemory(newMemory))) newMemory = '';
	}

	async function addSkill(event: SubmitEvent) {
		event.preventDefault();
		if (skills && (await skills.create(skillName.trim(), skillInstruction.trim()))) {
			skillName = '';
			skillInstruction = '';
		}
	}

	async function createKey(event: SubmitEvent) {
		event.preventDefault();
		if (!apiKeys || !keyName.trim()) return;
		copiedSecret = false;
		await apiKeys.create(keyName.trim());
		keyName = '';
	}

	async function copySecret() {
		if (!apiKeys?.justCreated) return;
		await navigator.clipboard.writeText(apiKeys.justCreated.secret);
		copiedSecret = true;
	}

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

<svelte:window onkeydown={onKeydown} />

<!-- Backdrop: click to dismiss; blurs the app behind. -->
<div
	class="backdrop"
	role="button"
	tabindex="-1"
	aria-label="Close settings"
	data-testid="settings-backdrop"
	onclick={() => settingsModal.close()}
	onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && settingsModal.close()}
></div>

<div class="dialog" role="dialog" aria-modal="true" aria-label="Settings" data-testid="settings-modal">
	<button
		class="close"
		aria-label="Close settings"
		data-testid="settings-close"
		onclick={() => settingsModal.close()}>×</button
	>

	<nav class="rail" aria-label="Settings sections">
		<p class="rail-label">Workspace</p>
		{#each TABS as tab (tab.id)}
			<button
				class="rail-item"
				class:active={activeTab === tab.id}
				aria-current={activeTab === tab.id}
				data-testid="settings-tab-{tab.id}"
				onclick={() => (activeTab = tab.id)}
			>
				<span class="rail-icon" aria-hidden="true">{tab.icon}</span>
				{tab.label}
			</button>
		{/each}
	</nav>

	<div class="pane">
	<div class="pane-scroll">
		<header class="head">
			<h1>{activeMeta.title}</h1>
			<p class="sub">{activeMeta.sub}</p>
		</header>

	{#if activeTab === 'keys'}
	{#if apiKeys}
		<section class="card">
			<h2>API keys — connect Claude / ChatGPT to CyberArche</h2>
			<p class="hint">
				Personal keys let external MCP clients act as you. Point the client at
				<code>{mcpUrl}</code> with header
				<code>Authorization: Bearer &lt;key&gt;</code>. Keys are hashed at rest and shown
				only once.
			</p>
			<form class="add" onsubmit={createKey}>
				<input
					class="input grow"
					placeholder="Key name (e.g. Claude Desktop)"
					bind:value={keyName}
					data-testid="apikey-name"
				/>
				<button class="btn btn-primary" type="submit" data-testid="apikey-create"
					>Create key</button
				>
			</form>

			{#if apiKeys.justCreated}
				<div class="secret-once" data-testid="apikey-secret-box">
					<p class="secret-title">
						Copy this key now — it will not be shown again.
					</p>
					<div class="secret-row">
						<code class="secret" data-testid="apikey-secret">{apiKeys.justCreated.secret}</code>
						<button class="btn btn-secondary" data-testid="apikey-copy" onclick={copySecret}>
							{copiedSecret ? 'Copied ✓' : 'Copy'}
						</button>
						<button class="mini" data-testid="apikey-dismiss" onclick={() => apiKeys!.dismissSecret()}
							>Done</button
						>
					</div>
				</div>
			{/if}

			{#each apiKeys.items as key (key.id)}
				<div class="key-row" class:revoked={key.revoked} data-testid="apikey-row">
					<div class="info">
						<strong>{key.name}</strong>
						<code class="key-prefix">{key.prefix}</code>
						<span class="chip">{key.revoked ? 'revoked' : 'active'}</span>
						{#if key.last_used_at}
							<span class="muted">last used {new Date(key.last_used_at).toLocaleString()}</span>
						{:else if !key.revoked}
							<span class="muted">never used</span>
						{/if}
					</div>
					{#if !key.revoked}
						<button
							class="remove"
							data-testid="apikey-revoke"
							onclick={() => apiKeys!.revoke(key.id)}>Revoke</button
						>
					{/if}
				</div>
			{:else}
				<p class="none">No API keys yet.</p>
			{/each}
			{#if apiKeys.error}
				<p class="error" role="alert">{apiKeys.error}</p>
			{/if}
		</section>
	{/if}
	{/if}

	{#if activeTab === 'agent'}
	{#if persona}
		<section class="card">
			<h2>Agent instructions &amp; memory</h2>
			<p class="hint">
				Shape the agent for this workspace. Instructions are added to every agent
				run; memories are durable facts it recalls across conversations.
			</p>

			<label class="field">
				<span>Workspace instructions (shared — everyone here)</span>
				<textarea
					rows="4"
					maxlength="4000"
					placeholder="e.g. Always answer in Portuguese and cite block ids."
					bind:value={persona.workspaceText}
				></textarea>
			</label>
			<div class="row">
				<span class="count">{persona.workspaceText.length}/4000</span>
				<button
					class="save"
					disabled={persona.busy}
					onclick={() => persona?.saveInstructions('workspace')}>Save</button
				>
			</div>

			<label class="field">
				<span>Your personal instructions (only you)</span>
				<textarea
					rows="3"
					maxlength="2000"
					placeholder="e.g. Keep answers terse; I prefer TypeScript examples."
					bind:value={persona.personalText}
				></textarea>
			</label>
			<div class="row">
				<span class="count">{persona.personalText.length}/2000</span>
				<button
					class="save"
					disabled={persona.busy}
					onclick={() => persona?.saveInstructions('personal')}>Save</button
				>
			</div>

			<h3 class="mem-title">Remembered facts</h3>
			<form class="add" onsubmit={addMemory}>
				<input
					placeholder="Add a durable fact (no secrets)…"
					bind:value={newMemory}
				/>
				<button type="submit" disabled={persona.busy || !newMemory.trim()}>Add</button>
			</form>
			{#each persona.memories as memory (memory.id)}
				<div class="mem">
					<span class="mem-text">{memory.text}</span>
					<button
						class="mem-remove"
						title="Forget"
						aria-label="Forget"
						onclick={() => persona?.removeMemory(memory.id)}>×</button
					>
				</div>
			{:else}
				<p class="none">No memories yet.</p>
			{/each}
			{#if persona.error}
				<p class="error" role="alert">{persona.error}</p>
			{/if}
		</section>
	{/if}

	{#if skills}
		<section class="card">
			<h2>Agent skills</h2>
			<p class="hint">
				Save reusable prompts. Use <code>{'{variable}'}</code> placeholders (e.g.
				“Summarize for <code>{'{audience}'}</code>”) — you’ll be asked to fill them in
				when you run the skill from the agent panel.
			</p>
			<form class="skill-add" onsubmit={addSkill}>
				<input placeholder="Skill name (e.g. Weekly status)" bind:value={skillName} />
				<textarea
					rows="2"
					placeholder="Instruction, with {'{variables}'} — e.g. Summarize this doc for {'{audience}'}."
					bind:value={skillInstruction}
				></textarea>
				<button
					type="submit"
					disabled={skills.busy || !skillName.trim() || !skillInstruction.trim()}
					>Save skill</button
				>
			</form>
			{#each skills.skills as skill (skill.id)}
				<div class="mem">
					<span class="mem-text"><strong>{skill.name}</strong> — {skill.instruction}</span>
					<button
						class="mem-remove"
						title="Delete skill"
						aria-label="Delete skill"
						onclick={() => skills?.remove(skill.id)}>×</button
					>
				</div>
			{:else}
				<p class="none">No skills yet.</p>
			{/each}
			{#if skills.error}
				<p class="error" role="alert">{skills.error}</p>
			{/if}
		</section>
	{/if}

	{#if tasks}
		<section class="card">
			<h2>Scheduled agents</h2>
			<p class="hint">
				Autonomous tasks the agent runs on a schedule (5-field cron), in the
				background, with no live user. Results are written to a document and you
				get a notification. Destructive edits (deleting blocks) are disabled in
				background runs.
			</p>
			<form class="skill-add" onsubmit={addTask}>
				<input placeholder="Task name (e.g. Daily standup digest)" bind:value={taskName} />
				<textarea
					rows="2"
					placeholder="Instruction — e.g. Summarize yesterday’s changes as a status update."
					bind:value={taskInstruction}
				></textarea>
				<label class="cron-row">
					<span>Cron</span>
					<input class="cron" placeholder="0 9 * * *" bind:value={taskCron} />
					<span class="cron-hint">min hour dom mon dow — e.g. “0 9 * * 1-5” = 9am weekdays</span>
				</label>
				<button
					type="submit"
					disabled={tasks.busy || !taskName.trim() || !taskInstruction.trim() || !taskCron.trim()}
					>Create task</button
				>
			</form>
			{#each tasks.tasks as task (task.id)}
				<div class="task">
					<label class="task-toggle" title={task.enabled ? 'Enabled' : 'Disabled'}>
						<input
							type="checkbox"
							checked={task.enabled}
							onchange={() => tasks?.toggle(task)}
						/>
					</label>
					<div class="task-body">
						<strong>{task.name}</strong>
						<span class="task-meta"
							>{task.schedule_cron} · next {task.next_run_at
								? new Date(task.next_run_at).toLocaleString()
								: '—'}</span
						>
						<span class="task-instr">{task.instruction}</span>
					</div>
					<button
						class="mem-remove"
						title="Delete task"
						aria-label="Delete task"
						onclick={() => tasks?.remove(task.id)}>×</button
					>
				</div>
			{:else}
				<p class="none">No scheduled tasks yet.</p>
			{/each}
			{#if tasks.error}
				<p class="error" role="alert">{tasks.error}</p>
			{/if}
		</section>
	{/if}
	{/if}

	{#if activeTab === 'notifications'}
	{#if notificationPrefs}
		<section class="card" data-testid="settings-tab-notifications">
			<h2>Delivery preferences</h2>
			<p class="hint">
				In-app notifications (the bell) are always on. These toggles control
				extra delivery and which kinds you receive.
			</p>
			{#each NOTIFICATION_TOGGLES as row (row.key)}
				<div class="notif-row">
					<div class="notif-info">
						<strong>{row.label}</strong>
						<span class="notif-hint">{row.hint}</span>
					</div>
					<label class="toggle" title={row.label}>
						<input
							type="checkbox"
							checked={notificationPrefs.prefs[row.key]}
							disabled={notificationPrefs.busy}
							data-testid="notif-toggle-{row.key}"
							onchange={() => notificationPrefs?.toggle(row.key)}
						/>
					</label>
				</div>
			{/each}
			{#if notificationPrefs.error}
				<p class="error" role="alert">{notificationPrefs.error}</p>
			{/if}
		</section>
	{/if}
	{/if}

	{#if activeTab === 'integrations'}
		<section class="card">
			<h2>Google Workspace</h2>
			{#if google && google.status?.configured}
				<p class="hint">
					Connect your Google account to give the agent read-only Gmail,
					Calendar, Drive/Docs, Sheets, and Slides — plus the ability to create
					Calendar events. The connection is personal to you.
				</p>
				{#if google.status.connected}
					<div class="google-connected">
						<span>Connected as <strong>{google.status.email}</strong></span>
						<button class="save" onclick={() => google?.disconnect()}>Disconnect</button>
					</div>
					<p class="task-meta">Granted: {google.status.scopes.length} scope(s)</p>
				{:else}
					<div class="google-groups">
						{#each GOOGLE_GROUPS as grp (grp.id)}
							<label class="google-group">
								<input
									type="checkbox"
									checked={googleGroups.includes(grp.id)}
									onchange={() => toggleGroup(grp.id)}
								/>
								{grp.label}
							</label>
						{/each}
					</div>
					<button
						class="save"
						disabled={googleGroups.length === 0}
						onclick={() => google?.connect(googleGroups)}>Connect Google</button
					>
				{/if}
				{#if google.error}
					<p class="error" role="alert">{google.error}</p>
				{/if}
			{:else}
				<p class="none" data-testid="google-not-configured">
					Google Workspace isn't enabled on this deployment. An administrator
					needs to configure the Google OAuth client
					(<code>CYBERARCHE_GOOGLE_CLIENT_ID</code> / <code>_SECRET</code> /
					<code>_REDIRECT_URI</code>) before it can be connected.
				</p>
			{/if}
		</section>
	{/if}

	{#if activeTab === 'connectors'}
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
	{/if}
		</div>

		<footer class="foot">
			<button class="btn btn-primary" data-testid="settings-done" onclick={() => settingsModal.close()}
				>Done</button
			>
		</footer>
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 900;
		background: rgba(15, 15, 20, 0.35);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		animation: fade 0.14s ease;
	}
	.dialog {
		position: fixed;
		z-index: 901;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: min(960px, 92vw);
		height: min(660px, 88vh);
		display: grid;
		grid-template-columns: 232px 1fr;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: 14px;
		box-shadow:
			0 24px 64px rgba(0, 0, 0, 0.28),
			0 2px 8px rgba(0, 0, 0, 0.12);
		overflow: hidden;
		animation: pop 0.16s cubic-bezier(0.2, 0.8, 0.3, 1);
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: translate(-50%, -48%) scale(0.98);
		}
	}
	.close {
		position: absolute;
		top: 14px;
		right: 16px;
		z-index: 2;
		width: 28px;
		height: 28px;
		border: none;
		background: none;
		font-size: 22px;
		line-height: 1;
		color: var(--tx3);
		cursor: pointer;
		border-radius: var(--r-control);
	}
	.close:hover {
		background: var(--bg2, var(--bg0));
		color: var(--tx);
	}
	/* ---- left rail ---- */
	.rail {
		background: var(--bg0);
		border-right: 1px solid var(--line);
		padding: 20px 12px;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.rail-label {
		margin: 0 0 8px 10px;
		font-size: 12px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--tx3);
	}
	.rail-item {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		padding: 8px 10px;
		border: none;
		background: none;
		font: inherit;
		font-size: 14px;
		color: var(--tx);
		text-align: left;
		border-radius: var(--r-control);
		cursor: pointer;
	}
	.rail-item:hover {
		background: var(--bg1);
	}
	.rail-item.active {
		background: var(--bg2, var(--line));
		font-weight: 500;
	}
	.rail-icon {
		font-size: 15px;
		width: 18px;
		text-align: center;
	}
	/* ---- content pane ---- */
	.pane {
		min-width: 0;
		min-height: 0; /* let the grid item be capped at the dialog height... */
		display: flex;
		flex-direction: column;
	}
	.pane-scroll {
		flex: 1;
		min-height: 0; /* ...and the flex child shrink, so overflow-y actually scrolls */
		overflow-y: auto;
		padding: 34px 40px 24px;
	}
	.foot {
		display: flex;
		justify-content: flex-end;
		gap: 10px;
		padding: 12px 24px;
		border-top: 1px solid var(--line);
		background: var(--bg1);
	}
	.hint {
		color: var(--tx2);
		margin: 0 0 12px;
		font-size: 13px;
	}
	.field {
		display: block;
		margin-top: 12px;
	}
	.field span {
		display: block;
		font-size: 13px;
		color: var(--tx2);
		margin-bottom: 4px;
	}
	.field textarea {
		width: 100%;
		resize: vertical;
		padding: 8px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg1);
		color: var(--tx);
		font: inherit;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 6px;
	}
	.count {
		font-size: 12px;
		color: var(--tx3);
		margin-left: auto;
	}
	.save {
		padding: 5px 14px;
		border-radius: var(--r-control);
		background: var(--acc);
		color: #fff;
	}
	.save:disabled {
		opacity: 0.5;
	}
	.mem-title {
		margin: 18px 0 8px;
		font-size: 14px;
	}
	.mem {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		margin-top: 6px;
	}
	.mem-text {
		flex: 1;
		font-size: 13px;
	}
	.mem-remove {
		color: var(--tx3);
		font-size: 16px;
		line-height: 1;
	}
	.mem-remove:hover {
		color: var(--rose);
	}
	.skill-add {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 12px;
	}
	.skill-add input,
	.skill-add textarea {
		width: 100%;
		padding: 8px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		background: var(--bg1);
		color: var(--tx);
		font: inherit;
		resize: vertical;
	}
	.skill-add button {
		align-self: flex-start;
		padding: 5px 14px;
		border-radius: var(--r-control);
		background: var(--acc);
		color: #fff;
	}
	.skill-add button:disabled {
		opacity: 0.5;
	}
	.cron-row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.cron-row span:first-child {
		font-size: 13px;
		color: var(--tx2);
	}
	.cron {
		width: 140px;
		font-family: var(--font-mono, ui-monospace, monospace);
	}
	.cron-hint {
		font-size: 11px;
		color: var(--tx3);
	}
	.task {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 8px 10px;
		border: 1px solid var(--line);
		border-radius: var(--r-control);
		margin-top: 6px;
	}
	.task-toggle {
		padding-top: 2px;
	}
	.task-body {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.task-meta {
		font-size: 11px;
		color: var(--tx3);
	}
	.task-instr {
		font-size: 12px;
		color: var(--tx2);
	}
	.notif-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 10px 0;
		border-top: 1px solid var(--line);
	}
	.notif-row:first-of-type {
		border-top: none;
	}
	.notif-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.notif-hint {
		font-size: 12px;
		color: var(--tx3);
	}
	.google-groups {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin-bottom: 12px;
	}
	.google-group {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
	}
	.google-connected {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 6px;
	}
	.head {
		margin-bottom: 4px;
	}
	.head h1 {
		margin: 0;
		font-size: 22px;
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
		/* A connector can advertise dozens of tools — cap the chip list and let
		 * it scroll on its own instead of making the whole card very long. */
		max-height: 168px;
		overflow-y: auto;
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
	.secret-once {
		margin-top: 12px;
		background: var(--accbg);
		border: 1px solid var(--accbg2);
		border-radius: var(--r-block);
		padding: 10px 12px;
	}
	.secret-title {
		margin: 0 0 6px;
		font-weight: 600;
		color: var(--acc-strong);
	}
	.secret-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.secret {
		flex: 1;
		font-size: 11px;
		word-break: break-all;
	}
	.key-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		padding: 9px 0;
		border-top: 1px solid var(--line);
	}
	.key-row.revoked {
		opacity: 0.55;
	}
	.key-row .info {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.key-prefix {
		font-size: 11px;
		color: var(--tx2);
	}
	.muted {
		color: var(--tx3);
		font-size: 11px;
	}
	.mini {
		font-size: 11px;
		color: var(--acc-strong);
	}
</style>
