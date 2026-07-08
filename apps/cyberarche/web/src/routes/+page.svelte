<script lang="ts">
	import { goto } from '$app/navigation';
	import { session } from '$lib/viewmodels/session.svelte';
	import { workspaces } from '$lib/viewmodels/workspaces.svelte';

	$effect(() => {
		(async () => {
			if (!session.isAuthenticated) {
				await goto('/signin');
				return;
			}
			await workspaces.load();
			const first = workspaces.items[0];
			await goto(first ? `/w/${first.id}` : '/w/new');
		})();
	});
</script>

<div class="loading">CyberArche</div>

<style>
	.loading {
		display: grid;
		place-items: center;
		height: 100vh;
		color: var(--tx3);
		font-weight: 600;
		letter-spacing: 0.08em;
	}
</style>
