# syntax=docker/dockerfile:1
#
# Multi-stage Dockerfile for an optional Vite + React web service.
# Build context: REPO ROOT.
#
# Targets:
#   deps     — restore node_modules from frozen lockfile. Intermediate.
#   builder  — produce production bundle in dist/. Intermediate.
#   dev      — Vite dev server with HMR; used by docker compose override.
#   prod     — nginx:alpine serving dist/ + /api proxy with SSE-friendly settings.
#
# If you ship the frontend to a static/CDN host, the prod target is mostly for
# local-prod parity testing and as a fallback.

ARG NODE_VERSION=20
ARG NGINX_VERSION=1.27

# ---------------- deps: install node_modules ----------------
FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@latest --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# ---------------- builder: produce dist/ ----------------
FROM deps AS builder
COPY apps/web/ ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm build

# ---------------- dev: Vite HMR on 5173 ----------------
FROM deps AS dev
COPY apps/web/ ./
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]

# ---------------- prod: nginx serving static files ----------------
FROM nginx:${NGINX_VERSION}-alpine AS prod
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
