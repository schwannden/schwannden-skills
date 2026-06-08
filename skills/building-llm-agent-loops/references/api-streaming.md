# API reference: streaming with `messages.stream`

When you stream the model's output to a client over SSE, this file covers the
SDK side: how `messages.stream()` works, what events you receive, and how to
translate them to your wire protocol.

**Authoritative docs:**
- Streaming overview: <https://docs.claude.com/en/api/messages-streaming>
- Python SDK README: <https://github.com/anthropics/anthropic-sdk-python>

## Table of contents

- [Why stream](#why-stream)
- [The Python SDK shape](#the-python-sdk-shape)
- [Streaming event types](#streaming-event-types)
- [Translating to the wire](#translating-to-the-wire)
- [Server-tool blocks don't stream incrementally](#server-tool-blocks-dont-stream-incrementally)
- [Error handling](#error-handling)

---

## Why stream

1. **Perceived latency**. A turn with one search and one fetch can be several
   seconds wall-clock. Streaming text token-by-token keeps the UI alive.
2. **Backpressure**. Streaming lets you emit events *during* the call — a
   `form_required` event when the model calls your client tool, citations as
   they attach — instead of holding everything until the call returns.

Use `messages.stream()` (the context manager) for production paths.
`messages.create()` is fine for tests where you want a synchronous final
message.

---

## The Python SDK shape

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic()  # API key from env

async with client.messages.stream(
    model=MODEL,
    system=SYSTEM,
    tools=TOOLS,
    messages=history,
    max_tokens=2048,
) as stream:
    async for event in stream:
        await translate_to_sse(event)
    final = await stream.get_final_message()
    # final is a Message — same shape messages.create() returns.
```

- `stream` is an async context manager; the `async with` holds the connection
  open, exiting closes it.
- `async for event in stream` walks streaming events as they arrive.
- `await stream.get_final_message()` returns the fully-assembled `Message` —
  what you persist. The events are for live display.

`stream.text_stream` yields just text deltas as strings. Convenient for simple
cases; use the full event stream when you need non-text events
(`server_tool_use`, your client tool, citations).

---

## Streaming event types

| Event type | Carries | What you do |
|---|---|---|
| `message_start` | The `Message` envelope, no content yet. | Start the SSE turn. |
| `content_block_start` | A new content block begins. | Track which block is being filled. |
| `content_block_delta` | Incremental update — most commonly `text_delta`. | If text: emit `token`. If tool-input deltas: accumulate. |
| `content_block_stop` | The current block ended. | If a `tool_use` for your client tool, emit `form_required` here. If a citation block, emit `citation`. |
| `message_delta` | `usage` and `stop_reason` updates. | Capture for the final message and cache-hit verification. |
| `message_stop` | The whole stream is done. | Loop body returns; `get_final_message()` is now safe. |

For tool input (JSON), `content_block_delta` events carry partial JSON strings
— rebuild by concatenation, parse once `content_block_stop` arrives.

---

## Translating to the wire

A skeletal translator:

```python
async def translate_to_sse(event, emit):
    match event.type:
        case "content_block_delta":
            if event.delta.type == "text_delta":
                await emit("token", {"text": event.delta.text})
        case "content_block_stop":
            block = event.content_block
            if block.type == "tool_use" and block.name == "book_appointment":
                await emit("form_required",
                           {"tool_use_id": block.id, "prefill": block.input})
            elif block.type == "web_search_result_location":
                await emit("citation", {
                    "url": block.url, "title": block.title,
                    "cited_text": block.cited_text,
                    # char-range field names can drift — verify in the live doc
                })
```

Emit the `end` and `error` events from the route handler, not from
`translate_to_sse` — they bracket the whole turn rather than any specific
event. `end` fires on `message_stop` after the loop decides no further
iterations are needed (`stop_reason == "end_turn"`); `error` fires on
exception with a friendly message (no stack traces).

---

## Server-tool blocks don't stream incrementally

**`web_search` and `web_fetch` activity is not delivered as
`content_block_delta` events.** The blocks appear in the `final` message
returned by `await stream.get_final_message()` after `message_stop` — not
token-by-token in the live stream. In practice:

- You **cannot** surface a "searching…" indicator by listening for
  `content_block_start` on `server_tool_use`; that event won't arrive
  mid-stream. If you want a progress indicator, emit a best-effort `status` SSE
  event from the route handler before invoking the loop, then clear it when the
  first `token` flows.
- Persistence still works: `get_final_message()` gives the assembled message
  including all `server_tool_use`, `web_search_tool_result`, and
  `web_fetch_tool_result` blocks. Persist via `block.model_dump(mode="json")`.

If you're following an older example that shows live-streamed server-tool
deltas, it's out of date — verify against the live streaming doc.

---

## Error handling

Network errors, model errors, and rate limits surface as exceptions when you
`async for` over the stream or call `get_final_message()`. **Catch them at the
boundary so none escapes to the SSE writer** — an escaped exception kills the
connection mid-stream with no `error` event, and the client shows a blank
reply.

```python
try:
    async for event in agent_loop(...):
        await emit_sse(event)
except anthropic.APIStatusError as e:
    await emit("error", {"code": "api", "message": friendly(e)})
except anthropic.APIConnectionError as e:
    await emit("error", {"code": "net", "message": friendly(e)})
except TypeError as e:
    # the SDK raises this when ANTHROPIC_API_KEY is unset
    await emit("error", {"code": "config", "message": friendly(e)})
except AssertionError:
    raise  # re-raise so test fixtures still surface
except Exception as e:
    await emit("error", {"code": "unknown", "message": friendly(e)})
finally:
    await emit("end", {})  # always close the SSE stream
```

Pin this behavior with tests (e.g. assert that an unset API key, a simulated
connection error, and an unexpected exception each yield a structured `error`
event rather than an aborted stream). For the route shape and error envelope
around the loop, see the `writing-fastapi-apis` skill; for testing the async
endpoint, `testing-async-fastapi`.

---

## Verifying streaming locally

Send a streaming request and confirm `token` lines arrive incrementally:

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"conversation_id": "00000000-0000-0000-0000-000000000000",
       "message": "what classes do you offer?"}'
```

You should see `event: token` lines arrive token-by-token, then maybe
`event: citation`, then `event: end`. If everything arrives at once at the end,
streaming is broken — check the route handler isn't buffering and that you're
not awaiting `get_final_message()` before yielding.
