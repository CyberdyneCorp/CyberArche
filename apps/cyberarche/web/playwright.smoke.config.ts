import { defineConfig } from '@playwright/test';

/** Post-deploy smoke suite against the DEPLOYED instance (no local servers).
 *
 * Targets the production web app and API; signs in with the CYBERARCHE_IT_*
 * test user via the app's own /api/v1/auth/session endpoint. Read-mostly:
 * the only writes are a throwaway document that is trashed (and its trash
 * purged) at the end of the run.
 *
 *   CYBERARCHE_SMOKE_WEB_URL  (default https://cyberarche.coolify.cyberdynecorp.ai)
 *   CYBERARCHE_SMOKE_API_URL  (default https://cyberarche.backend.coolify.cyberdynecorp.ai)
 *   CYBERARCHE_IT_EMAIL / CYBERARCHE_IT_PASSWORD  (required; suite skips without them)
 */
export default defineConfig({
	testDir: 'e2e-smoke',
	timeout: 30_000,
	retries: 1,
	fullyParallel: false,
	workers: 1,
	use: {
		baseURL: process.env.CYBERARCHE_SMOKE_WEB_URL ?? 'https://cyberarche.coolify.cyberdynecorp.ai',
		trace: 'retain-on-failure'
	}
});
