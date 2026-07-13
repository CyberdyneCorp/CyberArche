# Deployment (Coolify)

CyberArche runs as a Docker Compose application on Coolify.

| Service  | Image                     | Port | Public URL |
|----------|---------------------------|------|------------|
| web      | `apps/cyberarche/web`     | 80   | https://cyberarche.coolify.cyberdynecorp.ai |
| api      | `docker/backend.Dockerfile` | 8000 | https://cyberarche.backend.coolify.cyberdynecorp.ai |
| mcp      | same image, `cyberarche-mcp` | 8100 | https://cyberarche.mcp.coolify.cyberdynecorp.ai |
| workers  | same image, `cyberarche-workers` | — | internal |
| postgres | `postgres:16-alpine`      | 5432 | internal |
| redis    | `redis:7-alpine`          | 6379 | internal |

**Coolify app:** `ree00p47nytm4iajiqv34u8i` in project *CyberArche* /
environment *production*. Build pack `dockercompose`, source
`CyberdyneCorp/CyberArche@main` via the `leocoolify` GitHub App. Domains are
mapped per compose service (`docker_compose_domains`).

Migrations run in the api container's entrypoint before uvicorn starts; the
mcp and workers services wait for `api: service_healthy`.

## Environment variables (set in Coolify, never committed)

```
POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
CYBERARCHE_AUTH_BASE_URL / _CLIENT_ID / _CLIENT_SECRET   # cyberarche-backend client
CYBERARCHE_RAG_BASE_URL / _RAG_API_TOKEN / _RAG_WEBHOOK_SECRET
CYBERARCHE_LLM_PROVIDER / _MODEL / _API_KEY / _BASE_URL  # _BASE_URL for OpenAI-compatible endpoints
CYBERARCHE_MEETINGS_URL                                  # Cyberflies transcripts; defaults to prod URL
CYBERARCHE_CONNECTOR_SECRET_KEY                          # Fernet key for connector creds
CYBERARCHE_MCP_ALLOWED_HOSTS=cyberarche.mcp.coolify.cyberdynecorp.ai
CYBERARCHE_CORS_ORIGINS=["https://cyberarche.coolify.cyberdynecorp.ai"]  # literal
VITE_API_URL=https://cyberarche.backend.coolify.cyberdynecorp.ai         # BUILD arg
NPM_GITHUB_TOKEN                                         # BUILD arg: private npm registry (web)
```

`VITE_API_URL` and `NPM_GITHUB_TOKEN` are consumed at **build** time —
changing them requires a rebuild, not a restart.

The backend settings surface (`services/cyberarche/api/src/cyberarche/api/config.py`,
prefix `CYBERARCHE_`) is larger than the list above. Settings not mapped in
`docker-compose.yml`'s `environment:` block fall back to their in-code
defaults and **cannot be overridden from Coolify** until a mapping is added:

- `CYBERARCHE_DAO_URL` — DAO backend for agent web search + YouTube tools
  (defaults to the production URL; caller-token forwarded, works out of the box).
- `CYBERARCHE_INTERPRETER_URL` — Cyberdyne Python interpreter for the agent's
  `run_python` tool (defaults to the production URL).
- `CYBERARCHE_GOOGLE_CLIENT_ID / _SECRET / _REDIRECT_URI` — Google Workspace
  connector OAuth. Default empty = **disabled**; enabling it in production
  requires adding these to the compose `environment:` block.
- `CYBERARCHE_IMAGE_API_KEY / _MODEL / _BASE_URL` — agent `generate_image`
  tool. Default empty = **disabled**; same compose caveat as Google.
- `CYBERARCHE_ENABLE_SCHEDULER` / `_SCHEDULER_INTERVAL_SECONDS` — autonomous
  scheduled agents (default on, 60 s).
- `CYBERARCHE_AUTH_AUDIENCE` / `_AUTH_TENANT_CLAIM` — token validation tuning
  (defaults: none / `org_id`).

## Deploy

```bash
CLI="python3 ~/.claude/skills/coolify/coolify_cli.py --server cyberdyne"
$CLI deployments ree00p47nytm4iajiqv34u8i --limit 3   # status
curl -s "$COOLIFY_CYBERDYNE_URL/api/v1/deploy?uuid=ree00p47nytm4iajiqv34u8i&force=false" \
  -H "Authorization: Bearer $COOLIFY_CYBERDYNE_TOKEN"
```

## Connecting Claude / ChatGPT to the MCP server

1. Sign in → **Settings & connectors** → create an API key (shown once).
2. In the client's MCP connector config:
   - URL: `https://cyberarche.mcp.coolify.cyberdynecorp.ai/mcp/`
   - Header: `Authorization: Bearer cak_…`

The key authenticates as its owner with exactly that user's permissions and
can be revoked from the same screen.

## Deployment gotchas (learned the hard way)

See the vault note *Infrastructure/Coolify/Coolify Deploy MCP Servers
(FastMCP)* for the full write-up. In short:

- **No `EXPOSE` in the shared backend image.** Docker merges image `EXPOSE`
  with the compose `expose`; the mcp container would advertise two ports and
  Traefik cannot pick one → 502.
- **`CYBERARCHE_MCP_ALLOWED_HOSTS` must not break the health check.** The
  code appends `127.0.0.1[:port]` automatically; without it FastMCP's
  DNS-rebinding protection answers 421 to the container health check → the
  container is unhealthy → Traefik skips it → 502.
- **uvicorn needs `--proxy-headers`.** Otherwise FastMCP's `/mcp/` → `/mcp`
  redirect points at `http://`, and MCP clients (httpx) strip the
  `Authorization` header on the scheme change: `/health` is green,
  `tools/list` works, but every tool call reports "missing bearer token".
- **Blocking Redis reads must return `None` on timeout.** `redis-py`'s
  `brpop` raises `TimeoutError` on an idle 5 s poll, which used to kill the
  workers loop.

## Known follow-ups

- Postgres RLS policies exist but the app connects as the table owner; a
  dedicated non-owner role with `SET app.tenant_id` would make them active
  enforcement rather than defense-in-depth.
- Add the production redirect URI to the `cyberarche-web` OAuth client and
  wire the OIDC auth-code + PKCE flow (password sign-in works today).
- Blob storage is a Docker volume; swap `BlobStoragePort` for S3/MinIO when
  uploads outgrow the host.
