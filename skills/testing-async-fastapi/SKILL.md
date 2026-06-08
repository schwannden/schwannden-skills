---
name: testing-async-fastapi
description: |
  Conventions for testing an async FastAPI + Postgres + LLM app: pytest with
  pytest-asyncio (asyncio_mode="auto"); httpx.AsyncClient with ASGITransport
  (not the legacy sync TestClient); a Django-style auto-created/dropped
  throwaway Postgres test database with per-test transactional rollback and
  KEEPDB=1; overriding the DB pool dependency so app and test share one
  in-flight connection; a unit/integration/e2e taxonomy; faking the LLM
  client at the SDK boundary via a dependency override (not over HTTP); and
  asserting on SSE event streams with a helper. Use when writing or reviewing
  async FastAPI tests; setting up pytest or pytest-asyncio; designing fixtures
  or a conftest; isolating database state or fixing rollback leakage; mocking
  an LLM / Anthropic client; asserting against SSE streaming including the
  terminal error event; wiring CI; or running xdist.
  Keywords: pytest, pytest-asyncio, httpx, ASGITransport, AsyncClient,
  transactional rollback, test database, conftest, mock LLM, SSE assertions,
  xdist.
---

# Testing an async FastAPI + Postgres + LLM app

Every commit that touches the API ships a test. Every test runs the same
way: `pytest`, no flags, no setup steps. A fresh checkout goes from
`git clone` to green dots in two commands. That ergonomic is
load-bearing — if running tests is friction, tests don't get written, and
the development loop slows to a crawl.

The shape of "easy to run" here is **Django-equivalent**: pytest creates a
throwaway `app_test` database from your schema bootstrap SQL, runs the
suite with per-test transactional rollback, and drops the database at the
end. You never see it, never clean it up. Set `KEEPDB=1` to keep it across
runs (Django's `--keepdb`) when iterating fast on one test.

This skill ships **drop-in scaffolding**. The first time it runs in a fresh
checkout, copy the templates from `assets/` into your test tree. After that,
every new test imports the same fixtures. The skill's job from then on is to
keep patterns consistent, refresh guidance against installed versions, and
prevent common drift (mocking the DB, faking the LLM over HTTP, hand-rolling
SSE assertions).

## When to invoke this skill

Trigger on any of:

- "Write a test for X", "add a regression for Y", "TDD this"
- Any new file under the test tree, or any modification to one
- "How do I test the SSE endpoint?", "how do I test a tool dispatch?"
- "Set up pytest", "bootstrap the test suite", "wire up CI tests"
- Adding `pytest`, `pytest-asyncio`, `httpx`, etc. to `[dev-dependencies]`
- "Mock the LLM", "fake the Claude / Anthropic client", "test without
  hitting the API"
- "Truncate the DB between tests", "tests are leaking state", "transaction
  not rolling back"
- A request mentioning "test plan", "verifiable", "smoke test",
  "integration test", "end-to-end test", "fixture"

If a request talks about correctness, regression prevention, or the
development loop, treat it as a trigger.

## First action: refresh against installed versions

The Python testing ecosystem moves. Before writing fixtures or helpers,
check the installed versions of the libraries you're about to use. Use the
**context7 MCP**:

```
mcp__context7__resolve-library-id  libraryName="FastAPI"   # or "pytest", "pytest-asyncio", "httpx"
mcp__context7__query-docs          libraryId="/<resolved-id>"
                                   query="<the exact thing you're doing>"
```

Good queries: "AsyncClient with ASGITransport for FastAPI app",
"pytest-asyncio fixture loop scope session", "asyncpg pool override in
FastAPI dependency_overrides". Bad queries: "pytest" or "FastAPI testing" —
too broad.

Skip context7 for things that aren't framework-specific: vanilla asyncpg
SQL, dataclass usage, Python's `unittest.mock`.

## Stack — recommended decisions

| Layer | Choice | Why |
|---|---|---|
| Test runner | **`pytest`** | De-facto standard; richest fixture and plugin ecosystem. |
| Async support | **`pytest-asyncio`** with `asyncio_mode = "auto"` | Removes `@pytest.mark.asyncio` boilerplate from every test; one fewer thing to forget. |
| HTTP client | **`httpx.AsyncClient(transport=ASGITransport(app=app))`** | The FastAPI-docs-recommended async test client. The legacy `TestClient` is sync-under-async and breaks subtly with `asyncpg`. |
| Database | **Real local Postgres** (e.g. a docker-compose `db` service) | Mocking SQL hides bugs; you already have a local DB; CI gets one too. |
| DB lifecycle | **Auto-create `app_test` from your schema SQL per session, drop on teardown** | Django-style. `KEEPDB=1` keeps it across runs for tight iteration. |
| Per-test isolation | **Transaction-rollback** with the app's pool overridden to yield the test connection | One transaction per test; rolled back at teardown; app and test share the same in-flight view. No truncation calls. |
| LLM mocking | **A fake client fixture** stubbing the LLM SDK at the boundary | Cheap, deterministic, no network. The real LLM is opt-in via `@pytest.mark.live_llm`. |
| SSE assertions | **`tests/_helpers/sse.py`** consumes `event:`/`data:` framing into a typed list | Hand-rolled SSE assertions get noisy fast. |
| Coverage | **`pytest-cov`** with terminal-missing report | Use as a guide for hot spots, not a gate. |
| Parallelism | **`pytest-xdist` (optional)** with `-n auto` for full-suite runs | Each worker gets its own test DB to avoid lock fights. |

> If you change a row, update it here in the same commit.

## The three test layers

Every test belongs in exactly one of these directories. The layer
determines what the test is allowed to touch and how fast it must run.

| Layer | Path | Touches | Runs in | Example |
|---|---|---|---|---|
| **Unit** | `tests/unit/` | Pure Python. No DB, no FastAPI app, no LLM. | <1 ms each | A pricing calculator, a Pydantic validator, a `redact()` helper. |
| **Integration** | `tests/integration/` | Real DB (rolled back), real FastAPI app, **fake** LLM. | <100 ms each | A `POST /appointments` end-to-end through the envelope handler. |
| **End-to-end** | `tests/e2e/` | Real DB, real app, fake LLM, **streaming SSE**. | <1 s each | A full `/chat` turn that includes a `book_appointment` tool call. |

Why three? So you can run the fast layer continuously during dev
(`pytest tests/unit -x`) and the slow layers only when you need them. The
unit layer is your TDD inner loop; integration and e2e gate the PR.

```
api/tests/                 # illustrative; mirror your own package layout
├── conftest.py            # all fixtures — copied from assets/conftest.py.tmpl
├── _helpers/
│   ├── __init__.py
│   ├── sse.py             # SSE stream consumer
│   ├── factories.py       # tiny seed factories
│   └── fake_llm.py        # fake LLM client (Anthropic SDK shape)
├── unit/
│   └── test_envelope.py
├── integration/
│   ├── test_health.py
│   └── test_appointment_endpoint.py
└── e2e/
    ├── test_chat_basic.py
    └── test_chat_book_appointment.py
```

Mirror the source tree where it makes sense, but don't be religious about
it — group by feature when that's clearer.

## Bootstrapping into a fresh project

If `tests/conftest.py` doesn't exist yet, **copy these templates** into
place before any test is written (adjust the destination to your package
layout):

```
assets/conftest.py.tmpl                  → tests/conftest.py
assets/_helpers/sse.py.tmpl              → tests/_helpers/sse.py
assets/_helpers/factories.py.tmpl        → tests/_helpers/factories.py
assets/_helpers/fake_llm.py.tmpl         → tests/_helpers/fake_llm.py
assets/example_unit_test.py.tmpl         → tests/unit/test_envelope.py
assets/example_integration_test.py.tmpl  → tests/integration/test_health.py
assets/example_e2e_test.py.tmpl          → tests/e2e/test_chat_basic.py
```

Add empty `__init__.py` files under `tests/`, `tests/_helpers/`,
`tests/unit/`, `tests/integration/`, `tests/e2e/` so pytest collects
cleanly without `rootdir` games.

Add dev dependencies per `assets/pyproject-deps.md` (read it). Drop the
pytest config block from `assets/pytest_config.md` into your
`pyproject.toml`.

### Minimal mode (no DB, no LLM yet)

The drop-in `conftest.py.tmpl` assumes the app already imports `asyncpg`
(for `get_pool`) and an LLM SDK (for `get_llm_client`). On a fresh checkout
that hasn't built those yet, the full template **fails at collection time**
with `ModuleNotFoundError`. Ship this minimal conftest instead and graduate
to the full template the moment the DB pool lands. The contract the tests
rely on — a `client` fixture yielding an `AsyncClient` — stays the same;
only the plumbing behind it changes.

```python
# tests/conftest.py — minimal mode
"""Minimal conftest. App + AsyncClient, no DB, no LLM.
Replace with assets/conftest.py.tmpl when the pool lands."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.main import app as fastapi_app


@pytest.fixture
def app() -> FastAPI:
    return fastapi_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
```

`tests/_helpers/sse.py` (the SSE consumer) **is** safe to ship from day one
— it has no DB or LLM dependency. Use it for a mock `/chat` endpoint's
contract test. The graduation trigger is unambiguous: the first PR that adds
`asyncpg` to `pyproject.toml` should also swap this file for
`assets/conftest.py.tmpl`, copy `_helpers/factories.py` and
`_helpers/fake_llm.py`, and ensure your schema bootstrap SQL exists.

## Writing a test (5 steps)

The full set of patterns lives in `references/example-tests.md`. The short
form for a typical feature:

1. **Pick the layer.** Pure logic → `unit/`. Anything that touches a route
   or the DB → `integration/`. Anything that asserts on the SSE stream →
   `e2e/`.
2. **Use the fixtures, don't roll your own.** The `client` fixture yields an
   `AsyncClient` already wired to the app with the test DB connection plumbed
   in. The `db_conn` fixture gives you a raw `asyncpg.Connection` inside the
   same transaction the app is using. The `fake_llm` fixture replaces the
   LLM client.
3. **Seed via factories, not raw SQL.** The factories in
   `_helpers/factories.py` know the schema and the FK shape, so a future
   column addition doesn't shower you with broken tests.
4. **Assert on the response envelope.** Every API response goes through your
   response envelope (see `writing-fastapi-apis`). Assert on `success`,
   `data`, and `error.code` — never on raw JSON shape that bypasses it.
5. **Don't skip the cleanup question.** If the test commits explicitly (rare
   — only when testing commit boundaries), it owes a TRUNCATE. Otherwise the
   rollback fixture handles it. See `references/db-strategy.md` § "Escape
   hatch".

## Faking the LLM — the boundary

The LLM client is reached via a single dependency in the application. Tests
override that dependency with a fake — they never mock at the HTTP layer.
Reason: an LLM SDK does its own streaming/state machine, and HTTP-level
mocks (`respx`, `httpx_mock`, `vcrpy`) have been a source of flaky tests for
every team that's tried them. Stubbing at the SDK boundary keeps the test
surface tiny.

The concrete example throughout this skill uses the Anthropic SDK
(`AsyncAnthropic`) — substitute whichever client your app uses; the boundary
pattern is identical.

```python
# The dependency the application defines
from anthropic import AsyncAnthropic

_llm = AsyncAnthropic()  # module-level singleton; reads its key from env

def get_llm_client() -> AsyncAnthropic:
    return _llm

# The test fixture overrides it
@pytest.fixture
def fake_llm(app):
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm_client, None)
```

The `FakeLLM` class is a tiny harness that lets a test program the next
response: `fake.expect_text("Hello")`,
`fake.expect_tool_use("book_appointment", input={...})`,
`fake.expect_pause_turn()`. Full pattern in
`references/llm-mocking.md`.

When you genuinely need a real LLM call (e.g. a nightly groundedness
regression on a tiny corpus), mark the test:

```python
@pytest.mark.live_llm
async def test_real_search_returns_citation(client, ...):
    ...
```

`live_llm` is registered as a marker in `pytest_config.md` and
**deselected by default** (`-m "not live_llm"`). CI opts in only on the
nightly job. Keep these tests rare; they're slow, costly, and flaky.

## SSE assertions

Once `/chat` starts streaming, you can no longer return an HTTP error — see
`writing-fastapi-apis`. Tests therefore need to consume the stream and
assert on parsed events, including the **terminal `event: error`** case.

Use the `read_sse_events()` helper:

```python
from tests._helpers.sse import read_sse_events

async def test_chat_streams_tokens(client, fake_llm):
    fake_llm.expect_text("hi there")

    async with client.stream("POST", "/chat", json={"message": "hello"}) as resp:
        events = await read_sse_events(resp)

    assert resp.status_code == 200
    assert [e.event for e in events][-1] == "end"
    assert "".join(e.data["text"] for e in events if e.event == "token") == "hi there"
```

Full event types and the error case in `references/sse-testing.md`.

## Common pitfalls (and how the skill prevents each)

| Pitfall | Symptom | Prevention |
|---|---|---|
| App and test see different DB connections | "Test inserted a row, the endpoint can't see it" | The `client` fixture overrides `get_pool` to wrap the test's pinned connection. Always use `client`, not a raw `AsyncClient`. |
| `loop_scope` mismatch | "Event loop is closed" mid-suite | `pytest-asyncio` config in `pytest_config.md`; the DB session fixtures set `loop_scope="session"` and everything else stays `function`. |
| Deprecated `TestClient` import | Sync-under-async deadlocks; `asyncpg` "another operation in progress" | Use `httpx.AsyncClient` with `ASGITransport`. The legacy `TestClient` is removed from the recommendations. |
| Mocking the DB | Mock drifts from prod schema; migrations break silently | Don't. Use the real local Postgres; the rollback fixture is fast enough. |
| Faking the LLM over HTTP | Brittle to SDK internals (streaming framing, retry logic) | Fake at the `get_llm_client` dependency boundary. |
| Hand-rolled SSE parsing | Off-by-one on the `data:` framing; tests pass on lucky timing | Use `read_sse_events()` from `_helpers/sse.py`. |
| Tests that depend on test order | Random failures with `pytest-xdist` | Keep tests independent; never `commit()` from a test. The rollback fixture is your friend. |
| Forgetting `__init__.py` | "Module not found" with `pytest-xdist` workers | Empty `__init__.py` in every test directory. The bootstrap step takes care of this. |

## CI integration (one-liner)

```yaml
# .github/workflows/test.yml — abbreviated
- run: docker compose up -d db
- run: uv run pytest -m "not live_llm"
```

The DB lifecycle fixture handles `CREATE DATABASE` / `DROP DATABASE` itself,
so CI doesn't need an extra setup step. A nightly job can add
`-m live_llm` against a separate LLM-key secret with a small budget.

For running parallel workers, sharding the DB across workers, and `KEEPDB=1`
semantics, see `references/db-strategy.md` § "Parallelism". For the local
`db` service that tests connect to, see `dockerizing-fastapi-uv`.

## Files in this skill

- `SKILL.md` — this file
- `assets/conftest.py.tmpl` — the canonical conftest with all fixtures
- `assets/_helpers/sse.py.tmpl` — SSE stream consumer
- `assets/_helpers/factories.py.tmpl` — seed factories
- `assets/_helpers/fake_llm.py.tmpl` — fake LLM client (Anthropic SDK shape)
- `assets/example_unit_test.py.tmpl` — minimal unit test
- `assets/example_integration_test.py.tmpl` — minimal integration test
- `assets/example_e2e_test.py.tmpl` — minimal SSE end-to-end test
- `assets/pyproject-deps.md` — `uv add --dev` commands
- `assets/pytest_config.md` — pytest config block for `pyproject.toml`
- `references/db-strategy.md` — full Django-equivalent DB lifecycle, rollback, escape hatch, parallelism
- `references/llm-mocking.md` — `FakeLLM` patterns including server-tool blocks and `pause_turn`
- `references/sse-testing.md` — SSE event types, terminal error case, full assertion examples
- `references/example-tests.md` — one worked example per layer

## Cross-skill notes

This skill is the **how**. The **what** lives elsewhere:

- For the route shell, error envelope, and PII rules the tests assert
  against — see `writing-fastapi-apis`.
- For the LLM loop's invariants (stable `tools[]`, prompt-cache placement,
  `pause_turn` handling) that tests exercise via `fake_llm` — see
  `building-llm-agent-loops`.
- For containers, docker-compose, and the local `db` service tests connect
  to — see `dockerizing-fastapi-uv`.
- For managing Python dependencies with `uv` — see the built-in `uv` skill.
