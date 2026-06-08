---
name: dockerizing-fastapi-uv
description: Use when authoring or editing Dockerfiles, docker-compose files, or container CI/CD for a Python 3.12 + FastAPI service managed with uv — including "containerize the api", "set up a local dev stack", "build the image for Cloud Run", "speed up Docker builds", "run as non-root", "add a healthcheck", or "wire up GitHub Actions to build/push/deploy". Produces multi-stage Dockerfiles (named builder/test/dev/prod targets) with BuildKit cache mounts for uv, dependency-before-code layering, non-root users, 0.0.0.0/PORT binding, exec-form CMD for SIGTERM, two-layer healthchecks, hot-reload compose overrides, and GitHub Actions that deploy to Google Cloud Run via Workload Identity Federation (one documented example deploy target; the Dockerfile/compose patterns are provider-agnostic). Keywords: Docker, Dockerfile, docker-compose, multi-stage, uv, FastAPI, BuildKit cache, non-root, Cloud Run, GitHub Actions, Workload Identity Federation, healthcheck, hot reload.
---

# Dockerizing a FastAPI + uv service

This skill packages a battle-tested way to containerize a Python 3.12 + FastAPI
service whose dependencies are managed by [uv](https://docs.astral.sh/uv/). The
core artifact is a **multi-stage Dockerfile** that serves local development, CI,
and production from one file via named targets. The patterns are
provider-agnostic; Google Cloud Run appears throughout as a fully worked
**example** deploy target, clearly labeled as one option.

The templates under `assets/` are **drop-in starting points** — copy them and
adapt the paths. The files under `references/` are **deep-dive reading** —
consult the one that matches your task. Cross-reference the sibling skills
`writing-fastapi-apis`, `testing-async-fastapi`, and `building-llm-agent-loops`
for the application code, and the built-in `uv` skill for dependency management.

## Example stack and layout

This skill assumes a representative monorepo. Adapt the paths to your project.

| Concern | Example |
|---|---|
| Stack | Python 3.12 + FastAPI + **uv** + asyncpg |
| DB | Postgres 16 (`init.sql` mounted; no ORM) |
| Frontend (optional) | React 18 + Vite + Tailwind SPA |
| Repo layout | `apps/api/` (Python), `apps/web/` (Node), `infra/` (Dockerfiles + compose). Build context for the Dockerfiles is the **repo root**, not `infra/`. |
| Local | `docker compose up` boots `db`, `api`, (`web`); `api`/`web` hot-reload on source change |
| Example prod | Cloud Run for `api`, managed Postgres for `db`, a secret store for the API key, a container registry for images |

The api container is the load-bearing one. The web container is included only as
an illustration of multi-language monorepo builds; treat it as optional.

## The three concerns one Dockerfile serves

The same Dockerfile does three jobs without forking, via **multi-stage targets**:

1. **Local development.** `docker compose up` → services hot-reload via
   bind-mounted source. Target: `dev`. Postgres advertises a healthcheck and
   `api` waits for `service_healthy` (otherwise asyncpg connect-storms on cold boot).
2. **CI / pytest in a container.** `docker build --target test` produces an image
   that runs the test suite against the same lockfile as prod — no drift between
   "passes on my laptop" and "passes in CI".
3. **CI/CD → a deploy target.** PR builds use the `test` target. Pushes to the
   default branch build the `prod` target, push to a registry, and deploy. The
   example deploy uses GitHub Actions → Cloud Run via **Workload Identity
   Federation** (no JSON keys).

## Decision tree

| What you're doing | Read | Start from |
|---|---|---|
| Authoring/editing the api Dockerfile | `references/dockerfile-api.md` | `assets/api.Dockerfile` |
| Authoring/editing a web (Node) Dockerfile | `references/dockerfile-web.md` | `assets/web.Dockerfile` |
| Authoring/editing compose files | `references/compose-patterns.md` | `assets/docker-compose.yml` + `assets/docker-compose.override.yml` |
| GitHub Actions that build/test/deploy | `references/github-actions.md` | `assets/github/ci.yml`, `assets/github/deploy.yml` |
| Cloud Run, managed Postgres, secret wiring (example target) | `references/cloud-run.md` | (commands inline in `deploy.yml`) |
| Healthchecks, logging, image hardening, `.dockerignore` | `references/operations.md` | `assets/.dockerignore` |

If a task spans rows (e.g. "set up the whole local stack"), read
`references/dockerfile-api.md` and `references/compose-patterns.md` together — the
compose targets and Dockerfile stages are designed as one system.

## Core principles (the *why* matters)

These are the load-bearing decisions. Every template encodes them; deviate only knowingly.

1. **Multi-stage with named targets** (`builder`, `test`, `dev`, `prod`). One
   Dockerfile drives every concern. Switching `target:` in compose or
   `build-push-action` is the difference between local dev, CI, and production —
   not three files that drift.

2. **BuildKit cache mounts** for uv:
   `RUN --mount=type=cache,target=/root/.cache/uv uv sync ...`. The cache
   survives between builds without entering the layer. First build is ~2 minutes;
   rebuilds are <15s when only application code changes. Requires the
   `# syntax=docker/dockerfile:1` pragma at the top of the file.

3. **Layer order is dependency → code, never the reverse.** Copy
   `pyproject.toml` + `uv.lock` first, run `uv sync --no-install-project --no-dev`,
   *then* copy source. Application changes don't bust the dependency cache. This
   is the single biggest factor in rebuild speed.

4. **Non-root user with explicit UID** in the prod stage
   (`useradd --system --uid 1001 ... appuser` → `USER appuser`). Many sandboxed
   runtimes (including Cloud Run) run non-root; matching that locally surfaces
   permission bugs during dev, not at deploy time.

5. **`PORT` env var, bind to `0.0.0.0`.** Cloud Run (and many platforms) inject
   `PORT`; the container is unreachable if you bind to `localhost`. Use
   `${PORT:-8000}` in the CMD so the local default is 8000 but the platform can
   override. Listening on `0.0.0.0` is non-negotiable.

6. **Exec-form CMD with proper signal handling.**
   `CMD ["sh", "-c", "exec uvicorn ... --port ${PORT:-8000}"]` — the `exec`
   matters. Shell-form `CMD uvicorn ...` makes `sh` PID 1, which swallows SIGTERM.
   Platforms give a grace window for shutdown; if the process never receives
   SIGTERM, in-flight requests (e.g. SSE streams) get hard-killed.

7. **Healthchecks at two layers.** Postgres advertises a `pg_isready` healthcheck
   so `api`'s `depends_on: { db: { condition: service_healthy } }` actually waits.
   The api advertises a `HEALTHCHECK` that hits `/health`, and the FastAPI app
   must expose that route. A platform's startup probe can use the same endpoint.

8. **Secrets never in the image.** The API key is read from the environment at
   startup. Locally it comes from a `.env` file referenced by compose
   (`${ANTHROPIC_API_KEY:?set in .env}`). In production a secret store injects it
   at deploy time. The Dockerfile must never `ARG` or `ENV` it — those bake values
   into image layers visible to anyone who pulls the image.

9. **Pin base images to a specific tag (and digest in prod).**
   `python:3.12-slim-bookworm`, not `python:3.12` (1GB+) and not
   `python:3.12-alpine` (musl libc breaks prebuilt wheels for asyncpg,
   cryptography). For prod, pin by digest (`@sha256:...`) when you cut a release.

10. **Build context is the repo root, not `infra/`.** Compose and CI both pass
    `context: ..` (or `.` from root). The Dockerfile then references
    `apps/api/pyproject.toml`. One Dockerfile sees both the source tree and the
    lockfile without symlinks or rearranging the repo.

## Anti-patterns

| Don't | Why |
|---|---|
| Single-stage Dockerfile with dev tools and source mixed | Bloats image (~1GB), ships compilers to prod, slows pulls on every cold start |
| `USER root` (or no `USER` directive) | Loses least-privilege; a compromised container can write anywhere in its filesystem |
| Bake the API key via `ARG`/`ENV` | The value is recoverable from image layers forever — even after you "fix" it. Rotate the key if this happens. |
| `image: python:3.12` (no tag pin) or `:latest` | Builds become non-reproducible; a base-image push silently changes your runtime |
| Mount source into the prod image at runtime | Defeats the immutable image; compose is the right place for bind mounts (dev only) |
| Bind to `127.0.0.1` or omit `--host 0.0.0.0` | Container unreachable from outside; first symptom is `connection refused` |
| Shell-form `CMD uvicorn ...` | Breaks SIGTERM propagation; in-flight requests get killed on rollover |
| Skip `.dockerignore` | Ships `.git/`, `.venv/`, `node_modules/` to the daemon — slow builds and accidental secret leaks |
| Service-account JSON keys in CI secrets | Long-lived credentials; if leaked, project-wide access. Use Workload Identity Federation — short-lived, scoped, nothing to leak. |

## Verification checklist

After Docker changes, run these (most need no cloud access). If you can't run a
check, say so — don't claim verification you didn't do.

```bash
# Build the prod image and confirm it boots as non-root.
docker buildx build -f infra/api.Dockerfile --target prod -t api:check ..
docker run --rm api:check whoami         # → appuser, not root

# Compose health: --wait blocks until all services are healthy
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml up --wait
curl -fsS localhost:8000/health          # → 200

# Test stage runs pytest in the same image lineage as prod
docker buildx build -f infra/api.Dockerfile --target test -t api:test ..
docker run --rm api:test                 # pytest exits 0

# Lint the templates
hadolint infra/api.Dockerfile
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml config >/dev/null
```
