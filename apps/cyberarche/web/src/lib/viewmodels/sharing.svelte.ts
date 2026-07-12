/** Sharing ViewModel (permissions-sharing spec 11.7): invites, links, comments. */

import {
	addComment,
	createShareLink,
	grantOnDocument,
	inviteToWorkspace,
	listComments,
	listShareLinks,
	resolveComment,
	revokeShareLink,
	type Comment,
	type ShareLink,
	type SharePermission,
	type ShareRole
} from '$lib/api/sharing';

export function createSharing(workspaceId: string, documentId: string) {
	let links = $state<ShareLink[]>([]);
	let comments = $state<Comment[]>([]);
	let error = $state<string | null>(null);
	let invited = $state<string | null>(null);

	async function guard<T>(action: () => Promise<T>): Promise<T | null> {
		error = null;
		try {
			return await action();
		} catch (err) {
			error = (err as Error).message;
			return null;
		}
	}

	return {
		documentId,
		get links() {
			return links;
		},
		get comments() {
			return comments;
		},
		get error() {
			return error;
		},
		get invited() {
			return invited;
		},
		commentsFor(blockId: string): Comment[] {
			return comments.filter((c) => c.block_id === blockId && !c.resolved);
		},

		async load() {
			await guard(async () => {
				comments = await listComments(documentId);
			});
			// Links are owner-only; a 403 just means the section stays empty.
			try {
				links = await listShareLinks(documentId);
			} catch {
				links = [];
			}
		},

		async invite(userId: string, role: ShareRole) {
			invited = null;
			const result = await guard(() => inviteToWorkspace(workspaceId, userId, role));
			if (result !== null) invited = userId;
		},

		async grant(userId: string, role: ShareRole) {
			invited = null;
			const result = await guard(() => grantOnDocument(documentId, userId, role));
			if (result !== null) invited = userId;
		},

		async createLink(permission: SharePermission) {
			await guard(async () => {
				const link = await createShareLink(documentId, permission);
				links = [...links, link];
			});
		},

		async revokeLink(linkId: string) {
			await guard(async () => {
				const revoked = await revokeShareLink(documentId, linkId);
				links = links.map((l) => (l.id === linkId ? revoked : l));
			});
		},

		linkUrl(link: ShareLink): string {
			return `${location.origin}/share/${link.id}`;
		},

		async comment(blockId: string, body: string) {
			await guard(async () => {
				const created = await addComment(documentId, blockId, body);
				comments = [...comments, created];
			});
		},

		async resolve(commentId: string) {
			await guard(async () => {
				const resolved = await resolveComment(documentId, commentId);
				comments = comments.map((c) => (c.id === commentId ? resolved : c));
			});
		}
	};
}

export type SharingVM = ReturnType<typeof createSharing>;
