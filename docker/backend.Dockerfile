# syntax=docker/dockerfile:1.4
# Shared image for the three backend deployables (api / mcp / workers);
# docker-compose overrides the command per service.
# Pattern: Infrastructure/Coolify — "Coolify Deploy Backend (FastAPI + uv)".

# Stage 1: base with uv
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Stage 2: dependencies (cached — only member pyprojects + lock)
FROM base AS deps

COPY pyproject.toml uv.lock ./
COPY libs/cyberarche/domain/pyproject.toml libs/cyberarche/domain/
COPY libs/cyberarche/application/pyproject.toml libs/cyberarche/application/
COPY libs/cyberarche/adapters/pyproject.toml libs/cyberarche/adapters/
COPY services/cyberarche/api/pyproject.toml services/cyberarche/api/
COPY services/cyberarche/mcp/pyproject.toml services/cyberarche/mcp/
COPY services/cyberarche/workers/pyproject.toml services/cyberarche/workers/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Stage 3: production
FROM base AS production

COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
COPY libs/ libs/
COPY services/ services/
COPY scripts/ scripts/
COPY db/ db/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Non-root user AFTER copying files; blob volume mount point owned by it.
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /data/blobs && \
    chown -R appuser:appuser /app /data
USER appuser

# NO `EXPOSE` here. This image serves api (8000), mcp (8100), and workers
# (none); each service declares its own `expose` in docker-compose. An image
# EXPOSE would merge with it, leaving the mcp container with two exposed
# ports — Traefik then cannot pick one and answers 502 on the public domain.

# Default command = API (migrations first; exec so SIGTERM reaches uvicorn).
CMD ["sh", "-c", "python scripts/migrate.py && exec uvicorn --factory cyberarche.api.bootstrap:create_app --host 0.0.0.0 --port 8000"]
