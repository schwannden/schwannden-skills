# Operations: healthchecks, logging, image hardening, .dockerignore

## Table of contents
- [.dockerignore](#dockerignore)
- [Healthchecks: liveness vs readiness](#healthchecks-liveness-vs-readiness)
- [Structured logging](#structured-logging)
- [Image hardening checklist](#image-hardening-checklist)
- [Image scanning](#image-scanning)
- [What *not* to do](#what-not-to-do)

This file groups the operational concerns that thread through every other reference. If you're adding observability, hardening an image, or wondering why builds are slow because the build context is huge, look here.

## .dockerignore

A missing or weak `.dockerignore` is the single most common reason builds are slow and accidentally leak secrets. The drop-in template at `assets/.dockerignore` is exhaustive; the reasoning:

```gitignore
# VCS
.git
.gitignore
.gitattributes

# Python
**/__pycache__/
**/*.pyc
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
**/.venv/
**/venv/
**/dist/
**/build/
**/*.egg-info/

# Node
**/node_modules/
**/.pnpm-store/
**/.vite/

# Editors / OS
.idea/
.vscode/
.DS_Store

# Env & secrets — NEVER ship these
.env
.env.*
!.env.example
**/.env
**/.env.*
!**/.env.example

# Local-only artifacts
**/.coverage
**/htmlcov/
**/*.log

# Docs and meta (not needed in image)
docs/
README.md
CHANGELOG.md
LICENSE
.github/

# Compose / infra meta (the Dockerfile is consumed during build, not shipped inside the image)
infra/docker-compose.yml
infra/docker-compose.override.yml
```

**Why every entry matters:**

- `.git/` can be 100s of MB on a mature repo. With it in the build context, every build sends the whole history to the daemon — slow and wasted.
- `.venv/` (or `node_modules/`) from host is the wrong architecture and would overwrite the venv the image just built. If it leaks into a layer, it bloats the image by 100–500 MB.
- `.env` is the secret-leak hazard. If a developer's local `.env` ends up in a `COPY . .` layer, the key is in the image forever — even after you "fix" it. The `!.env.example` exception lets the committed example file be copied if needed.

The Dockerfile templates `COPY` specific paths, which already limits the blast radius. `.dockerignore` is the second line of defense and the one that catches sloppy `COPY . .` usage.

## Healthchecks: liveness vs readiness

Two different questions:

| Probe | Question | What it checks | Failure action |
|---|---|---|---|
| Liveness | "Is the process alive?" | Pure: HTTP responds 200 | Restart container |
| Readiness | "Is it ready to handle traffic?" | Includes deps: DB reachable, etc. | Remove from load balancer (no restart) |

Mixing them is the classic mistake: if `/health` checks the DB and the DB hiccups, the platform *restarts* the container, which doesn't help and creates a thundering herd.

### FastAPI implementation

```python
@app.get("/health")
async def health():
    """Liveness: am I running?"""
    return {"status": "ok"}

@app.get("/ready")
async def ready():
    """Readiness: can I serve traffic right now?"""
    pool: asyncpg.Pool = app.state.pool
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as e:
        return JSONResponse({"status": "degraded", "error": str(e)}, status_code=503)
    return {"status": "ready"}
```

### Docker HEALTHCHECK

Use stdlib (no extra binary in the prod image):

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,sys,urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/health',timeout=3).status==200 else 1)"
```

`--start-period=10s` tells Docker not to count failures during the first 10s of startup — uvicorn's first request after boot can be slow.

## Structured logging

Most platforms auto-capture stdout. To get filterable, severity-aware logs, emit JSON:

```python
import json, logging, sys, time

logger = logging.getLogger("api")
logger.handlers.clear()
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def log_event(event: str, severity: str = "INFO", **fields):
    """Emit a single JSON line. Cloud Logging recognises 'severity'."""
    logger.info(json.dumps({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "severity": severity,
        "event": event,
        **fields,
    }))

# Usage:
log_event("request_completed", request_id=rid, latency_ms=890, status=200)
```

Cloud Logging filters like `severity>=WARNING` and `jsonPayload.event="request_completed"` work out of the box. Other log backends parse the JSON line equivalently.

## Image hardening checklist

Run through these before declaring an image "production ready":

- [ ] **Multi-stage** — prod image contains no compilers, build tools, or dev dependencies
- [ ] **Pinned base** — `python:3.12-slim-bookworm` (not `:3.12` or `:latest`); for releases, pin by digest
- [ ] **Non-root user** — `USER appuser` with explicit UID, set after all `COPY --chown=...` calls
- [ ] **No secrets in layers** — grep the Dockerfile for any `ARG.*KEY`, `ENV.*TOKEN`, `ENV.*SECRET`. None should be there.
- [ ] **`.dockerignore` covers `.env`** — `docker build --no-cache .` should not include any `.env*` files
- [ ] **Healthcheck present** — `HEALTHCHECK` directive in prod stage; uses stdlib, not curl
- [ ] **Exec-form CMD** — `CMD ["..."]` not `CMD ...` (or `sh -c "exec ..."` if shell expansion is needed)
- [ ] **EXPOSE matches reality** — `EXPOSE 8000` if uvicorn binds to 8000
- [ ] **No `apt-get install` in prod** — only in `builder`. `prod` does `COPY --from=builder` for the venv.
- [ ] **No `pip` / `uv` in prod** — they're only in `builder`. `prod` activates the venv via `PATH`.
- [ ] **`hadolint`** passes with no errors
- [ ] **Image size** — `docker image inspect <tag> --format='{{.Size}}'` under ~300MB for the api prod target

## Image scanning

Two free tools that run in CI:

```bash
# Trivy — vulnerability scanning
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image api:check

# Hadolint — Dockerfile linter
docker run --rm -i hadolint/hadolint:latest < infra/api.Dockerfile
```

## What *not* to do

- Don't add a separate health-check script shipped in the image just for the HEALTHCHECK directive. Inlining a stdlib one-liner keeps the image smaller.
- Don't `apt-get install -y curl` in prod just so HEALTHCHECK can use it. We have Python; use it.
- Don't run logs through a custom transport (Fluent Bit sidecar, log shipper) on a managed runtime. The platform captures stdout for free.
- Don't suppress hadolint warnings reflexively. `DL3008` (apt-get versions not pinned) is meaningful; suppress only after a deliberate, commented decision.
- Don't skip `.dockerignore`. "It's just a small repo" is the common excuse — then six months later the build context is 800MB because someone added a fixtures directory full of test data.
