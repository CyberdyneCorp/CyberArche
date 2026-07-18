import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

// In dev/e2e the app calls the API with relative /api URLs; vite proxies
// them to the local FastAPI service (CYBERARCHE_API_ORIGIN overrides).
const apiOrigin = process.env.CYBERARCHE_API_ORIGIN ?? 'http://localhost:8000';

export default defineConfig({
	plugins: [sveltekit()],
	// Under Vitest, resolve Svelte's browser build so components can be mounted
	// (mount() is unavailable in the server build). Dev/build are untouched.
	...(process.env.VITEST ? { resolve: { conditions: ['browser'] } } : {}),
	server: {
		proxy: {
			'/api': { target: apiOrigin, changeOrigin: true, ws: true }
		}
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'jsdom',
		// Unit coverage is scoped to the logic layers (viewmodels, api clients,
		// editor/crdt utilities). Svelte views/routes are exercised by the
		// Playwright e2e suite instead. The Google connector UI is optional
		// (disabled without OAuth config) and excluded like on the backend.
		coverage: {
			provider: 'v8',
			include: ['src/lib/**/*.ts'],
			exclude: [
				'src/lib/**/*.test.ts',
				'src/lib/api/google.ts',
				'src/lib/viewmodels/google.svelte.ts'
			],
			thresholds: {
				statements: 90,
				lines: 90,
				branches: 80,
				functions: 85
			}
		}
	}
});
