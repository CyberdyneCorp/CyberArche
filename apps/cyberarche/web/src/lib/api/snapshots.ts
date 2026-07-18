/** Snapshot (version history) API client: list / record / rename / restore /
 * diff a document's immutable versions (version-history spec). */

import type { BlockData } from '$lib/editor/registry';
import { get, patch, post } from './http';

export interface Snapshot {
	id: string;
	document_id: string;
	seq: number;
	created_at: string;
	restored_from: string | null;
	created_by: string | null;
	label: string | null;
}

export interface ModifiedBlock {
	id: string;
	before: string;
	after: string;
}

export interface BlockDiff {
	added: BlockData[];
	removed: BlockData[];
	modified: ModifiedBlock[];
}

export const listSnapshots = (documentId: string) =>
	get<Snapshot[]>(`/api/v1/documents/${documentId}/snapshots`);

export const recordSnapshot = (
	documentId: string,
	content: { blocks: BlockData[] },
	label?: string
) =>
	post<Snapshot>(`/api/v1/documents/${documentId}/snapshots`, {
		content,
		label: label ?? null
	});

export const renameSnapshot = (documentId: string, snapshotId: string, label: string | null) =>
	patch<Snapshot>(`/api/v1/documents/${documentId}/snapshots/${snapshotId}`, { label });

export const restoreSnapshot = (documentId: string, snapshotId: string) =>
	post<Snapshot>(`/api/v1/documents/${documentId}/snapshots/${snapshotId}/restore`);

export const diffSnapshots = (documentId: string, from: string, to?: string) => {
	const params = new URLSearchParams({ from });
	if (to) params.set('to', to);
	return get<BlockDiff>(`/api/v1/documents/${documentId}/snapshots/diff?${params}`);
};
