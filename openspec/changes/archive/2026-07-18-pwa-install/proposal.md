# Installable PWA + offline app shell

## Why

The web-push work added a service worker, and the editor already supports offline
CRDT editing — but there is no web app manifest or app icons, so CyberArche is
not installable, and the service worker does not cache the app shell, so a
reload with no network fails. A small amount of work turns it into a real
installable, offline-capable app.

## What Changes

- Add a web app manifest (name, theme/background colors, `standalone` display,
  app icons) and link it, theme-color, and an apple-touch-icon from the HTML
  shell. Generate branded PNG icons (192, 512, maskable, apple-touch).
- Extend the existing service worker with install/activate/fetch handlers that
  precache and serve the app shell offline (network-first navigations falling
  back to the cached shell; stale-while-revalidate for same-origin static
  assets), never caching API/auth/WebSocket traffic. The existing push and
  notificationclick handlers are preserved unchanged.
- Register the service worker on app startup (not only when enabling push).

## Impact

- Affected specs: `progressive-web-app` (new).
- Affected code: `static/manifest.webmanifest` + `static/icons/*`; `app.html`;
  the existing `static/sw.js`; a startup registration in the root layout.
  Frontend only; no backend or migration.
