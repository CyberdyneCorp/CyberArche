/** API keys ViewModel: mint credentials for external MCP clients. */

import {
	createApiKey,
	listApiKeys,
	revokeApiKey,
	type ApiKey,
	type CreatedApiKey
} from '$lib/api/apiKeys';

export function createApiKeys() {
	let items = $state<ApiKey[]>([]);
	let justCreated = $state<CreatedApiKey | null>(null);
	let error = $state<string | null>(null);

	return {
		get items() {
			return items;
		},
		/** The one moment the secret is visible; cleared on dismiss. */
		get justCreated() {
			return justCreated;
		},
		get error() {
			return error;
		},

		async load() {
			items = await listApiKeys();
		},

		async create(name: string) {
			error = null;
			try {
				const created = await createApiKey(name);
				justCreated = created;
				items = [...items, created];
			} catch (err) {
				error = (err as Error).message;
			}
		},

		dismissSecret() {
			justCreated = null;
		},

		async revoke(keyId: string) {
			error = null;
			try {
				const revoked = await revokeApiKey(keyId);
				items = items.map((k) => (k.id === keyId ? revoked : k));
			} catch (err) {
				error = (err as Error).message;
			}
		}
	};
}

export type ApiKeysVM = ReturnType<typeof createApiKeys>;
