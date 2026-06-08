# syntax=docker/dockerfile:1
#
# Multi-target Dockerfile for a FastAPI + uv api service.
# Build context: REPO ROOT (so this file can see apps/api/ and infra/).
#
# Targets:
#   builder  — installs prod deps from uv.lock, then installs project. Intermediate.
#   test     — adds dev deps; CMD runs pytest. Used by CI and `docker build --target test`.
#   dev      — adds dev deps; CMD runs uvicorn --reload. Used by docker compose override.
#   prod     — fresh slim base, non-root, healthcheck. Used by docker compose base + deploy.
#
# Usage:
#   docker buildx build -f infra/api.Dockerfile --target prod -t api:latest ..
#   docker buildx build -f infra/api.Dockerfile --target test -t api:test ..

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.5

# ---------------- uv binary stage ----------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------------- shared base -------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

# ---------------- builder: prod deps + project ----------------
FROM base AS builder
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
# If pyproject sets `readme = "README.md"`, the project install (next RUN) needs
# the file present, or it fails with "OSError: Readme file does not exist".
# Uncomment if your pyproject references a readme:
# COPY apps/api/README.md ./README.md
COPY apps/api/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---------------- test: dev deps + tests ----------------
FROM builder AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
COPY apps/api/tests ./tests
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src
CMD ["uv", "run", "pytest", "-v"]

# ---------------- dev: same deps as test, uvicorn --reload ----------------
FROM builder AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/src"]

# ---------------- prod: fresh slim base, non-root ----------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS prod
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

RUN useradd --system --uid 1001 --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src   /app/src

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,sys,urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/health',timeout=3).status==200 else 1)"

# sh -c expands ${PORT}; exec replaces shell so uvicorn becomes PID 1 and receives SIGTERM directly.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
