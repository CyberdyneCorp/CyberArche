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
/** POST multipart/form-data. `request` leaves the Content-Type unset for a
 * non-string body, so fetch adds the multipart boundary itself. */
export const postForm = <T>(path: string, form: FormData) =>
	request<T>(path, { method: 'POST', body: form });

/** Fetch binary content (e.g. an uploaded image) with bearer auth + one refresh
 * retry. Used by <AuthImage> to load membership-gated files into an object URL,
 * since an <img> tag cannot send the Authorization header itself. */
export async function getBlob(path: string): Promise<Blob> {
	const send = async () => {
		const headers = new Headers();
		const token = auth.getAccessToken();
		if (token) headers.set('Authorization', `Bearer ${token}`);
		return fetch(`${API_BASE}${path}`, { headers });
	};
	let response = await send();
	if (response.status === 401 && (await auth.tryRefresh())) {
		response = await send();
	}
	if (!response.ok) {
		throw new ApiError(response.status, response.statusText);
	}
	return response.blob();
}
export const patch = <T>(path: string, body: unknown) =>
	request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
export const put = <T>(path: string, body: unknown) =>
	request<T>(path, { method: 'PUT', body: JSON.stringify(body) });
export const del = <T>(path: string) => request<T>(path, { method: 'DELETE' });
