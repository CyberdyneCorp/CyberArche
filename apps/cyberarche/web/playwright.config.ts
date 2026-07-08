import { defineConfig } from '@playwright/test';

/** E2E against the real backend: Playwright boots our FastAPI service
 * (in-memory store, LIVE CyberdyneAuth for tokens) plus the vite dev
 * server, and signs in with the CYBERARCHE_IT_* test user.
 *
 * globalSetup acquires ONE session for the whole suite — logging in per
 * spec trips the live auth service's rate limit, and the throttled spec
 * then fails far from the cause. */

const AUTH_URL =
	process.env.CYBERARCHE_IT_AUTH_URL ?? 'https://auth.backend.coolify.cyberdynecorp.ai';

export default defineConfig({
	testDir: 'e2e',
	globalSetup: './e2e/global-setup.ts',
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
				'uv run --directory ../../.. uvicorn --factory cyberarche.api.bootstrap:create_app --host 127.0.0.1 --port 8123',
			url: 'http://127.0.0.1:8123/api/v1/health',
			reuseExistingServer: false, // fresh in-memory state every run
			env: {
				CYBERARCHE_BACKEND: 'memory',
				CYBERARCHE_AUTH_BASE_URL: AUTH_URL,
				CYBERARCHE_RAG_BASE_URL: '',
				// Real LLM for the agent e2e when a key is provided.
				CYBERARCHE_LLM_PROVIDER: 'openai',
				CYBERARCHE_LLM_MODEL: process.env.CYBERARCHE_IT_LLM_MODEL ?? 'gpt-4o-mini',
				CYBERARCHE_LLM_API_KEY: process.env.CYBERARCHE_IT_OPENAI_KEY ?? ''
			}
		},
		{
			// External MCP fixture the connectors e2e attaches to.
			command:
				'uv run --directory ../../.. python apps/cyberarche/web/e2e/fixtures/ticketing_mcp.py',
			url: 'http://127.0.0.1:8200/health',
			reuseExistingServer: !process.env.CI
		},
		{
			command: 'pnpm dev --port 5173 --strictPort',
			env: { CYBERARCHE_API_ORIGIN: 'http://127.0.0.1:8123' },
			url: 'http://localhost:5173',
			reuseExistingServer: !process.env.CI
		}
	]
});
