# Cloud Run as an example deploy target

## Table of contents
- [What Cloud Run requires of a container](#what-cloud-run-requires-of-a-container)
- [Anatomy of a `gcloud run deploy`](#anatomy-of-a-gcloud-run-deploy)
- [Health probes](#health-probes)
- [Statelessness & graceful shutdown](#statelessness--graceful-shutdown)
- [Logs and metrics](#logs-and-metrics)
- [Common operations](#common-operations)
- [What *not* to do](#what-not-to-do)

> This file documents **one example deploy target**: Google Cloud Run + managed
> Postgres + a secret store + a container registry. The Dockerfile and compose
> patterns in this skill are provider-agnostic — the same `prod` image runs on
> any platform that injects `PORT`, runs non-root, and sends SIGTERM. Use this as
> a worked reference, not a mandate. The requirements below (listen on `$PORT`,
> bind `0.0.0.0`, be stateless, handle SIGTERM) generalize to most serverless
> container runtimes.

## What Cloud Run requires of a container

| Requirement | How we satisfy it |
|---|---|
| Listens on `$PORT` (Cloud Run injects whatever it picks) | `CMD ["sh", "-c", "exec uvicorn ... --port ${PORT:-8000}"]` |
| Binds to all interfaces (`0.0.0.0`), not loopback | uvicorn `--host 0.0.0.0` |
| Stateless — no on-disk state survives between requests | Postgres for everything; no temp files, no local SQLite |
| Cold-start ready quickly | Slim base + bytecode-compiled venv → ~1.5s startup |
| Handles SIGTERM gracefully (grace window before SIGKILL) | `exec` in CMD; uvicorn handles SIGTERM and finishes in-flight requests |
| One container per service (no sidecars) | db is managed Postgres, not a sidecar |
| Image in a supported registry | Push to `${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/api` |

## Anatomy of a `gcloud run deploy`

```bash
gcloud run deploy api \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/api:${SHA} \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  \
  --add-cloudsql-instances ${PROJECT_ID}:${REGION}:${SQL_INSTANCE} \
  --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest \
  --set-env-vars "DATABASE_URL=postgres:///postgres?host=/cloudsql/${PROJECT_ID}:${REGION}:${SQL_INSTANCE}" \
  \
  --service-account ${RUNTIME_SA_EMAIL} \
  --cpu 1 --memory 512Mi \
  --min-instances 0 --max-instances 10 \
  --concurrency 40 \
  --timeout 300 \
  --port 8000
```

### Image & region
- `--image` must point at a registry Cloud Run can pull (Artifact Registry, GCR for legacy). Pull time matters for cold starts — keep the image <300 MB.
- `--region` should match the managed-Postgres region for low-latency socket access.

### Managed Postgres connection (Unix socket)

```
--add-cloudsql-instances ${PROJECT_ID}:${REGION}:${SQL_INSTANCE}
DATABASE_URL=postgres:///postgres?host=/cloudsql/${PROJECT_ID}:${REGION}:${SQL_INSTANCE}
```

- `--add-cloudsql-instances` mounts a Unix socket inside the container at `/cloudsql/<connection-name>/` via a managed Cloud SQL Auth Proxy — no IP networking.
- `DATABASE_URL` uses the `host=/cloudsql/...` form, which asyncpg understands.
- The runtime service account needs `roles/cloudsql.client`.

### Secret store wiring

```
--set-secrets ANTHROPIC_API_KEY=anthropic-key:latest
```

- Secret named `anthropic-key` in Secret Manager. `:latest` reads the latest version at boot; pin a numeric version (`:3`) for tighter control.
- The runtime service account needs `roles/secretmanager.secretAccessor` (prefer narrow scope to the specific secret).
- Cloud Run injects the secret value as an env var at startup. Code reads `os.environ["ANTHROPIC_API_KEY"]` — same as locally.

### Resource sizing
- `--cpu 1 --memory 512Mi` — sensible default for an async FastAPI app that mostly awaits I/O.
- `--concurrency 40` — per-instance request concurrency. FastAPI is async; most time is spent awaiting upstream responses.
- `--min-instances 0` — scale to zero. Set `--min-instances 1` for warm capacity if latency is sensitive.
- `--max-instances 10` — caps fan-out. Pair with the asyncpg pool size (max ~5 per instance) so total connections stay under the DB tier's cap.

### Timeout
- `--timeout 300` (5 min) — request timeout. Streaming responses can be long; max is 3600 (60 min).

## Health probes

Cloud Run supports startup and liveness probes (TCP, HTTP, or gRPC):

```bash
gcloud run services update api \
  --region ${REGION} \
  --startup-probe httpGet.path=/health,httpGet.port=8000,timeout=2s,period=5s,initialDelay=0s,failureThreshold=10 \
  --liveness-probe httpGet.path=/health,httpGet.port=8000,timeout=2s,period=30s
```

The FastAPI app must expose `/health` (pure liveness, no deps) and optionally `/ready` (checks the DB). See `references/operations.md` for the liveness-vs-readiness split.

## Statelessness & graceful shutdown

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=5)
    app.state.pool = pool
    yield
    await pool.close()  # SIGTERM arrives, then a grace window before SIGKILL

app = FastAPI(lifespan=lifespan)
```

- Pool sized 1–5 per instance; with max_instances=10 that's at most 50 connections.
- `await pool.close()` in the lifespan teardown drains the pool gracefully when SIGTERM arrives.
- **No filesystem state.** Write logs to stdout; the platform's log collector captures them.

## Logs and metrics

Cloud Run auto-captures stdout/stderr. For filterable logs, emit JSON with a `severity` field — Cloud Logging recognizes it. See `references/operations.md` for a structured-logging helper.

## Common operations

```bash
# Tail prod logs
gcloud run services logs tail api --region ${REGION}

# Roll back to a specific revision
gcloud run services update-traffic api --region ${REGION} \
  --to-revisions=api-00042-abc=100

# List recent revisions
gcloud run revisions list --service api --region ${REGION} --limit 10

# Manual deploy without CI (uses Cloud Build; slower)
gcloud run deploy api --source . --region ${REGION}
```

## What *not* to do

- Don't bind to `localhost`. The container is unreachable to the load balancer; you'll see "Container failed to start" with uvicorn happily listening on 127.0.0.1.
- Don't read secrets at module import time. Read them in the lifespan handler or per request; module-level reads can race with secret injection.
- Don't write `.tmp/` or any on-disk file expecting persistence. `/tmp` is in-memory and ephemeral. Use Postgres or object storage.
- Don't add a sidecar for the SQL Auth Proxy manually. `--add-cloudsql-instances` runs it for you.
- Don't `--allow-unauthenticated` for an internal-only api. Use it only for genuinely public endpoints.
- Don't hardcode the deployed URL in the frontend. Route `/api/*` through your static host's rewrites so a URL change doesn't require a frontend redeploy.
