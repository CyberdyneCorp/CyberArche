import { request } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

/** One login for the whole suite.
 *
 * Logging in per spec hammers the live auth service, which rate-limits: a
 * later spec would receive a token that immediately 401s, the SPA's refresh
 * would also be throttled, and the page silently bounced to /signin —
 * surfacing as "waiting for block-editor" timeouts in whichever spec ran
 * next. Acquire one session here and share it via SESSION_FILE.
 */
export const SESSION_FILE = 'e2e/.auth/session.json';

export default async function globalSetup(): Promise<void> {
	const email = process.env.CYBERARCHE_IT_EMAIL;
	const password = process.env.CYBERARCHE_IT_PASSWORD;
	if (!email || !password) return; // specs skip themselves

	const context = await request.newContext();
	let tokens: { access_token?: string; refresh_token?: string } = {};
	for (const delay of [0, 2000, 5000, 10_000, 20_000]) {
		if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
		const response = await context.post('http://127.0.0.1:8123/api/v1/auth/session', {
			data: { email, password }
		});
		if (response.ok()) {
			tokens = await response.json();
			break;
		}
	}
	await context.dispose();
	if (!tokens.access_token) throw new Error('e2e global login failed after retries');

	mkdirSync(dirname(SESSION_FILE), { recursive: true });
	writeFileSync(
		SESSION_FILE,
		JSON.stringify({ access: tokens.access_token, refresh: tokens.refresh_token })
	);
}
