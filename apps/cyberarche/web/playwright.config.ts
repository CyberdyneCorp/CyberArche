import { defineConfig } from '@playwright/test';

/** E2E against the real backend: Playwright boots our FastAPI service
 * (in-memory store, LIVE CyberdyneAuth for tokens) plus the vite dev
 * server, and signs in with the CYBERARCHE_IT_* test user. */

const AUTH_URL =
	process.env.CYBERARCHE_IT_AUTH_URL ?? 'https://auth.backend.coolify.cyberdynecorp.ai';

export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: process.env.CI ? 1 : 0,
	// Tests share one in-memory backend: run them serially so state
	// progressions (first-run workspace, tree contents) stay deterministic.
	fullyParallel: false,
	workers: 1,
	use: {
		baseURL: 'http://localhost:5173',
		trace: 'retain-on-failure'
	},
	webServer: [
		{
			command:
				'uv run --directory ../../.. uvicorn --factory cyberarche.api.bootstrap:create_app --port 8000',
			url: 'http://localhost:8000/api/v1/health',
			reuseExistingServer: false, // fresh in-memory state every run
			env: {
				CYBERARCHE_BACKEND: 'memory',
				CYBERARCHE_AUTH_BASE_URL: AUTH_URL,
				CYBERARCHE_RAG_BASE_URL: ''
			}
		},
		{
			command: 'pnpm dev --port 5173 --strictPort',
			url: 'http://localhost:5173',
			reuseExistingServer: !process.env.CI
		}
	]
});
