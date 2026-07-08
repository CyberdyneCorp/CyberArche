/** HTTP core (Model layer): bearer auth, one refresh retry on 401.
 * Views never import this directly — only ViewModels via the api/ clients. */

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string
	) {
		super(`${status}: ${detail}`);
	}
}

interface AuthHooks {
	getAccessToken(): string | null;
	/** Attempt a token refresh; true if a new access token is available. */
	tryRefresh(): Promise<boolean>;
}

let auth: AuthHooks = { getAccessToken: () => null, tryRefresh: async () => false };

export function configureAuth(hooks: AuthHooks): void {
	auth = hooks;
}

export async function request<T>(
	path: string,
	init: RequestInit = {},
	{ retry = true }: { retry?: boolean } = {}
): Promise<T> {
	const headers = new Headers(init.headers);
	const token = auth.getAccessToken();
	if (token) headers.set('Authorization', `Bearer ${token}`);
	if (init.body && typeof init.body === 'string') {
		headers.set('Content-Type', 'application/json');
	}

	const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
	if (response.status === 401 && retry && (await auth.tryRefresh())) {
		return request<T>(path, init, { retry: false });
	}
	if (!response.ok) {
		const body = await response.json().catch(() => ({}));
		throw new ApiError(response.status, body.detail ?? response.statusText);
	}
	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}

export const get = <T>(path: string) => request<T>(path);
export const post = <T>(path: string, body?: unknown) =>
	request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) =>
	request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
export const del = <T>(path: string) => request<T>(path, { method: 'DELETE' });
