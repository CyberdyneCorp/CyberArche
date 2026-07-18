# CyberArche — Security Audit

**Engagement:** White-box pentest, owner-authorized (`.claude/security-scope.yaml`).
**Date:** 2026-07-13
**Targets:** CyberArche API / web / MCP (production + local docker-compose instance),
integration with CyberdyneAuth (IdP, analysis only). Google Workspace connector out of scope.
**Method:** White-box source review + active testing against a local instance
(ports 18000/18100/15173) and read-only/active probes against production.
**Standard:** No-Exploit-No-Report — theoretical-only items are Informational.

## Executive summary

The multi-tenant isolation core is **strong**: every Postgres query is
tenant-scoped, the one tenant-bypassing repository method (`get_any_tenant`) is
used only in the share-link flow and always re-gated by a document grant,
share-link IDs are UUID4, all inbound surfaces (HTTP, MCP, WebSocket) funnel
through the same application-layer `AccessControl`, and SQL is fully
parameterized (no SQLi), with no command-injection, SSTI, path-traversal, or
CSRF exposure. CORS is a correct exact-allowlist.

The findings cluster in **auth-token hardening, an SSRF surface, credential
encryption fail-open, and missing platform hardening (rate limits, security
headers)** rather than in the access-control model.

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 2 |
| Medium | 6 |
| Low | 8 |
| Informational | 6 |

**Top priorities:** F-001 (connector-secret fail-open → cleartext OAuth tokens),
F-002 (MCP-connector SSRF, live PoC), F-003 (audience-less JWTs accepted →
cross-realm replay), F-004 (refresh token in localStorage), F-006 (no rate
limiting on the login proxy).

---

## FINDING-001 — Connector encryption silently falls back to non-encryption when key unset
- **Skill:** secrets-in-code / crypto-flaw · **Severity:** High (config-conditional Critical)
- **CVSS v3.1:** 7.5 · **CWE:** CWE-312 (Cleartext Storage) + CWE-311 (Missing Encryption)
- **Status:** Confirmed (white-box) · **Asset:** API (all environments)
- **Location:** `libs/cyberarche/adapters/src/cyberarche/adapters/wiring/__init__.py:596-603` (`_build_secret_box`); fallback `libs/cyberarche/application/src/cyberarche/application/testing/fakes.py:1005-1012` (`NaiveSecretBox`)

**Summary.** `_build_secret_box` uses `FernetSecretBox` only when
`config.connector_secret_key` is truthy; otherwise it returns `NaiveSecretBox`,
whose `encrypt()` is `b"enc:" + plaintext[::-1]` — a byte reversal, no key, no
authentication. This box encrypts **external MCP connector credentials and
Google OAuth access/refresh tokens** at rest. `docker-compose.yml` maps
`CYBERARCHE_CONNECTOR_SECRET_KEY` with **no default**, so if the Coolify var is
unset/blank the app boots with reversible obfuscation and no warning.
`FernetSecretBox` correctly rejects an empty key — but the wiring routes around
that guard.

**Impact.** Any DB read (backup, snapshot, SQLi, insider) exposes every user's
connector secrets and live Google OAuth tokens → downstream account takeover.

**Remediation.** Fail closed: when `backend == "postgres"`, raise at startup if
`connector_secret_key` is empty. Restrict `NaiveSecretBox` to the in-memory/test
backend. Add a startup assertion that a real SecretBox is active in production.

---

## FINDING-002 — Server-Side Request Forgery via MCP connector registration
- **Skill:** ssrf · **Severity:** High · **CVSS v3.1:** 8.5 (`AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N`)
- **CWE:** CWE-918 · **OWASP:** A10:2021 / API7:2023 · **Status:** Confirmed (live PoC, local)
- **Asset:** API · **Endpoint:** `POST /api/v1/workspaces/{id}/connectors`
- **Location:** `routers/connectors.py` (`RegisterConnectorRequest.endpoint`, no validation) → `use_cases/connectors.py:59` (`register()` handshakes the raw URL) → `adapters/outbound/mcp_client/fastmcp_client.py:11-18` (`StreamableHttpTransport(endpoint)`, no scheme/host allowlist)

**Summary.** The connector `endpoint` is a bare user-supplied string, fetched
server-side during registration (and re-fetched on every later agent run via
`tools()`/`call()`, which only require VIEWER). No scheme check, no internal-range
block. This is the only outbound adapter without a config-fixed base URL.

**Evidence (live, local instance, authenticated as workspace owner):**
```
POST /api/v1/workspaces/{ws}/connectors  {"endpoint":"http://redis:6379/", ...}
→ "MCP handshake with http://redis:6379/ failed: Client failed to connect: "        (open port)
POST … {"endpoint":"http://169.254.169.254/latest/meta-data/", ...}
→ "MCP handshake with http://169.254.169.254/... failed: Timed out while waiting..." (filtered metadata)
POST … {"endpoint":"http://postgres:5433/", ...}
→ "MCP handshake with http://postgres:5433/ failed: All connection attempts failed" (closed port)
```
Three distinct error oracles turn this into a **blind internal port scanner /
service fingerprinter**. The raw transport error is returned to the caller
(`connectors.py:61-63`), amplifying the leak.

**Impact.** Authenticated tenant owner can probe internal network topology
(cloud metadata, `postgres`, `redis`, `interpreter.backend`, …). Full
cloud-credential theft is partially gated because the transport POSTs JSON-RPC
(AWS IMDS rejects POST), but internal reachability + fingerprinting are fully
confirmed.

**Remediation.** Validate `endpoint` before every handshake: enforce
`https://` (or an explicit allowlist), resolve the host and reject RFC-1918 /
loopback / link-local / `169.254.169.254`, re-resolve at fetch time (DNS-rebind
safe). Return a generic "handshake failed"; log details server-side. Add egress
filtering from the app subnet and enforce IMDSv2.

---

## FINDING-003 — JWT audience not verified; tokens carry no audience → cross-realm replay
- **Skill:** jwt / oauth-oidc · **Severity:** Medium · **CVSS v3.1:** 6.5
- **CWE:** CWE-287 / CWE-1220 · **Status:** Confirmed (white-box + live token inspection)
- **Location:** `adapters/outbound/auth/cyberdyne.py:108-114` (`verify_aud: self._config.audience is not None`); `services/*/config.py` (`auth_audience` defaults `None`, unset in `docker-compose.yml`)

**Summary.** `jwt.decode` only verifies audience when `auth_audience` is
configured — and it is unset in production. A live CyberdyneAuth token decodes
to **`aud: None`** (no audience claim at all), so CyberArche cannot distinguish a
token minted for the SPA from one minted for any other client in the same
CyberdyneAuth realm. Acceptance rests solely on "RS256-signed by a key in the
realm JWKS."

**Impact.** A token obtained by any sibling application in the realm is
replayable against CyberArche as that user.

**Remediation.** Have CyberdyneAuth stamp a per-client `aud`, make `audience`
required config in CyberArche, and set `options={"verify_aud": True, "require":
["exp","iat","aud","sub"]}` — fail closed at startup if unset.

---

## FINDING-004 — Access and refresh tokens stored in localStorage (XSS → persistent takeover)
- **Skill:** jwt / xss · **Severity:** Medium (High when chained with any XSS) · **CVSS v3.1:** 8.1 (chained)
- **CWE:** CWE-522 / CWE-539 · **Status:** Confirmed (white-box)
- **Location:** `apps/cyberarche/web/src/lib/viewmodels/session.svelte.ts:33` (write), `:14-22`/`:63-69` (read)

**Summary.** `persist()` writes `{access, refresh}` as plaintext JSON to
`localStorage['cyberarche.session']`. Any JS on the origin (an XSS, or a
malicious npm dependency) reads both. The long-lived **refresh** token lets an
attacker mint access tokens indefinitely. `logout()` only clears local state —
there is **no server-side/IdP revocation** — so a stolen token survives logout
until natural expiry. This is the impact multiplier for every XSS-class finding.

**Remediation.** Keep the refresh token out of localStorage (in-memory access
token + silent refresh, or an `HttpOnly; Secure; SameSite=Strict` refresh cookie
scoped to the refresh endpoint). Add a real logout that revokes the refresh
token at the IdP. Ship the CSP from F-005.

---

## FINDING-005 — No security-headers middleware (clickjacking + no XSS containment)
- **Skill:** clickjacking / xss · **Severity:** Medium · **CVSS v3.1:** 4.3
- **CWE:** CWE-1021 / CWE-693 · **Status:** Confirmed (active probe)
- **Location:** `services/cyberarche/api/src/cyberarche/api/bootstrap.py:78-90` (CORS + access log only); web host likewise

**Summary.** Confirmed by response inspection: no `Content-Security-Policy`,
`X-Frame-Options`/`frame-ancestors`, `Strict-Transport-Security`, or
`X-Content-Type-Options` on API or web responses. The app can be framed
(clickjacking of authenticated share/delete/invite actions), and there is no CSP
to contain any script-injection defect (compounds F-004, F-014, F-015).

**Remediation.** Add a headers middleware: `Content-Security-Policy` with a
`script-src` and `frame-ancestors 'none'`, `X-Frame-Options: DENY`,
`X-Content-Type-Options: nosniff`, `Strict-Transport-Security`. Set framing
headers on the web host too.

---

## FINDING-006 — No rate limiting (login-proxy brute force + LLM/RAG denial-of-wallet)
- **Skill:** rate-limit / auth-flaw · **Severity:** Medium · **CVSS v3.1:** 6.5
- **CWE:** CWE-307 / CWE-770 · **Status:** Confirmed (white-box; not exercised on prod per scope)
- **Location:** `bootstrap.py:78-90` (no limiter middleware); `routers/auth.py:44-51`

**Summary.** No throttling anywhere. `POST /api/v1/auth/session` proxies password
login to CyberdyneAuth with no per-IP/per-account limit → unlimited credential
stuffing from one client. LLM/agent and `knowledge/query`/ingest endpoints invoke
paid providers with no per-caller cap → an authenticated low-priv member can loop
expensive calls (denial-of-wallet). Uploads and share-link redeem are unthrottled.

**Remediation.** Per-IP + per-account limits on the auth proxy; per-caller
quotas/concurrency caps on LLM/RAG/upload endpoints; 429 on breach. (Scope marks
prod `service_affecting: denied`, so this was not exercised against production.)

---

## FINDING-007 — Postgres default credentials in docker-compose
- **Skill:** container / secrets · **Severity:** Medium · **CVSS v3.1:** 6.5 (→~5 mitigated)
- **CWE:** CWE-1188 / CWE-798 · **Status:** Confirmed (white-box) · **Location:** `docker-compose.yml`

**Summary.** `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-cyberarche}` (and matching
user + `CYBERARCHE_DATABASE_URL`) boot the DB with `cyberarche`/`cyberarche` if
the Coolify vars are unset. Postgres is only `expose`d internally, limiting blast
radius, but any container/network foothold yields trivial DB access.

**Remediation.** Drop the `:-cyberarche` defaults so a missing secret fails the
deploy; require a strong generated password.

---

## FINDING-008 — JWT issuer not validated; `exp` not required
- **Skill:** jwt · **Severity:** Medium/Low · **CVSS v3.1:** 6.5 (iss) / 3.7 (exp)
- **CWE:** CWE-347 / CWE-613 · **Status:** Confirmed (white-box)
- **Location:** `adapters/outbound/auth/cyberdyne.py:108-114`

**Summary.** `jwt.decode` passes no `issuer=` and no `options={"require":[...]}`.
The `iss` claim (`cyberdyne-auth` on real tokens) is ignored — removing the
second independent guardrail alongside the missing `aud` (F-003). A token minted
without `exp` would be accepted and never expire.

**Remediation.** `jwt.decode(..., issuer=expected_issuer, options={"require":
["exp","iat","iss","sub"], "verify_aud": True})`; make `issuer`/`audience`
required config.

---

## FINDING-009 — Share-link redeem writes grant before existence/trashed check
- **Skill:** business-logic · **Severity:** Low · **CVSS v3.1:** 4.2
- **CWE:** CWE-841 · **Status:** Confirmed (white-box) · **Location:** `use_cases/sharing.py:147-170`

**Summary.** `open_share_link` persists the `DocumentGrant` (`:159-166`) before
checking the document exists / is trashed (`:167-169`). `ShareLink.is_usable`
checks only revoked/expired, not document state. Redeeming a usable link whose
doc was trashed returns 404 but leaves a live grant; when the doc is restored the
recipient silently retains access. Redeeming after a hard purge writes an orphan
grant.

**Remediation.** Load and validate the document (exists + not trashed) *before*
`add_document_grant`.

---

## FINDING-010 — Scheduled-agent run history/instructions readable by any workspace VIEWER
- **Skill:** bola-bfla / excessive-data-exposure · **Severity:** Low · **CVSS v3.1:** 4.3
- **CWE:** CWE-639 · **Status:** Confirmed (white-box) · **Location:** `use_cases/scheduled_agents.py:143-162`

**Summary.** `list_runs` requires only VIEWER (`_require_task`). Run records
expose `detail` = first 500 chars of another user's agent output; task listing
exposes each task's `instruction` and `owner_id` to all viewers.

**Remediation.** Restrict run history (and per-task instruction detail) to the
task `owner_id` or workspace OWNER, mirroring `delete`.

---

## FINDING-011 — Any workspace EDITOR can toggle another user's scheduled agent
- **Skill:** bola-bfla · **Severity:** Low · **CVSS v3.1:** 4.3
- **CWE:** CWE-285 · **Status:** Confirmed (white-box) · **Location:** `use_cases/scheduled_agents.py:110-129`

**Summary.** `set_enabled` requires only EDITOR, unlike `delete`
(OWNER-or-task-owner). Re-enabling a task causes it to run **as the task's
owner** (`execute_task` builds `CallerContext(user_id=task.owner_id, …)`), a
limited run-as-owner lever on a schedule the owner didn't authorize.

**Remediation.** Gate `set_enabled` on OWNER-or-task-owner, consistent with `delete`.

---

## FINDING-012 — WebSocket bearer token in query string (log leakage)
- **Skill:** session-flaw · **Severity:** Low · **CVSS v3.1:** 3.7 · **CWE:** CWE-598
- **Status:** Confirmed (white-box) · **Location:** `adapters/inbound/http/realtime.py:125`; client `apps/cyberarche/web/src/lib/crdt/provider.ts:110`

**Summary.** `WS /api/v1/documents/{id}/sync?token=<bearer>` puts the live access
token in the URL → captured by reverse-proxy/CDN/access logs and browser history.
The app's own access log records only the path, but intermediaries you don't
control will capture the query. Common WS trade-off, hence Low.

**Remediation.** Exchange a short-lived single-use ticket over an authenticated
POST and put only the ticket in the URL, or use a `Sec-WebSocket-Protocol`
subprotocol token. Ensure proxies don't log WS query strings.

---

## FINDING-013 — Unknown-`kid` tokens force unbounded JWKS refetch (amplification DoS)
- **Skill:** jwt · **Severity:** Low · **CVSS v3.1:** 5.3 · **CWE:** CWE-770 / CWE-405
- **Status:** Confirmed (white-box; not exercised — prod `service_affecting: denied`)
- **Location:** `adapters/outbound/auth/cyberdyne.py:119-132`

**Summary.** `_key_for` refetches JWKS whenever a token's (unsigned, attacker-set)
`kid` is unknown, with no negative cache or rate limit. A stream of well-formed
JWTs with random `kid`s amplifies attacker requests into outbound IdP traffic.
Not fail-open (keyset only replaced on success), but a JWKS fetch error surfaces
as a 500 rather than a clean 401.

**Remediation.** Rate-limit/negative-cache JWKS refresh; map transport errors to
401/503, not 500.

---

## FINDING-014 — Inline-math error injected unescaped into a `title=` attribute (HTML attribute injection)
- **Skill:** xss · **Severity:** Low · **CVSS v3.1:** 3.1 · **CWE:** CWE-79
- **Status:** Confirmed attribute-injection; JS execution not demonstrated
- **Location:** `apps/cyberarche/web/src/lib/editor/inline.ts:20-29`

**Summary.** `escapeHtml` escapes `& < >` but not `"`; the KaTeX error message
(which echoes raw user source) flows into a double-quoted `title="…"` rendered via
`{@html}`. A `"` breaks out and injects attributes onto the `<span>`. Verified the
breakout with a live KaTeX PoC; KaTeX truncates the echoed context (~15 chars +
`…`) and `< >` stay escaped, so a working JS payload could not be assembled — real
attribute injection, not demonstrated XSS. An `escapeAttr` that escapes quotes
already exists but is unused here.

**Remediation.** Use `escapeAttr(message)` for the `title` attribute (one-line fix).

---

## FINDING-015 — CodeBlock highlight fallback injects raw source on exception (latent XSS)
- **Skill:** xss · **Severity:** Low (latent) · **CVSS v3.1:** 2.0 · **CWE:** CWE-79
- **Status:** Confirmed latent · **Location:** `apps/cyberarche/web/src/lib/components/editor/blocks/CodeBlock.svelte:15-23,58`

**Summary.** The normal highlight.js path HTML-escapes; the `catch` returns raw
unescaped `source`, then `{@html}`-injected. highlight.js is designed not to
throw on arbitrary input, so this is latent, not currently reachable.

**Remediation.** `catch { return escapeHtml(source); }`.

---

## FINDING-016 — Weak Fernet key derivation (unsalted single SHA-256)
- **Skill:** crypto-flaw · **Severity:** Low · **CVSS v3.1:** 3.7 · **CWE:** CWE-916
- **Status:** Confirmed (white-box) · **Location:** `adapters/outbound/crypto.py:11-13`

**Summary.** The Fernet key is `sha256(secret)`, unsalted, no stretching. Fine for
a high-entropy random key (Fernet itself is authenticated AES-128-CBC+HMAC), but
nothing enforces entropy — a weak passphrase would be brute-forceable.

**Remediation.** Require a proper 32-byte urlsafe-base64 Fernet key, or derive via
scrypt/HKDF with a salt; validate key length/entropy at startup.

---

## FINDING-017 — Unpinned build-tool image `uv:latest`
- **Skill:** container · **Severity:** Low · **CVSS v3.1:** Low · **CWE:** CWE-1104
- **Status:** Confirmed (white-box) · **Location:** `docker/backend.Dockerfile:9`

**Summary.** `COPY --from=ghcr.io/astral-sh/uv:latest` is mutable → non-reproducible
builds + supply-chain surface. Other base images are tag-pinned but not
digest-pinned.

**Remediation.** Pin `uv` to a version; ideally digest-pin all base images.

---

## Informational

- **INFO-1 — CORS credentialed-wildcard guard.** Config is a safe exact allowlist
  today (`bootstrap.py:80-85`, no `*`, no Origin echo). Add a startup guard that
  rejects `CYBERARCHE_CORS_ORIGINS="*"` while `allow_credentials=True`.
- **INFO-2 — Cross-tenant membership by raw `user_id`.** Workspace/teamspace
  invite/add-member (`sharing.py`, `teamspaces.py`) accept an arbitrary `user_id`
  with no same-tenant check (OWNER-gated). Document share links are intentionally
  cross-tenant; workspace membership arguably should validate the invitee resolves
  within the tenant.
- **INFO-3 — Mermaid `securityLevel` implicit.** `MermaidBlock` relies on
  mermaid's default `strict` (DOMPurify) — safe now. Set `securityLevel:'strict'`
  explicitly so a future refactor can't silently open stored XSS.
- **INFO-4 — `is_service` heuristic is dead code.** `token_use=='client' or
  'client_id' in payload` sets `is_service`, but it is never read in
  application/domain logic — no current escalation, but fragile; remove or wire a
  real check.
- **INFO-5 — Secrets in on-disk `.env` (not committed).** `.env` is correctly
  gitignored and clean in git history. It holds a **second** OpenAI-shaped key
  (`CYBERARCHE_IT_OPENAI_KEY`) beyond the known one, plus IT-account creds —
  inventory and rotate; confirm non-production. (Values not read.)
- **INFO-6 — Embed iframe hardening.** Generic embeds are https-only and sandboxed
  without `allow-top-navigation` (safe). Consider dropping `allow-same-origin` for
  the generic provider or an embed-host allowlist.

## Verified clean (negative results)
Multi-tenant document isolation; `AccessControl` role logic; share-link ID
entropy (UUID4); MCP tool authorization; SQL injection (all parameterized);
command injection / SSTI / path traversal (incl. export ZIP — client-side, name
sanitized); CSRF (bearer-only, no ambient cookies); CORS origin reflection; JWT
algorithm confusion (RS256 pinned, RSA public key); introspection fail-open;
mass assignment (`created_by`/`tenant_id`/`role` never bound from bodies); API-key
& connector & file & RAG cross-user access; blob path traversal (SHA-256 keyed);
container non-root; no secret logging; no committed secrets; no non-TLS internal
calls; markdown/KaTeX/link/Mermaid `{@html}` sinks (escaped / trust:false /
strict-mode / scheme-gated).

## Skills run log
| Skill | Result |
|---|---|
| jwt / oauth-oidc (integration) | F-003, F-004, F-008, F-012, F-013; alg/introspection clean |
| ssrf / ssrf-cloud-metadata | F-002 (live PoC); other outbound adapters host-pinned |
| sqli / command-injection / ssti / path-traversal | Clean |
| idor / bola-bfla / mass-assignment / rate-limit / business-logic | F-006, F-009, F-010, F-011; core ACL clean |
| xss / dom-xss / csrf / cors / clickjacking / open-redirect | F-005, F-014, F-015; CSRF/CORS/redirect clean |
| secrets-in-code / crypto-flaw / container | F-001, F-007, F-016, F-017; no committed secrets |

## Coverage & blind spots
- **Shannon (autonomous PoC pentester):** cloned + registered as a project MCP
  server, but it is **pending interactive approval** (`claude` → approve `shannon`)
  and could not be activated in this non-interactive session. Not run.
- **Production:** active probes kept non-destructive and rate-limited per scope;
  `service_affecting`/`destructive` classes (F-006, F-013 exercise) were reviewed
  in source, not fired at prod.
- **CyberdyneAuth:** analyzed for integration only (passive); its own endpoints
  were not attacked.
- **Google Workspace connector:** out of scope, not tested.
