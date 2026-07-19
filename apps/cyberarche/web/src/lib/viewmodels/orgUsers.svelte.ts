/** Org directory ViewModel (org-directory spec): debounced email search over
 * the organization's users, with an `unavailable` flag on 503 so views can
 * fall back to raw-id entry. */

import { ApiError } from '$lib/api/http';
import { listOrgUsers, type OrgUser } from '$lib/api/orgUsers';

const DEBOUNCE_MS = 250;

export function createOrgUsers() {
	let users = $state<OrgUser[]>([]);
	let total = $state(0);
	let loading = $state(false);
	let unavailable = $state(false);
	let error = $state<string | null>(null);

	let timer: ReturnType<typeof setTimeout> | null = null;
	let seq = 0;

	async function fetchPage(search: string): Promise<void> {
		const ticket = ++seq;
		try {
			const page = await listOrgUsers(search);
			if (ticket !== seq) return;
			users = page.users;
			total = page.total;
			unavailable = false;
			error = null;
		} catch (err) {
			if (ticket !== seq) return;
			users = [];
			total = 0;
			unavailable = err instanceof ApiError && err.status === 503;
			error = unavailable ? null : (err as Error).message;
		} finally {
			if (ticket === seq) loading = false;
		}
	}

	return {
		get users() {
			return users;
		},
		get total() {
			return total;
		},
		get loading() {
			return loading;
		},
		get unavailable() {
			return unavailable;
		},
		get error() {
			return error;
		},

		/** Fetch immediately (initial load — no debounce). */
		async load(): Promise<void> {
			loading = true;
			await fetchPage('');
		},

		/** Debounced search as the user types. */
		search(query: string): void {
			loading = true;
			if (timer !== null) clearTimeout(timer);
			timer = setTimeout(() => {
				timer = null;
				void fetchPage(query.trim());
			}, DEBOUNCE_MS);
		}
	};
}

export type OrgUsersVM = ReturnType<typeof createOrgUsers>;
