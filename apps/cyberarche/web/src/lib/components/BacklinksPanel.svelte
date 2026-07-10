<script lang="ts">
	import { backlinks, type Document } from '$lib/api/documents';

	let { documentId }: { documentId: string } = $props();

	let refs = $state<Document[]>([]);

	$effect(() => {
		const id = documentId;
		let cancelled = false;
		refs = [];
		backlinks(id)
			.then((docs) => {
				if (!cancelled) refs = docs;
			})
			.catch(() => {
				if (!cancelled) refs = [];
			});
		return () => {
			cancelled = true;
		};
	});
</script>

{#if refs.length > 0}
	<section class="backlinks" data-testid="backlinks">
		<h2>Linked references</h2>
		<ul>
			{#each refs as doc (doc.id)}
				<li>
					<a href={`/w/${doc.workspace_id}/d/${doc.id}`} data-testid="backlink">
						<span class="icon">▤</span>
						<span class="title">{doc.title || 'Untitled'}</span>
					</a>
				</li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	.backlinks {
		margin-top: 40px;
		padding-top: 16px;
		border-top: 1px solid var(--line);
	}
	.backlinks h2 {
		margin: 0 0 8px;
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--tx3);
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	a {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		border-radius: var(--r-control);
		color: var(--tx);
		text-decoration: none;
		font-size: 14px;
	}
	a:hover {
		background: var(--bg2);
	}
	.icon {
		color: var(--tx3);
		font-size: 11px;
	}
</style>
