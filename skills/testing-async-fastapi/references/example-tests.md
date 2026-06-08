# Example tests — one per layer

## Contents

- [Unit test](#unit-test--testsunittest_envelopepy)
- [Integration test](#integration-test--testsintegrationtest_appointment_endpointpy)
- [End-to-end test](#end-to-end-test--testse2etest_chat_basicpy)
- [TDD workflow](#tdd-workflow)
- [What you should not do](#what-you-should-not-do)

Three minimal, working examples. Each is also shipped as a `.tmpl` under
`assets/` so the bootstrap step lands them on disk. Use them as the shape
every new test follows.

## Unit test — `tests/unit/test_envelope.py`

A unit test exercises pure logic. No fixtures, no DB, no FastAPI app. The
whole point is to be fast enough to run on every save.

```python
import json

from api.request_context import set_request_id
from api.responses import ok


def test_ok_envelope_has_required_keys() -> None:
    set_request_id("req_test_1")
    payload = json.loads(ok({"hello": "world"}).body)

    assert payload["success"] is True
    assert payload["data"] == {"hello": "world"}
    assert payload["error"] is None
    assert payload["request_id"] == "req_test_1"


def test_ok_envelope_does_not_leak_extra_keys() -> None:
    set_request_id("req_test_2")
    payload = json.loads(ok({"x": 1}).body)
    assert set(payload.keys()) == {"success", "data", "error", "request_id"}
```

The `ok()` builder takes no `request_id` argument — it reads the id from a
ContextVar that middleware sets per request, so a unit test seeds it with
`set_request_id(...)` and decodes the returned `JSONResponse.body`.

Heuristics for "is this a unit test":

- Does it import `app` or any route handler? → not unit.
- Does it await anything besides pure-Python coroutines? → not unit.
- Does it touch `db_conn` or `client`? → not unit.

## Integration test — `tests/integration/test_appointment_endpoint.py`

Integration tests use `client` (the AsyncClient bound to the app) and
`db_conn` (the test's pinned connection). The LLM is auto-faked via the
`client` fixture's transitive dependency on `fake_llm`.

```python
import asyncpg
from httpx import AsyncClient

from tests._helpers.factories import make_note


async def test_health_endpoint_returns_ok_envelope(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"status": "ok"}


async def test_appointment_endpoint_persists_row(
    client: AsyncClient,
    db_conn: asyncpg.Connection,
) -> None:
    note_id = await make_note(db_conn)

    response = await client.post(
        "/appointments",
        json={"note_id": str(note_id), "title": "Intro call",
              "contact": "alice@example.com",
              "start_time": "2026-07-01T10:00:00Z",
              "note": "Tell me more"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True

    # The endpoint's writes are visible inside the same transaction.
    row = await db_conn.fetchrow(
        "SELECT title, start_time FROM appointments WHERE note_id = $1", note_id
    )
    assert row["title"] == "Intro call"


async def test_appointment_endpoint_rejects_unknown_note(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/appointments",
        json={"note_id": "00000000-0000-0000-0000-000000000000",
              "title": "x", "contact": "bob@example.com",
              "start_time": "2026-07-01T10:00:00Z", "note": "hi"},
    )
    body = response.json()
    assert response.status_code == 404
    assert body["error"]["code"] == "NOTE.NOT_FOUND"
    # PII discipline (per writing-fastapi-apis): contact MUST NOT leak.
    assert "bob@example.com" not in response.text
```

Three things to notice:

1. The DB row is asserted via `db_conn`, not via a follow-up GET. The pool
   override means `db_conn` and the endpoint share a transaction — what the
   endpoint wrote is visible to the test, and vice versa.
2. The 404 test asserts on `error.code`, not on a free-text message. The
   frontend is built against the code; assertions on phrasing would break
   translations.
3. PII discipline is a unit-of-test, not an afterthought. Every error test
   grep-asserts the user's PII does not appear in the response body.

## End-to-end test — `tests/e2e/test_chat_basic.py`

E2E tests assert on the SSE stream. They program `fake_llm` with the turn(s)
the test needs.

```python
import asyncpg
from httpx import AsyncClient

from tests._helpers.factories import make_note
from tests._helpers.fake_llm import FakeLLM
from tests._helpers.sse import assert_token_text, event_kinds, read_sse_events


async def test_chat_streams_assistant_text(
    client: AsyncClient,
    fake_llm: FakeLLM,
    db_conn: asyncpg.Connection,
) -> None:
    note_id = await make_note(db_conn)
    fake_llm.expect_text("Hello there, friend.")

    async with client.stream(
        "POST", "/chat",
        json={"note_id": str(note_id), "message": "hi"},
    ) as response:
        assert response.status_code == 200
        events = await read_sse_events(response)

    assert event_kinds(events)[-1] == "end"
    assert assert_token_text(events) == "Hello there, friend."


async def test_chat_book_appointment_emits_form_required(
    client: AsyncClient,
    fake_llm: FakeLLM,
    db_conn: asyncpg.Connection,
) -> None:
    note_id = await make_note(db_conn)
    fake_llm.expect_tool_use(
        "book_appointment",
        input={"start_time": "2026-07-01T10:00:00Z",
               "note": "wants to schedule"},
        leading_text="Of course — ",
    )

    async with client.stream(
        "POST", "/chat",
        json={"note_id": str(note_id), "message": "Can we schedule?"},
    ) as response:
        events = await read_sse_events(response)

    kinds = event_kinds(events)
    assert "form_required" in kinds
    form = next(e for e in events if e.event == "form_required")
    assert form.data["prefill"]["start_time"] == "2026-07-01T10:00:00Z"
```

## TDD workflow

The fast layer is your TDD inner loop:

```bash
KEEPDB=1 uv run pytest tests/unit -x --ff
```

`KEEPDB=1` keeps the test DB across runs (not strictly needed for unit
tests, but it's harmless and you'll want it the moment you add an
integration test to the loop). `-x` stops on first failure. `--ff` re-runs
the previous failures first so you iterate on the broken thing rather than
re-running 50 green tests.

When the unit ring is green, run the next layer:

```bash
uv run pytest tests/integration -x
```

When that's green:

```bash
uv run pytest          # everything except live_llm
```

That last command is what pre-push and CI both run.

## What you should not do

- **Don't write a test that talks to the real LLM by accident.** Use the
  `client` fixture or the explicit `fake_llm`.
- **Don't write integration tests that share state.** Each test gets a fresh
  transaction; if you find yourself reaching for module-level setup, you're
  fighting the framework.
- **Don't write e2e tests for things integration could cover.** SSE parsing
  is real overhead; if your test doesn't care about the stream, hit the
  route directly.
- **Don't add `time.sleep`.** Async tests don't need it. If a test seems to
  need it, the production code has a real race.
