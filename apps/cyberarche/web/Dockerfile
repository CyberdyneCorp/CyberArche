# syntax=docker/dockerfile:1.4
# CyberArche web (SvelteKit adapter-static SPA) served by nginx.
# Pattern: Infrastructure/Coolify — "Coolify Deploy Frontend (SvelteKit)".

# Stage 1: build
FROM node:22-alpine AS build

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.32.1 --activate

# Auth for the private @cyberdynecorp GitHub Packages registry. .npmrc references
# ${NPM_GITHUB_TOKEN}; the token is a BUILD arg (Coolify build-time env) and lives
# only in this build stage — the nginx production stage never sees it.
ARG NPM_GITHUB_TOKEN
ENV NPM_GITHUB_TOKEN=${NPM_GITHUB_TOKEN}

COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

# VITE_ vars are baked at BUILD time (Coolify: pass via compose build args).
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

COPY . .
RUN pnpm build

# Stage 2: serve (static SPA, nginx fallback to index.html)
FROM nginx:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

# 127.0.0.1 + --spider: see knowledge base — localhost/-qO- silently 503s.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --spider http://127.0.0.1:80/ || exit 1
