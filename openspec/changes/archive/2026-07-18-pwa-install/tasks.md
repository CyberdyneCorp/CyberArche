# Tasks
- [ ] 1.1 Generate branded PNG icons (192, 512, maskable 512, apple-touch 180) into static/icons/
- [ ] 1.2 `static/manifest.webmanifest`; link manifest + theme-color + apple-touch-icon + favicon in app.html
- [ ] 1.3 Extend static/sw.js with install/activate/fetch (precache shell, network-first navigations, SWR static assets, bypass API/auth/ws); keep push handlers intact
- [ ] 1.4 Register the service worker on startup in the root layout (idempotent with the push flow)
- [ ] 1.5 Tests: manifest validity + icon presence; SW fetch routing (shell fallback, API bypass) via unit-testable helpers
- [ ] 1.6 `openspec validate pwa-install --strict`; gates green
