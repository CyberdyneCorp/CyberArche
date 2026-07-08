import { readFileSync } from 'node:fs';

import { SESSION_FILE } from './global-setup';

export interface Session {
	access: string;
	refresh: string;
}

export const API = 'http://127.0.0.1:8123';

/** The suite-wide session created by global-setup (one login, no rate limits). */
export function loadSession(): Session {
	return JSON.parse(readFileSync(SESSION_FILE, 'utf8')) as Session;
}

export function authHeaders(session: Session): Record<string, string> {
	return { Authorization: `Bearer ${session.access}` };
}
