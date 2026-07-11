/** Live document titles (fix-title-sync): a reactive override of a document's
 * displayed name, so renaming a document on its page updates every list that
 * shows it (the sidebar teamspace/folder trees, favorites) immediately — without
 * those independently-loaded view-models needing to reload.
 *
 * `set` is called on rename; views render `titleOf(doc)` instead of `doc.title`.
 * The override only ever makes a name more current, so a stale server copy in a
 * sidebar VM is corrected the moment the user renames. */
import { SvelteMap } from 'svelte/reactivity';

const overrides = new SvelteMap<string, string>();

export const docTitles = {
	set(id: string, title: string): void {
		overrides.set(id, title);
	},
	/** The live title for a document: the latest rename, else its loaded title. */
	titleOf(doc: { id: string; title: string }): string {
		return overrides.get(doc.id) ?? doc.title;
	}
};
