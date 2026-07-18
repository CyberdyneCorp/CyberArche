/** History ViewModel (version-history spec): the timeline of a document's
 * versions plus the currently displayed block diff. Views bind to its getters;
 * it never touches the DOM. */

import {
	diffSnapshots,
	listSnapshots,
	renameSnapshot,
	restoreSnapshot,
	type BlockDiff,
	type Snapshot
} from '$lib/api/snapshots';

export function createHistory(documentId: string) {
	let versions = $state<Snapshot[]>([]);
	let diff = $state<BlockDiff | null>(null);
	let comparing = $state<string | null>(null); // the "from" snapshot id
	let busy = $state(false);
	let error = $state<string | null>(null);

	async function run<T>(work: () => Promise<T>): Promise<T | undefined> {
		busy = true;
		error = null;
		try {
			return await work();
		} catch (err) {
			error = (err as Error).message;
			return undefined;
		} finally {
			busy = false;
		}
	}

	return {
		get versions() {
			return versions;
		},
		get diff() {
			return diff;
		},
		/** The snapshot id currently being compared (drives the compare view). */
		get comparing() {
			return comparing;
		},
		get busy() {
			return busy;
		},
		get error() {
			return error;
		},

		async load() {
			await run(async () => {
				// Newest first — the timeline reads top-down from the latest version.
				versions = [...(await listSnapshots(documentId))].sort((a, b) => b.seq - a.seq);
			});
		},

		async rename(snapshotId: string, label: string) {
			const updated = await run(() =>
				renameSnapshot(documentId, snapshotId, label.trim() || null)
			);
			if (updated) versions = versions.map((v) => (v.id === updated.id ? updated : v));
		},

		async restore(snapshotId: string) {
			const recorded = await run(() => restoreSnapshot(documentId, snapshotId));
			if (recorded) await this.load();
			return recorded;
		},

		/** Diff `fromId` against `toId`, or against the current document when
		 * `toId` is omitted. */
		async diffAgainst(fromId: string, toId?: string) {
			const result = await run(() => diffSnapshots(documentId, fromId, toId));
			if (result) {
				diff = result;
				comparing = fromId;
			}
		},

		closeDiff() {
			diff = null;
			comparing = null;
		}
	};
}

export type HistoryVM = ReturnType<typeof createHistory>;
