/** Session ViewModel: token state, login/logout, refresh-on-401.
 * Persisted in localStorage; wires itself into the HTTP core's auth hooks. */

import { login as apiLogin, refreshSession } from '$lib/api/auth';
import { configureAuth } from '$lib/api/http';

const STORAGE_KEY = 'cyberarche.session';

interface StoredSession {
	access: string;
	refresh: string;
}

function loadStored(): StoredSession | null {
	if (typeof localStorage === 'undefined') return null;
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		return raw ? (JSON.parse(raw) as StoredSession) : null;
	} catch {
		return null;
	}
}

export function createSession() {
	let access = $state<string | null>(null);
	let refresh = $state<string | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);

	function persist() {
		if (typeof localStorage === 'undefined') return;
		if (access && refresh) {
			localStorage.setItem(STORAGE_KEY, JSON.stringify({ access, refresh }));
		} else {
			localStorage.removeItem(STORAGE_KEY);
		}
	}

	const vm = {
		get isAuthenticated() {
			return access !== null;
		},
		get error() {
			return error;
		},
		get busy() {
			return busy;
		},
		getAccessToken(): string | null {
			return access;
		},

		restore(): boolean {
			const stored = loadStored();
			if (!stored) return false;
			access = stored.access;
			refresh = stored.refresh;
			return true;
		},

		async login(email: string, password: string): Promise<boolean> {
			busy = true;
			error = null;
			try {
				const tokens = await apiLogin(email, password);
				access = tokens.access_token;
				refresh = tokens.refresh_token;
				persist();
				return true;
			} catch {
				error = 'Sign-in failed — check your email and password.';
				return false;
			} finally {
				busy = false;
			}
		},

		async tryRefresh(): Promise<boolean> {
			if (!refresh) return false;
			try {
				const tokens = await refreshSession(refresh);
				access = tokens.access_token;
				refresh = tokens.refresh_token;
				persist();
				return true;
			} catch {
				vm.logout();
				return false;
			}
		},

		logout() {
			access = null;
			refresh = null;
			persist();
		}
	};

	configureAuth({ getAccessToken: vm.getAccessToken, tryRefresh: vm.tryRefresh });
	return vm;
}

export const session = createSession();
