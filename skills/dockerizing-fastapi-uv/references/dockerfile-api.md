# `infra/api.Dockerfile` — FastAPI + uv

## Table of contents
- [The four targets](#the-four-targets)
- [Reference layout (annotated)](#reference-layout-annotated)
- [Common edits](#common-edits)
- [What *not* to do](#what-not-to-do)

This file is a **multi-target** Dockerfile. One file, named stages, each serving a different concern. The stages share layers up to the point they diverge, so total disk and build time stay small. The drop-in template lives at `assets/api.Dockerfile`.

## The four targets

| Target | Built when | Contains | CMD |
|---|---|---|---|
| `builder` | always (intermediate) | venv with prod deps only | — (intermediate) |
| `test` | CI / PR builds | venv with dev deps + test source | `uv run pytest -v` |
| `dev` | `docker compose up` (override) | venv with dev deps + reload | `uvicorn ... --reload` |
| `prod` | `docker compose up` (base), CI push to default branch | minimal: venv + src, non-root | `exec uvicorn ... --port ${PORT:-8000}` |

`docker buildx build --target <name>` selects the stage. Compose chooses via `build.target:`. CI chooses via `build-push-action.target:`.

## Reference layout (annotated)

The stages, in order, look like this — each block annotated with *why*.

### Stage 0: pull `uv` once, parameterize Python version

```dockerfile
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.5

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
```

- `# syntax=docker/dockerfile:1` is required to enable BuildKit cache mounts. Without it, `RUN --mount=type=cache` is a syntax error.
- We pull the **upstream uv binary image** as a stage. This is faster and more reproducible than `pip install uv` or `curl | sh` — both add a network round trip and depend on transient endpoints.
- `ARG`s with defaults let CI override (`--build-arg PYTHON_VERSION=3.13`) without editing the file.

### Stage 1: `base` — shared environment

```dockerfile
FROM python:${PYTHON_VERSION}-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
```

- **Why slim-bookworm, not alpine.** asyncpg, cryptography, and most data-science wheels are built against glibc; alpine's musl libc forces source compilation, which inflates the builder image and slows builds 5-10×. slim-bookworm is ~80MB and pulls every wheel.
- `PYTHONUNBUFFERED=1` makes stdout flush immediately — log collectors capture lines in real time instead of buffering until the process exits.
- `PYTHONDONTWRITEBYTECODE=1` keeps `.pyc` files out of the source tree.
- `UV_LINK_MODE=copy` is required when the cache mount is on a different filesystem from `/app/.venv`; without it, uv may fail with hardlink errors on overlay filesystems.
- `UV_COMPILE_BYTECODE=1` precompiles `.pyc` files at install time. Trades ~5s of build time for ~200ms faster cold-starts — worth it.

### Stage 2: `builder` — install deps, then install project

```dockerfile
FROM base AS builder
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
COPY apps/api/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
```

- **Two-step sync is the cache trick.** Step 1 installs only third-party deps (the slow part) using just the lockfile. Step 2 installs the project itself (fast). When you edit `apps/api/src/...`, only step 2 reruns. When you change a dependency, step 1 reruns but the cache mount keeps wheels around so the network is barely touched.
- `--locked` enforces that `uv.lock` matches `pyproject.toml` — fails the build if someone edited one without the other.
- `--no-dev` excludes dev-group dependencies (pytest, ruff). The prod image stays lean.
- The cache mount target `/root/.cache/uv` is uv's default location. The cache lives in BuildKit's cache backend — never in the image layer.
- If `pyproject.toml` sets `readme = "README.md"`, also `COPY apps/api/README.md ./README.md` before the project-install step, or the build fails with `OSError: Readme file does not exist`.

### Stage 3: `test` — re-sync with dev deps

```dockerfile
FROM builder AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked  # includes dev deps
COPY apps/api/tests ./tests
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src
CMD ["uv", "run", "pytest", "-v"]
```

- Inherits everything from `builder`, then re-runs `uv sync` *without* `--no-dev` to add pytest/etc.
- `tests/` is copied last because it's the layer most likely to change between commits.
- Used by `assets/github/ci.yml` and by local `docker buildx build --target test ...`.

### Stage 4: `dev` — same deps as test, but starts uvicorn with reload

```dockerfile
FROM builder AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/src"]
```

- Compose's override file binds `apps/api/src` as a volume on top of `/app/src`, so uvicorn's reloader sees host file changes.
- `--reload-dir /app/src` is explicit: by default `--reload` watches the working directory, which under bind mounts can include things you don't want (like `__pycache__/`).

### Stage 5: `prod` — fresh slim base, no build tools

```dockerfile
FROM python:${PYTHON_VERSION}-slim-bookworm AS prod
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

# Non-root with explicit UID; matches common sandbox conventions.
RUN useradd --system --uid 1001 --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src   /app/src

USER appuser
EXPOSE 8000

# Healthcheck uses Python stdlib so there's no curl/wget to ship.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,sys,urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/health',timeout=3).status==200 else 1)"

# exec ensures uvicorn is PID 1 so SIGTERM reaches it directly.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

- **Why a fresh `FROM python:...` here, not `FROM builder`.** The `prod` image must not contain `uv`, `pip`, build caches, or anything else not strictly needed at runtime. Multi-stage `COPY --from=builder` cherry-picks just `.venv` and `src/`.
- **Non-root with UID 1001** — many sandboxed runtimes run containers under a non-root identity by default. Matching that locally surfaces filesystem-permission issues during dev. The explicit UID makes ownership predictable in CI logs.
- **Healthcheck is in Python stdlib** — no `curl` in the prod image. curl is a CVE surface; shipping it in production is a small but real liability.
- **`sh -c` + `exec`** — `sh -c` is needed to expand `${PORT:-8000}`. The `exec` *replaces* the shell with uvicorn so uvicorn becomes PID 1 and receives SIGTERM directly. Without `exec`, sh stays PID 1, eats SIGTERM, and uvicorn is killed by SIGKILL after the grace period.

## Common edits

- **Add a prod runtime dep** (e.g. `httpx`): `cd apps/api && uv add httpx`. Rebuild — only `builder`'s second `uv sync` reruns. No Dockerfile change.
- **Add a dev dep** (e.g. `ruff`): `cd apps/api && uv add --dev ruff`. Rebuild — `test` and `dev` stages rerun their `uv sync`. `prod` is unaffected.
- **Bump Python**: `--build-arg PYTHON_VERSION=3.13`, or change the `ARG` default. uv warns if `requires-python` in `pyproject.toml` disagrees.
- **Pin a digest for prod**: replace `python:3.12-slim-bookworm` in the `prod` stage with `python:3.12-slim-bookworm@sha256:...`. Rotate quarterly or when CVE notices land.

## What *not* to do

- Don't move `COPY apps/api/src` above the dependency `uv sync`. That undoes the layer-cache win — every code change reruns the slow dep install.
- Don't `RUN apt-get install` build tools in the `prod` stage. If a pure-Python wheel doesn't exist, install in `builder` only; `prod` gets the compiled artifact via `.venv`.
- Don't `COPY . .` from the repo root. The build context is wide; copying everything bloats the image and busts cache on every commit. Be specific.
- Don't use `RUN curl ... | sh` for uv. The `FROM ghcr.io/astral-sh/uv` stage pins by version and avoids network non-determinism.
