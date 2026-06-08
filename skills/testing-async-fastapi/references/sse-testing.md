# Testing the SSE stream

## Contents

- [Event types we assert on](#event-types-we-assert-on)
- [The helper](#the-helper)
- [Pattern: assert on stream shape](#pattern-assert-on-stream-shape)
- [Pattern: assert on tool-use side effects](#pattern-assert-on-tool-use-side-effects)
- [Pattern: assert on the terminal error event](#pattern-assert-on-the-terminal-error-event)
- [What not to assert](#what-not-to-assert)
- [Common failure modes](#common-failure-modes)

`/chat` is a typical SSE endpoint. It streams **token events** as the model
produces text, may emit a **form_required** event when the model calls
`book_appointment`, and ends with **end** or a terminal **error**.

The full event protocol is defined by your API (see `writing-fastapi-apis`
for the SSE error-flow contract). This doc is about how to *test* against
that protocol.

## Event types we assert on

| `event:` | When it fires | `data` shape |
|---|---|---|
| `token` | Each chunk of assistant text | `{"text": "..."}` |
| `form_required` | After a `book_appointment` tool_use | `{"prefill": {"start_time": "...", "note": "..."}}` |
| `end` | Normal termination | `{"reason": "stop" \| "tool_use" \| ...}` |
| `error` | Mid-stream failure (terminal) | `{"code": "...", "message_key": "...", "params": {...}, "request_id": "..."}` |

A successful turn has the shape `[token..., end]` or
`[token..., form_required, end]`. A failed turn has `[token?..., error]` —
`error` is always last.

## The helper

Use `tests/_helpers/sse.py` rather than writing custom parsers in each test.
The key functions:

```python
from tests._helpers.sse import (
    read_sse_events,    # Response → list[SSEEvent]
    event_kinds,        # list[SSEEvent] → list[str]   (just the .event types)
    assert_token_text,  # list[SSEEvent] → str          (concat of all token data["text"])
)
```

Why a helper? Three reasons:

1. SSE framing is line-oriented (`event:`, `data:`, blank-line dispatch).
   Per-test parsers tend to swallow comment lines or miss the trailing
   blank-line case.
2. `data:` payloads are JSON; one `json.loads` site is easier to debug than
   ten.
3. When the protocol changes (new event type, new `data` field), you fix the
   helper, not every test.

## Pattern: assert on stream shape

```python
async def test_chat_basic(client, fake_llm, db_conn):
    note_id = await make_note(db_conn)
    fake_llm.expect_text("Hello, friend.")

    async with client.stream(
        "POST", "/chat",
        json={"note_id": str(note_id), "message": "hi"},
    ) as resp:
        assert resp.status_code == 200
        events = await read_sse_events(resp)

    assert event_kinds(events)[-1] == "end"
    assert assert_token_text(events) == "Hello, friend."
```

If your fake chunks at 8 chars (the default), "Hello, friend." gives two
`token` events. Don't pin the number unless you've also pinned the chunk
size — use `assert_token_text` to assert on the assembled text and let the
chunking be flexible.

## Pattern: assert on tool-use side effects

```python
async def test_book_appointment_emits_form(client, fake_llm, db_conn):
    note_id = await make_note(db_conn)
    fake_llm.expect_tool_use(
        "book_appointment",
        input={"start_time": "2026-07-01T10:00:00Z",
               "note": "ready to schedule"},
    )

    async with client.stream(
        "POST", "/chat",
        json={"note_id": str(note_id), "message": "let's schedule"},
    ) as resp:
        events = await read_sse_events(resp)

    kinds = event_kinds(events)
    assert "form_required" in kinds
    form = next(e for e in events if e.event == "form_required")
    assert form.data["prefill"]["start_time"] == "2026-07-01T10:00:00Z"
```

## Pattern: assert on the terminal error event

This is the case that's easy to get wrong. Once `/chat` has emitted its
first byte, the response is `200 OK` framed as SSE — there's no HTTP error
to come. The error surfaces *inside* the stream:

```python
async def test_chat_error_terminal_event(client, fake_llm, db_conn):
    note_id = await make_note(db_conn)
    # Arrange a deliberate failure: program only one turn when the loop
    # needs two, so the fake raises mid-stream and the server emits error.
    fake_llm.expect_tool_use("book_appointment", input={"start_time": "x"})

    async with client.stream(
        "POST", "/chat",
        json={"note_id": str(note_id), "message": "x"},
    ) as resp:
        # Status is still 200 — first bytes flushed before the error.
        assert resp.status_code == 200
        events = await read_sse_events(resp)

    assert events[-1].event == "error"
    err = events[-1].data
    assert err["code"].startswith("CHAT.")
    assert "request_id" in err
    # PII discipline: the user's message MUST NOT appear in the error.
    assert "x" not in err.get("params", {}).get("user_message", "")
```

## What not to assert

- **Don't assert on the precise number of `token` events.** Chunk sizes are
  an implementation detail of the streaming layer.
- **Don't assert on inter-event timing.** Tests run faster than real
  network; you'll get false positives.
- **Don't assert on `data:` raw bytes.** Use the parsed `.data` dict.
- **Don't grep `response.text` for tokens.** SSE responses are streamed;
  `.text` may be empty or partial. Always go through `read_sse_events`.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `read_sse_events` returns `[]` | The test consumed `response.text` first, exhausting the body | Always wrap in `async with client.stream(...)` and call the helper inside |
| Last event is missing | The server didn't flush a trailing blank line | The helper handles this — it flushes any unterminated event. If you still see it, check the server's SSE response config |
| `error` event has unexpected keys | The SSE error shape changed | Update the API contract (`writing-fastapi-apis`) and this reference together |
| Test passes locally, fails in CI under xdist | Two workers writing to the same DB | Per-worker DB names per `db-strategy.md` § "Parallelism" |
