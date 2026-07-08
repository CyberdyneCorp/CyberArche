<script lang="ts">
	import { goto } from '$app/navigation';
	import { session } from '$lib/viewmodels/session.svelte';

	let email = $state('');
	let password = $state('');

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (await session.login(email, password)) {
			await goto('/');
		}
	}
</script>

<main class="wrap">
	<form class="card" onsubmit={submit}>
		<div class="brand">
			<div class="mark">CA</div>
			<h1>CyberArche</h1>
			<p class="sub">Documents, whiteboards, and an agent that works where you do.</p>
		</div>

		<label>
			<span>Email</span>
			<input
				class="input"
				type="email"
				bind:value={email}
				autocomplete="email"
				placeholder="you@company.com"
				required
			/>
		</label>
		<label>
			<span>Password</span>
			<input
				class="input"
				type="password"
				bind:value={password}
				autocomplete="current-password"
				required
			/>
		</label>

		{#if session.error}
			<p class="error" role="alert">{session.error}</p>
		{/if}

		<button class="btn btn-primary submit" type="submit" disabled={session.busy}>
			{session.busy ? 'Signing in…' : 'Sign in'}
		</button>
		<p class="hint">Accounts are managed by Cyberdyne SSO.</p>
	</form>
</main>

<style>
	.wrap {
		display: grid;
		place-items: center;
		min-height: 100vh;
		background: var(--bg0);
	}
	.card {
		display: flex;
		flex-direction: column;
		gap: 14px;
		width: 340px;
		padding: 32px 28px;
		background: var(--bg1);
		border: 1px solid var(--line);
		border-radius: var(--r-dialog);
		box-shadow: var(--sh2);
	}
	.brand {
		text-align: center;
		margin-bottom: 8px;
	}
	.mark {
		display: inline-grid;
		place-items: center;
		width: 40px;
		height: 40px;
		border-radius: 10px;
		background: var(--tx);
		color: var(--bg1);
		font-weight: 700;
	}
	h1 {
		margin: 10px 0 2px;
		font-size: 20px;
	}
	.sub {
		margin: 0;
		color: var(--tx2);
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 5px;
		font-weight: 500;
	}
	.error {
		margin: 0;
		color: var(--rose);
	}
	.submit {
		justify-content: center;
		padding: 9px;
		font-size: 13.5px;
	}
	.hint {
		margin: 0;
		text-align: center;
		color: var(--tx3);
		font-size: 11px;
	}
</style>
