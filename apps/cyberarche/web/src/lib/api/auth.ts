/** Session endpoints (our API proxies CyberdyneAuth — BFF, no CORS).
 *
 * The refresh token lives in an HttpOnly cookie the browser sends automatically
 * (credentials: 'include'); it is never in the JS-visible response (F-004). Only
 * the short-lived access token is returned here. `retry: false` stops a failed
 * refresh from recursing back into a refresh. */

import { request } from './http';

export interface SessionTokens {
	access_token: string;
	token_type: string;
}

export const login = (email: string, password: string) =>
	request<SessionTokens>(
		'/api/v1/auth/session',
		{ method: 'POST', body: JSON.stringify({ email, password }), credentials: 'include' },
		{ retry: false }
	);

export const refreshSession = () =>
	request<SessionTokens>(
		'/api/v1/auth/session/refresh',
		{ method: 'POST', credentials: 'include' },
		{ retry: false }
	);

export const logout = () =>
	request<void>(
		'/api/v1/auth/session/logout',
		{ method: 'POST', credentials: 'include' },
		{ retry: false }
	);
