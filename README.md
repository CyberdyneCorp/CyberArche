# CyberArche

AI-centric, real-time collaborative document platform — a Notion/Confluence
alternative where math, diagrams, whiteboards, code, and an AI agent are
first-class, and multiple people (and the AI) edit the same document live.

Three differentiators:

1. **Rich technical blocks first-class** — LaTeX math, a native
   Excalidraw-style whiteboard (mind maps included), Mermaid diagrams, code
   blocks with syntax highlighting, tables, and a typed database block with
   table/board/calendar/gallery views.
2. **AI at the center** — every document has an agent that can summarize,
   draft, restructure, ingest files (PDF/CSV/Excel), search the web, run
   Python, generate images, read meeting transcripts, and edit the document as
   a first-class CRDT collaborator, grounded in the workspace via RAG. Agents
   have per-workspace personas, persistent memory, saved skills, and can run
   autonomously on a schedule.
3. **MCP-native** — CyberArche ships its own FastMCP server exposing tools
   over the user's documents, and users can attach external MCP servers so
   their agent gains extra capabilities. Google Workspace
   (Gmail/Calendar/Docs) is the only first-party SaaS connector; everything
   else goes through generic external MCP connectors.

## Stack

- **Backend** — Python 3.12+, FastAPI (HTTP) + FastMCP (MCP), Hexagonal
  Architecture, PostgreSQL, Redis, Yjs/CRDT realtime relay (pycrdt).
- **Frontend** — Svelte 5 (runes) + SvelteKit + TypeScript, strict MVVM.
- **LLM** — provider-agnostic behind an `LLMPort` (Anthropic/OpenAI-compatible
  via config).

## Repository layout

```
libs/cyberarche/          # domain / application / adapters (hexagonal core)
services/cyberarche/      # deployables: api (FastAPI), mcp (FastMCP), workers
apps/cyberarche/web/      # SvelteKit frontend
db/migrations/            # SQL migrations (applied by scripts/migrate.py)
tests/                    # backend unit suite (in-memory fakes) + opt-in integration
docs/                     # deployment, integration testing, design brief
openspec/                 # living specs (specs/) and change history (changes/archive/)
```

The dependency rule is `domain <- application <- adapters`; inbound adapters
never import outbound. Enforced with import-linter (`pyproject.toml`).

## Development

Backend (uses [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
uv run pytest                      # unit suite, in-memory fakes
uv run lint-imports                # architecture contracts
uv run python scripts/migrate.py   # apply migrations (needs CYBERARCHE_DATABASE_URL)
uv run uvicorn --factory cyberarche.api.bootstrap:create_app --reload
```

Frontend:

```bash
cd apps/cyberarche/web
npm install
npm run dev      # vite dev server on :5173
npm run check    # svelte-check
npm run test     # vitest
npm run e2e      # playwright
```

Full stack via Docker Compose: `docker compose up --build` (postgres, redis,
api, mcp, workers, web). See `docs/deployment.md` for the Coolify production
setup and environment variables, and `docs/integration-testing.md` for the
opt-in integration test layers.

## Specs

The product is spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec).
Current behavior lives in `openspec/specs/` (one folder per capability);
shipped changes are archived under `openspec/changes/archive/`. Medium/large
features and anything touching auth, security, or data models go through an
OpenSpec change first.
