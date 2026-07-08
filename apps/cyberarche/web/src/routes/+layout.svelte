<script lang="ts">
	import '../app.css';
	import { session } from '$lib/viewmodels/session.svelte';

	let { children } = $props();

	session.restore();
</script>

{@render children()}
