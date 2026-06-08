# SSE error flow

For streaming endpoints, once the first byte of an SSE stream has been
sent, the response is already framed as `text/event-stream`; you can't
return a JSON envelope after that. The convention is: **errors that
occur mid-stream emit a terminal SSE event, then close the connection.**

Errors raised **before** the first byte go through the normal HTTP
exception handler and produce the regular `{success, data, error,
request_id}` envelope. The frontend distinguishes the two cases by HTTP
status (the SSE one is always 200) and by listening for the `error`
event type.

If your route wraps an LLM agent loop, see the sibling
`building-llm-agent-loops` skill — the loop produces the event stream
this helper wraps.

## Table of contents

- [Wire shape](#wire-shape)
- [Helper](#helper)
- [What about pre-stream errors?](#what-about-pre-stream-errors)
- [Frontend contract](#frontend-contract)

## Wire shape

```
event: error
data: {"code":"STREAM.ABORTED","message_key":"errors.stream.aborted","params":{"reason":"upstream"},"request_id":"req_01HXXXXX"}
```

The `data` payload is the same shape as the `error` block in the
regular envelope minus the outer `{success, data, error}` wrapping —
the frontend can reuse its error-rendering code by treating this as
`{success: false, data: null, error: <data>, request_id: ...}`.

After this event, the server sends no more events and closes the
connection.

## Helper

`api/sse.py` (add when implementing a streaming endpoint):

```python
import json
from typing import AsyncIterator
from .errors import AppError, ErrorCode
from .request_context import current_request_id

async def with_error_terminator(
    stream: AsyncIterator[dict],
) -> AsyncIterator[dict]:
    """Wrap an async generator of SSE events. If the wrapped generator
    raises AppError or any unexpected exception after streaming has
    started, emit a terminal `error` event instead of propagating."""
    try:
        async for event in stream:
            yield event
    except AppError as exc:
        yield _error_event(exc)
    except Exception:
        # Don't leak the underlying exception type or message
        yield _error_event(AppError(ErrorCode.STREAM_ABORTED,
                                    {"reason": "upstream"}))


def _error_event(exc: AppError) -> dict:
    payload = {
        "code": exc.code.value,
        "message_key": exc.message_key,
        "params": exc.params,
        "request_id": current_request_id(),
    }
    return {"event": "error", "data": json.dumps(payload, ensure_ascii=False)}
```

Wire it into the streaming endpoint:

```python
from sse_starlette.sse import EventSourceResponse
from .sse import with_error_terminator

@app.post("/stream")
async def stream(body: StreamIn):
    return EventSourceResponse(with_error_terminator(_run_stream(body)))
```

`_run_stream` produces the normal `{event: "token"|"data"|"end"}`
events. If it `raise`s `AppError(ErrorCode.STREAM_ABORTED, ...)`, the
wrapper turns it into a terminal `error` event. If it raises anything
else, the wrapper masks it as a generic `STREAM.ABORTED` — the
underlying exception is logged via the global unhandled-exception
handler but never reaches the wire.

## What about pre-stream errors?

If the request body fails Pydantic validation, FastAPI raises
`RequestValidationError` before the handler runs. That goes through the
normal validation handler and returns a 422 envelope — the SSE stream
never starts.

If the handler raises `AppError` before yielding its first event (say,
resource not found), `EventSourceResponse` hasn't sent headers yet, so
the global `AppError` handler intercepts and returns a 404 envelope. The
SSE stream never starts.

The `with_error_terminator` wrapper only matters once the generator has
begun yielding events.

## Frontend contract

The frontend treats `event: "error"` as **terminal**. Pseudocode:

```ts
streamRequest({...}, (ev) => {
  if (ev.event === "error") {
    showError(ev.data);
    closeStream();
    return;
  }
  // ...handle token, data, end
});
```

It does NOT retry automatically. Some errors are deliberate
(`STREAM.RATE_LIMITED`); the user-visible message and any retry offer
come from the frontend's i18n table keyed by `message_key`.
