/** Session ViewModel: token state, login/logout, refresh-on-401.
 *
 * The access token is held in memory ONLY — never localStorage — and the
 * refresh token lives in an HttpOnly cookie the browser manages, so an XSS
 * cannot steal either for persistent account takeover (security audit F-004).
 * A session is restored on load by a silent refresh against that cookie. */

import { login as apiLogin, logout as apiLogout, refreshSession } from '$lib/api/auth';
import { configureAuth } from '$lib/api/http';

export function createSession() {
	let access = $state<string | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);
	// True until the initial cookie-based restore settles, so route guards don't
	// bounce a returning user to /signin before the silent refresh completes.
	let restoring = $state(true);

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
		get restoring() {
			return restoring;
		},
		getAccessToken(): string | null {
			return access;
		},
		/** JWT subject (user id) from the access token, if present. */
		get userId(): string | null {
			if (!access) return null;
			try {
				const payload = access.split('.')[1];
				return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/'))).sub ?? null;
			} catch {
				return null;
			}
		},

		/** Restore a session from the HttpOnly refresh cookie (silent refresh). */
		async init(): Promise<void> {
			try {
				await vm.tryRefresh();
			} finally {
				restoring = false;
			}
		},

		async login(email: string, password: string): Promise<boolean> {
			busy = true;
			error = null;
			try {
				const tokens = await apiLogin(email, password);
				access = tokens.access_token;
				return true;
			} catch {
				error = 'Sign-in failed — check your email and password.';
				return false;
			} finally {
				busy = false;
			}
		},

		async tryRefresh(): Promise<boolean> {
			try {
				const tokens = await refreshSession();
				access = tokens.access_token;
				return true;
			} catch {
				// No usable cookie/session — clear locally (no network logout: that
				// would recurse, and there's nothing to revoke).
				access = null;
				return false;
			}
		},

		async logout(): Promise<void> {
			try {
				await apiLogout(); // clears the refresh cookie server-side
			} catch {
				// Clear the local session regardless of network outcome.
			}
			access = null;
		}
	};

	configureAuth({ getAccessToken: vm.getAccessToken, tryRefresh: vm.tryRefresh });
	return vm;
}

export const session = createSession();
