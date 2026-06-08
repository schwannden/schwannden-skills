# Docker Compose for local dev + CI parity

## Table of contents
- [Two-file pattern: base + override](#two-file-pattern-base--override)
- [Base file](#base-file-infradocker-composeyml)
- [Override file](#override-file-infradocker-composeoverrideyml)
- [The `.env` file](#the-env-file)
- [Healthcheck dependencies](#healthcheck-dependencies)
- [Profiles for optional services](#profiles-for-optional-services)
- [Verifying compose locally](#verifying-compose-locally)
- [What *not* to do](#what-not-to-do)

Compose is for local development and local CI parity only. Production never sees
compose — a managed runtime (e.g. Cloud Run) + managed Postgres take over there.
The job of compose is to:

1. Boot the full stack (`db`, `api`, optionally `web`) with one command
2. Wait for `db` to be healthy before starting `api` (asyncpg is unforgiving on cold start)
3. Hot-reload `api`/`web` when source changes
4. Surface the same env-var contract production uses, so deploy-time surprises don't happen

## Two-file pattern: base + override

- `infra/docker-compose.yml` — the **base**. Targets `prod` builds. Used as-is for "runs like prod" parity testing.
- `infra/docker-compose.override.yml` — the **override**. Auto-merged on `docker compose up`. Switches `api`/`web` to their `dev` targets, mounts source for HMR, and overrides `command` to run with `--reload`.

`docker compose up` reads both. `docker compose -f infra/docker-compose.yml up` (with `-f` only) skips the override and runs prod targets. One command for everyday dev, an opt-in escape hatch for parity testing.

## Base file: `infra/docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
      - dbdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d postgres"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s

  api:
    build:
      context: ..
      dockerfile: infra/api.Dockerfile
      target: prod
    environment:
      DATABASE_URL: postgres://postgres:postgres@db:5432/postgres
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY in infra/.env or your shell}
      PORT: "8000"
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    restart: unless-stopped

volumes:
  dbdata:
```

**Things worth noticing:**

- `context: ..` — build context is the repo root. COPY paths in the Dockerfile are relative to that. Without this the api Dockerfile can't see `apps/api/`.
- `${ANTHROPIC_API_KEY:?...}` — compose interpolation with `:?`. If unset or empty, compose refuses to start with a clear error. Better than letting the api crash at first request.
- `condition: service_healthy` — depends on `db` advertising a `healthcheck`. Without it, `service_started` is the strictest you get, and asyncpg will sometimes fire connection attempts before Postgres is ready.
- `restart: unless-stopped` — compose restarts crashed containers but stops trying when you `docker compose down`.

(A `web` service follows the same shape; see `assets/docker-compose.yml`. Web is optional.)

## Override file: `infra/docker-compose.override.yml`

```yaml
services:
  api:
    build:
      target: dev
    volumes:
      - ../apps/api/src:/app/src
      - ../apps/api/tests:/app/tests
    command:
      - uv
      - run
      - uvicorn
      - api.main:app
      - --host=0.0.0.0
      - --port=8000
      - --reload
      - --reload-dir=/app/src
    environment:
      LOG_LEVEL: debug

  web:
    build:
      target: dev
    volumes:
      - ../apps/web:/app
      - /app/node_modules     # anonymous volume preserves the in-image install
    command: ["pnpm", "dev", "--host=0.0.0.0", "--port=5173"]
    ports: !override
      - "5173:5173"           # Vite dev server, NOT nginx; replace the base mapping
```

**The key tricks:**

1. **Anonymous volume on `/app/node_modules`** — without it, the bind mount of `apps/web` overlays the host's (possibly empty or wrong-architecture) node_modules onto the container, breaking imports. The anonymous volume preserves what the image installed.
2. **`!override` on ports** — base maps `5173:80` (nginx). Dev maps `5173:5173` (Vite). Compose merges port lists by default, producing a host-port collision; `!override` (Compose v2.24+) replaces the base list.

## The `.env` file

Compose reads `.env` from the **same directory as the compose file** (i.e. `infra/.env`), not the repo root. Add `.env` and `.env.local` to `.gitignore`. Commit only `infra/.env.example` with placeholder values. In production the same env var is set by your deploy step from a secret store — same name, different source. That's the point.

## Healthcheck dependencies

```yaml
depends_on:
  db:
    condition: service_healthy
```

Three values matter for `condition`:
- `service_started` — start order only; doesn't wait for readiness. Default; mostly useless.
- `service_healthy` — waits until the dependency's healthcheck passes. **Use this for db.**
- `service_completed_successfully` — waits until the dependency exits 0. Use for one-shot init containers (e.g. a migrations container running `alembic upgrade head` then exiting).

If you add a migration tool later, model it as a separate service that depends on `db: service_healthy` and is itself depended on by `api` with `service_completed_successfully`.

## Profiles for optional services

```yaml
services:
  pgadmin:
    image: dpage/pgadmin4
    profiles: ["debug"]
    ports: ["5050:80"]
```

`docker compose --profile debug up` includes pgadmin; `docker compose up` without the flag does not.

## Verifying compose locally

```bash
# Validate config (catches typos before runtime)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml config

# Boot and wait until everything reports healthy
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml up --wait

# Single service rebuild + restart (after a Dockerfile change)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml up --build api

# Run tests in the api container's test target (one-shot)
docker compose -f infra/docker-compose.yml run --rm --build \
  --entrypoint="" api uv run pytest -v
```

`up --wait` is the linchpin for CI scripts: it exits non-zero if any service fails to become healthy within the healthcheck's `start_period × retries` budget. Pair with `down --volumes` for clean-slate runs.

## What *not* to do

- Don't put production secrets in `.env`. `.env` is for local dev placeholders. Real keys live in a secret store.
- Don't bind-mount the api's `.venv/` from host. The host venv has the wrong architecture (e.g. macOS/arm64) for the container (linux/amd64). Let the image's venv stay isolated.
- Don't omit the healthcheck on `db`. It's the difference between "works on my machine" and intermittent CI flakes from connection-storm races.
- Don't use `version: "3.8"` at the top — obsolete in modern compose and produces a warning. The current spec has no required `version` key.
- Don't use `links:`. Compose creates a default network where every service resolves the others by service name; links are deprecated.
