# `infra/web.Dockerfile` — Vite + React (optional)

## Table of contents
- [The four targets](#the-four-targets)
- [Reference layout (annotated)](#reference-layout-annotated)
- [Common edits](#common-edits)
- [What *not* to do](#what-not-to-do)

This file is **optional** — it exists to illustrate building a Node frontend in
the same monorepo. If your project ships its frontend to a static/CDN host
(Vercel, Netlify, Firebase Hosting, an object-store bucket + CDN, etc.), the
container's `prod` target is mostly for **local-prod parity** and as a fallback.
The drop-in template is `assets/web.Dockerfile`.

## The four targets

| Target | Purpose | Final image | CMD |
|---|---|---|---|
| `deps` | install node_modules with frozen lockfile | intermediate | — |
| `builder` | run `pnpm build` → `dist/` | intermediate | — |
| `dev` | Vite dev server with HMR | node:20-alpine + node_modules | `pnpm dev --host 0.0.0.0` |
| `prod` | static files served by nginx | nginx:alpine + `/usr/share/nginx/html` | `nginx -g 'daemon off;'` |

## Reference layout (annotated)

### Stage 1: `deps` — restore node_modules

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app

# pnpm via corepack (bundled with node:20). No global install.
RUN corepack enable && corepack prepare pnpm@latest --activate

COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
```

- **`corepack enable`** activates pnpm without `npm i -g pnpm` — the version is pinned by `packageManager` in `package.json`.
- **`pnpm install --frozen-lockfile`** mirrors `--locked` for uv: fails if `pnpm-lock.yaml` doesn't match `package.json`.
- The cache mount uses pnpm's content-addressable store. First install ~60s; cached reinstall ~5s.

### Stage 2: `builder` — produce `dist/`

```dockerfile
FROM deps AS builder
COPY apps/web/ ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm build
```

- `VITE_API_BASE_URL` is a build-time env var baked into the bundle. In compose we proxy `/api` → the api service via the nginx config. For multi-environment builds, pass `--build-arg VITE_API_BASE_URL=...`.

### Stage 3: `dev` — Vite HMR

```dockerfile
FROM deps AS dev
COPY apps/web/ ./
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]
```

- `--host 0.0.0.0` is required to be reachable from outside the container; Vite defaults to `localhost` which is unreachable from compose's network.
- The compose override mounts the host's `apps/web/` into `/app`, so HMR sees host-side edits.

### Stage 4: `prod` — nginx serving static files

```dockerfile
FROM nginx:alpine AS prod
# Custom nginx.conf: SPA fallback + reverse-proxy /api → api:8000
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1
```

`infra/nginx.conf` (also a template under `assets/`) provides:

- **SPA fallback** — every unknown path falls back to `index.html` so a client-side router can pick it up. Without this, a refresh on `/some/route` returns 404.
- **`/api/` reverse proxy** — local-only proxy to the api service. If your frontend streams Server-Sent Events, the proxy must set `proxy_buffering off` and a long `proxy_read_timeout`; default nginx buffering prevents tokens from streaming and the stream appears to hang.

## Common edits

- **Style change**: bind mount in `dev` picks it up via Vite HMR. No rebuild.
- **`package.json` change** (new dep): rebuild `deps` stage. The cache mount keeps the pnpm store warm; only the new package downloads.
- **Env var for the bundle**: add `ARG VITE_FOO` near top of `builder`, set `ENV VITE_FOO=$VITE_FOO`, pass `--build-arg VITE_FOO=...`. Vite only inlines `VITE_*`-prefixed variables into client bundles by default — respect that security model.

## What *not* to do

- Don't `npm install` then `npm install -g pnpm` — corepack covers it.
- Don't ship `node_modules/` in the prod image. The point of multi-stage is that `prod` is `nginx:alpine` + `dist/` only.
- Don't omit SSE-friendly nginx settings if your app streams; a generic config will make the stream appear to hang because tokens are buffered.
- Don't bind to `localhost` in the dev CMD; Vite needs `--host 0.0.0.0` inside a container.
