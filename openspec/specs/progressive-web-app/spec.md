# progressive-web-app Specification

## Purpose
TBD - created by archiving change pwa-install. Update Purpose after archive.
## Requirements
### Requirement: Installable web app

The web app SHALL be installable as a standalone Progressive Web App: it SHALL
serve a web app manifest declaring the app name, theme and background colors,
standalone display mode, and app icons at the sizes required for installation
(including a maskable icon), and the HTML shell SHALL reference the manifest, a
theme color, and an apple-touch icon.

#### Scenario: Install prompt available

- **WHEN** the app is loaded over HTTPS with a registered service worker
- **THEN** the manifest and icons SHALL satisfy the browser's installability
  criteria so the app can be installed to the home screen / app launcher

### Requirement: Offline app shell

A service worker SHALL cache the application shell and serve it when the network
is unavailable, so a reload with no connectivity still loads the app. Navigation
requests SHALL be served network-first and fall back to the cached shell offline;
same-origin static assets SHALL be served stale-while-revalidate. API, auth, and
WebSocket requests SHALL NOT be cached. Existing push notification handling SHALL
be preserved.

#### Scenario: Reload while offline

- **GIVEN** the user has loaded the app at least once
- **WHEN** they reload with no network
- **THEN** the service worker SHALL serve the cached app shell

#### Scenario: API traffic is never cached

- **WHEN** the app makes an API, auth, or WebSocket request
- **THEN** the service worker SHALL NOT serve it from or store it in the cache

