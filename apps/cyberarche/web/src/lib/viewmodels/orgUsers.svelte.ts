/** Org directory ViewModel (org-directory spec): debounced email search over
 * the organization's users, with an `unavailable` flag on 503 so views can
 * fall back to raw-id entry. With `loadAll`, pages through the whole
 * directory (capped) so views can render a full roster. */

import { ApiError } from '$lib/api/http';
import { listOrgUsers, type OrgUser } from '$lib/api/orgUsers';

const DEBOUNCE_MS = 250;
const ALL_PAGE_SIZE = 200;
const ALL_MAX_USERS = 1000;

interface UsersResult {
	users: OrgUser[];
	total: number;
}

async function fetchOnePage(search: string): Promise<UsersResult> {
	const page = await listOrgUsers(search);
	return { users: page.users, total: page.total };
}

async function fetchEveryPage(search: string): Promise<UsersResult> {
	const first = await listOrgUsers(search, 1, ALL_PAGE_SIZE);
	const users = [...first.users];
	const target = Math.min(first.total, ALL_MAX_USERS);
	for (let page = 2; users.length < target; page += 1) {
		const next = await listOrgUsers(search, page, ALL_PAGE_SIZE);
		if (next.users.length === 0) break;
		users.push(...next.users);
	}
	return { users: users.slice(0, ALL_MAX_USERS), total: first.total };
}

export function createOrgUsers(options: { loadAll?: boolean } = {}) {
	const fetchUsers = options.loadAll ? fetchEveryPage : fetchOnePage;

	let users = $state<OrgUser[]>([]);
	let total = $state(0);
	let loading = $state(false);
	let unavailable = $state(false);
	let error = $state<string | null>(null);

	let timer: ReturnType<typeof setTimeout> | null = null;
	let seq = 0;

	async function refresh(search: string): Promise<void> {
		const ticket = ++seq;
		try {
			const result = await fetchUsers(search);
			if (ticket !== seq) return;
			users = result.users;
			total = result.total;
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
		/** True when the directory holds more users than were fetched (cap). */
		get truncated() {
			return total > users.length;
		},

		/** Fetch immediately (initial load — no debounce). */
		async load(): Promise<void> {
			loading = true;
			await refresh('');
		},

		/** Debounced search as the user types. */
		search(query: string): void {
			loading = true;
			if (timer !== null) clearTimeout(timer);
			timer = setTimeout(() => {
				timer = null;
				void refresh(query.trim());
			}, DEBOUNCE_MS);
		}
	};
}

export type OrgUsersVM = ReturnType<typeof createOrgUsers>;
