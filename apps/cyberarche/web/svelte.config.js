import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// Pure SPA: the FastAPI backend is the only server.
		adapter: adapter({ fallback: 'index.html' }),
		// Poll for new deployments so a long-open tab doesn't keep running stale
		// client JS after a deploy (which stranded tabs on old reconnect logic).
		// The `updated` store flips true; the root layout offers a reload.
		version: { pollInterval: 60_000 }
	}
};

export default config;
