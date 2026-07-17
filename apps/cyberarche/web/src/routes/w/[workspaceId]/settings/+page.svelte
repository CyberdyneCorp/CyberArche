<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { settingsModal } from '$lib/viewmodels/settingsModal.svelte';

	// Settings is a modal rendered by the workspace layout. A direct visit to
	// /settings (deep link / bookmark) opens the modal over the workspace root.
	$effect(() => {
		settingsModal.open();
		void goto(`/w/${page.params.workspaceId}`, { replaceState: true });
	});
</script>
