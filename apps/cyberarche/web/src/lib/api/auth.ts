/** Session endpoints (our API proxies CyberdyneAuth — BFF, no CORS). */

import { post } from './http';

export interface SessionTokens {
	access_token: string;
	refresh_token: string;
	token_type: string;
}

export const login = (email: string, password: string) =>
	post<SessionTokens>('/api/v1/auth/session', { email, password });

export const refreshSession = (refresh_token: string) =>
	post<SessionTokens>('/api/v1/auth/session/refresh', { refresh_token });
