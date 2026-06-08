# Database strategy — Django-equivalent, async edition

## Contents

- [Goal](#goal)
- [The lifecycle in detail](#the-lifecycle-in-detail)
- [Why not pytest-postgresql?](#why-not-pytest-postgresql)
- [Why not testcontainers-python?](#why-not-testcontainers-python)
- [Why transactional rollback (and not TRUNCATE)?](#why-transactional-rollback-and-not-truncate)
- [Escape hatch: when a test really needs to commit](#escape-hatch-when-a-test-really-needs-to-commit)
- [Parallelism (pytest-xdist)](#parallelism-pytest-xdist)
- [When the schema changes](#when-the-schema-changes)
- [Common failure modes](#common-failure-modes)

## Goal

Match the ergonomic Django gives you out of the box:

1. `pytest` — and the suite runs.
2. No manual setup.
3. No leakage between tests.
4. Fast enough that nobody dreads running them.

Achieved with three moving parts:

| Concern | Mechanism |
|---|---|
| Where the DB comes from | Session fixture creates `app_test` from your schema bootstrap SQL; drops at session end |
| How tests stay isolated | Per-test `BEGIN ... ROLLBACK` on a single pinned connection |
| How the app and the test see the same data | The app's pool dependency is overridden to yield that pinned connection |

## The lifecycle in detail

### Session start

```text
1. Connect to the `postgres` admin DB using the same credentials as DATABASE_URL.
2. If `app_test` exists and KEEPDB != 1, terminate other sessions and DROP it.
3. CREATE DATABASE app_test.
4. Connect to app_test and apply the schema bootstrap SQL (your init.sql).
5. Open an asyncpg pool against app_test (min_size=1, max_size=2).
```

`KEEPDB=1` skips steps 2-4 if the DB already exists. This is the same escape
hatch Django offers via `--keepdb`. Use it when you're rerunning one test in
a tight loop and the schema hasn't changed. Skip it (or just unset it) after
pulling main or editing the schema SQL.

### Per test

```text
1. Acquire one connection from the pool.
2. tx = conn.transaction(); await tx.start()
3. Override the app's get_pool dependency to a wrapper that always
   yields THIS connection (see `_SingleConnPool` in conftest).
4. Yield the connection to the test as `db_conn`.
5. After the test: tx.rollback(); release the connection.
```

The override in step 3 is the load-bearing trick: without it, the app would
acquire a *different* connection from the pool, and the test's in-flight
inserts would be invisible to the endpoint. With it, app and test share one
transaction; everything the test sets up is readable by the endpoint, and
everything the endpoint writes vanishes when the test ends.

### Session end

```text
1. Close the pool.
2. If KEEPDB != 1: connect to admin, terminate sessions, DROP DATABASE.
```

Test runs leave no trace. Re-running is idempotent.

## Why not pytest-postgresql?

`pytest-postgresql` does spin up an ephemeral cluster, but:

- It's psycopg-oriented; using it with asyncpg means writing a thin adapter
  anyway.
- It manages a separate cluster on a random port — slow startup, fights with
  the dev cluster if the dev one isn't there.
- You probably already have a local Postgres via `docker-compose`. Using the
  same one for tests means CI matches dev one-for-one.

The DIY approach above is ~80 lines of `conftest.py` and gives you exactly
the ergonomic you want. Not worth a dependency.

## Why not testcontainers-python?

Same reason — it's heavier than the DIY recipe, slower on cold start, and
you already have a Postgres container running. If a project later wants
per-test container isolation (e.g. testing migrations themselves), it's
worth revisiting.

## Why transactional rollback (and not TRUNCATE)?

| Property | Transaction rollback | TRUNCATE between tests |
|---|---|---|
| Speed | Faster — no DDL, no FK cascade | Slower; TRUNCATE is per-table |
| Test sees its own writes | Yes (inside the same tx) | Yes |
| App sees the test's writes | Only with the pool override | Yes (test commits) |
| Tests can assert post-commit behaviour (triggers, defaults) | Yes — the transaction sees all of it | Yes |
| Tests can verify *commit boundaries* (e.g. retry on serialization failure) | **No** — there's no commit to observe | Yes |
| Connection pressure | One pinned connection per test | Pool unused; fewer surprises |

The verdict: rollback is the right default. The single case it doesn't cover
— verifying behaviour at the commit boundary — is rare enough that it
deserves an explicit escape hatch (below) rather than slowing down every
test.

## Escape hatch: when a test really needs to commit

Some tests want to verify what happens *after* a transaction commits — e.g.
an `ON UPDATE` trigger fires correctly, or the application issues
`LISTEN/NOTIFY`. These tests can't use `db_conn` because that connection is
held inside the rollback transaction.

For those, write a fixture that gives the test a fresh connection and takes
responsibility for cleanup:

```python
@pytest_asyncio.fixture
async def committed_db(db_pool):
    async with db_pool.acquire() as conn:
        try:
            yield conn
        finally:
            # Test wrote real data — clean up explicitly.
            await conn.execute(
                "TRUNCATE notes, items, appointments RESTART IDENTITY CASCADE"
            )
```

Mark these tests so the rest of the suite knows they're heavier:

```python
@pytest.mark.slow
async def test_item_trigger_updates_last_active_at(committed_db):
    ...
```

Don't reach for this lightly. If a test seems to need it but actually just
wants to "see the row from another session", you probably want the pool
override instead.

## Parallelism (pytest-xdist)

`pytest -n auto` runs tests in worker subprocesses. They each need their own
test DB or they'll fight for advisory locks and block each other.

The fix: include the worker id in the test DB name.

```python
# In conftest.py — replace the static name:
worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
_TEST_DB_NAME = os.environ.get("TEST_DB_NAME", f"app_test_{worker_id}")
```

Each worker creates and drops its own DB. The session is per-worker, so the
lifecycle stays clean. CI runs `pytest -n auto` for the full suite; dev
usually runs single-process for clearer failure output.

## When the schema changes

Today the schema is a single bootstrap SQL file (your `init.sql`). When a
migration tool like Alembic arrives, swap step 4 of the session-start
lifecycle from "apply init.sql" to "run `alembic upgrade head`". Everything
else — drop, recreate, override — stays the same. The decoupling is
intentional.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `database "app_test" is being accessed by other users` | A previous run left a session open; `KEEPDB=1` was set last time | The fixture's `pg_terminate_backend` call should handle it; if it persists, drop it manually once: `dropdb app_test` |
| `cannot drop the currently open database` | The pool from the previous run is still alive | Don't run `pytest` twice in the same process; let the session fixture close cleanly |
| `relation "items" does not exist` | The schema SQL didn't apply | Check your init.sql runs cleanly against an empty DB; re-run with `KEEPDB=0` |
| Test inserts a row, the endpoint's GET returns 404 | The pool override isn't in place; app and test are on different connections | Use the `client` fixture, not a hand-rolled `AsyncClient`. The override is set inside the `app` fixture which `client` depends on. |
| `another operation is in progress` | The test ran two coroutines on the same pinned connection concurrently (rare) | Don't use `asyncio.gather` over `db_conn`; serial calls only inside one test |
