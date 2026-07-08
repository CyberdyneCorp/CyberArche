# Integration Testing

The unit suite runs everything against in-memory fakes. Two extra layers
verify the real adapters; both are opt-in via environment variables and
are skipped otherwise (locally and in CI).

## 1. Postgres contract suites

The per-port contract tests (`tests/test_port_contracts.py`) automatically
add a `postgres` parametrization when `TEST_DATABASE_URL` is set. Use a
dedicated database — the suite truncates all tables between tests.

```bash
docker run -d --name cyberarche-pg \
  -e POSTGRES_USER=cyberarche -e POSTGRES_PASSWORD=cyberarche \
  -e POSTGRES_DB=cyberarche -p 5544:5432 postgres:16

DATABASE_URL="postgresql://cyberarche:cyberarche@localhost:5544/cyberarche" \
  uv run python scripts/migrate.py

TEST_DATABASE_URL="postgresql://cyberarche:cyberarche@localhost:5544/cyberarche" \
  uv run pytest tests/test_port_contracts.py
```

## 2. Live CyberdyneAuth pass

`tests/test_integration_live.py` runs the real `JwksTokenVerifier` against
the auth service's JWKS and drives the full HTTP + realtime vertical on
Postgres with a real bearer token. Requires a test user; credentials are
passed via environment only — never commit them.

```bash
TEST_DATABASE_URL="postgresql://cyberarche:cyberarche@localhost:5544/cyberarche" \
CYBERARCHE_IT_AUTH_URL="https://auth.backend.coolify.cyberdynecorp.ai" \
CYBERARCHE_IT_EMAIL="<test-user-email>" \
CYBERARCHE_IT_PASSWORD="<test-user-password>" \
  uv run pytest tests/test_integration_live.py -v
```

What it verifies:

- Login against the live auth service returns an RS256 JWT
- Our verifier accepts it via the live JWKS (and the personal-tenant
  fallback applies — the current tokens carry no `org_id` claim)
- A tampered signature is rejected
- Workspace → document → snapshot → trash/restore over real Postgres
- Two WebSocket clients converge through the Postgres-persisted update log

## 3. Live CyberdyneRAG pass

`tests/test_integration_rag_live.py` drives the real `CyberdyneRagAdapter`
against the live RAG service. It authenticates with a CyberdyneAuth user
token (the RAG API accepts them as bearer tokens), works only inside a
disposable `cyberarche-it-<random>` project, and hard-deletes it on the
way out — existing projects are never touched.

```bash
CYBERARCHE_IT_AUTH_URL="https://auth.backend.coolify.cyberdynecorp.ai" \
CYBERARCHE_IT_EMAIL="<test-user-email>" \
CYBERARCHE_IT_PASSWORD="<test-user-password>" \
CYBERARCHE_IT_RAG_URL="https://cyberrag.coolify.cyberdynecorp.ai" \
  uv run pytest tests/test_integration_rag_live.py -v
```

What it verifies:

- `ensure_project` creates when missing and is idempotent
- Upload → task polling → `completed`; retrieval answers are grounded in
  the ingested content (hybrid mode)
- `delete_datasource` cascade
- The full `KnowledgeUseCases` flow (provision → ingest → track → query →
  delete) over the live service, exactly as the API runs it

## Known limitations

- RLS policies exist in the schema but the app connects as the table
  owner, so they are defense-in-depth only once a dedicated non-owner app
  role (with `SET app.tenant_id`) is provisioned.
