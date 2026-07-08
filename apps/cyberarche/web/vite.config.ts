import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

// In dev/e2e the app calls the API with relative /api URLs; vite proxies
// them to the local FastAPI service (CYBERARCHE_API_ORIGIN overrides).
const apiOrigin = process.env.CYBERARCHE_API_ORIGIN ?? 'http://localhost:8000';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': { target: apiOrigin, changeOrigin: true, ws: true }
		}
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'jsdom'
	}
});
