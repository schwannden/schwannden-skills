# LLM mocking — the boundary, not the wire

## Contents

- [Why the boundary](#why-the-boundary)
- [The boundary](#the-boundary)
- [The fixture](#the-fixture)
- [Programming the next response](#programming-the-next-response)
- [Asserting on what the loop sent](#asserting-on-what-the-loop-sent)
- [Server-tool blocks (web_search, web_fetch)](#server-tool-blocks-web_search-web_fetch)
- [When you actually want a real LLM call](#when-you-actually-want-a-real-llm-call)
- [Common failure modes](#common-failure-modes)

## Why the boundary

An LLM SDK does its own streaming, retry, and event reconstruction. Every
team that's tried to mock it at the HTTP layer (`respx`, `httpx_mock`,
`vcrpy`) has paid for it later when the SDK internals changed. The robust
approach is to fake the client at the SDK boundary the application defines.

The concrete example here uses the Anthropic SDK (`AsyncAnthropic`), but the
pattern is identical for any provider client — substitute your own.

## The boundary

The application has exactly one place where the LLM client enters the
request path:

```python
# api/agent/deps.py
from anthropic import AsyncAnthropic

_llm = AsyncAnthropic()  # reads its API key from env

def get_llm_client() -> AsyncAnthropic:
    return _llm
```

Routes don't import `AsyncAnthropic` directly; they accept it via
`Depends(get_llm_client)`. That single FastAPI dependency is the only seam
tests need.

## The fixture

`conftest.py` overrides that dependency inside the `app` fixture:

```python
@pytest.fixture
def fake_llm(app):
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm_client, None)
```

The `client` fixture depends on `fake_llm`, so any test that asks for
`client` automatically gets a faked LLM — no test ever accidentally calls
the real API.

## Programming the next response

`FakeLLM` ships a tiny builder DSL. A test programs the response(s) it
expects, runs the request, and asserts on the behaviour.

```python
async def test_chat_returns_text(client, fake_llm):
    fake_llm.expect_text("Hello there")

    async with client.stream("POST", "/chat", json={...}) as r:
        events = await read_sse_events(r)

    assert assert_token_text(events) == "Hello there"
```

### Available methods

```python
fake.expect_text("...")                 # one assistant text turn, end_turn
fake.expect_tool_use("book_appointment",
                     input={"start_time": "...",
                            "note": "..."})    # tool_use stop reason
fake.expect_pause_turn(partial_text="...")     # mid-stream pause
```

Chain calls to script multiple turns. The fake plays them in order:

```python
# Turn 1 → model says hi.
# Turn 2 → model calls book_appointment.
# Turn 3 → model wraps up.
fake.expect_text("Hello").\
     expect_tool_use("book_appointment", input={...}).\
     expect_text("Done — you're booked.")
```

If the loop calls the SDK more times than the fake has plans, the fake
raises an `AssertionError` with a clear message — that's almost always a
real bug in the loop (looping when it shouldn't).

## Asserting on what the loop sent

Every `messages.stream(...)` call records its kwargs into `fake.calls`.
Tests use this to verify load-bearing invariants from
`building-llm-agent-loops`:

```python
async def test_loop_sends_stable_tools_list(client, fake_llm):
    fake_llm.expect_text("ok")
    await client.post("/chat", json={"message": "hi", ...})

    assert len(fake_llm.calls) == 1
    tools = fake_llm.calls[0]["tools"]
    assert [t["name"] for t in tools] == ["web_search", "web_fetch", "book_appointment"]


async def test_system_prompt_has_cache_control(client, fake_llm):
    fake_llm.expect_text("ok")
    await client.post("/chat", json={"message": "hi", ...})

    sys = fake_llm.calls[0]["system"]
    # The system block must carry cache_control to make caching work
    assert any(b.get("cache_control") == {"type": "ephemeral"} for b in sys)
```

## Server-tool blocks (web_search, web_fetch)

When the loop is meant to consume `server_tool_use` /
`web_search_tool_result` blocks (e.g. to persist them into a
`tool_results` column), extend the fake's `_StreamCtx` to inject those
blocks into the final message.

A minimal approach: add a `with_server_tool_use` builder method that appends
a fake block to the next plan's `final_message.content`:

```python
fake.expect_text("Based on the page...").with_server_tool_use(
    web_search_results=[{"url": "https://example.com/...", "title": "...",
                         "page_age": "2025-01-01"}],
    web_fetch_pages=[{"url": "https://example.com/...", "content": "..."}],
)
```

The persistence test then asserts the stored row contains those structures
verbatim. Implement these extensions in `tests/_helpers/fake_llm.py`
incrementally as the loop's surface grows. The shipped template covers text
+ tool_use + pause_turn; that's enough to test an MVP loop end-to-end.

## When you actually want a real LLM call

A handful of tests genuinely need the real API:

- Nightly groundedness regressions (the bot still cites real URLs).
- A smoke test that the model name in env vars is still valid after a model
  retirement.

Mark them:

```python
@pytest.mark.live_llm
async def test_chat_cites_real_url(...):
    ...
```

`live_llm` is deselected by default (see `pytest_config.md` and the
`pytest_collection_modifyitems` hook in `conftest.py`). CI runs
`pytest -m live_llm` only on the nightly job, against a secret with a small
per-month budget.

These tests should be **few** (single digits), **shallow** (don't assert on
exact wording — only on shape: `assert "example.com" in text`), and
**independent** (no chaining across turns; flake budget is zero).

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `FakeLLM has no programmed plans left` | The loop is making more SDK calls than the test programmed | Either the loop is buggy, or the test is missing an `expect_*` for a follow-up turn |
| Test calls the real LLM and burns money | A test bypassed the `client` fixture and built its own `AsyncClient` | Always use `client` (or `fake_llm` plus the `app` fixture) |
| `text_stream` AttributeError on the fake | The application is using a method the fake doesn't ship | Add it to `_StreamCtx`; keep the fake minimal but extend as the loop grows |
| Assertions on `fake.calls` are off-by-one | The loop did a `pause_turn` resumption | Each `messages.stream(...)` call appends one entry; expect 2 calls for one pause-and-resume turn |
