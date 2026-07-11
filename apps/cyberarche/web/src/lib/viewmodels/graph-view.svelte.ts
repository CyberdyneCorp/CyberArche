/** Graph-view modal state (wikilink-graph-view): a module-level singleton the
 * <GraphModal/> in the workspace layout renders. Call `graphView.open(...)` from
 * a teamspace/folder context menu; the modal fetches and draws the link graph. */

export interface GraphScope {
	kind: 'teamspace' | 'folder';
	id: string;
	name: string;
}

export function createGraphView() {
	let current = $state<GraphScope | null>(null);

	return {
		get current() {
			return current;
		},
		open(scope: GraphScope): void {
			current = scope;
		},
		close(): void {
			current = null;
		}
	};
}

export const graphView = createGraphView();
