---
name: writing-fastapi-apis
description: |
  Conventions for building consistent FastAPI APIs — a uniform
  success/error response envelope (success/data/error/request_id),
  hierarchical error codes (DOMAIN.CONDITION) with a central ErrorCode
  enum + HTTP-status mapping, a single AppError exception raised
  everywhere and rendered by one registered exception handler,
  locale-agnostic i18n via message_key with synced locale tables, PII
  redaction discipline, SSE error events, and request_id middleware.
  Use when adding, modifying, or reviewing any FastAPI endpoint, route
  handler, error code, custom exception, Pydantic response model, or
  middleware; when registering a new error type or locale; when
  auditing responses or logs for PII leaks; or when bootstrapping a new
  API. Keywords: FastAPI, response envelope, error code, exception
  handler, AppError, i18n, message_key, PII redaction, SSE error event,
  request_id, middleware, Pydantic response model, endpoint. Refreshes
  FastAPI docs via the context7 MCP at use time so guidance tracks the
  installed version.
---

# Writing FastAPI APIs

Give every endpoint in your API one shape. Every response goes through
the same envelope, every error is a registered code, every translatable
string lives in one place. The reasons are pragmatic: a single frontend
has to render whatever you send, ops has to grep logs for codes without
leaking PII, and as endpoints multiply, drift now becomes carrying cost
forever.

This skill ships **drop-in scaffolding**. The first time it runs in a
fresh checkout, copy the templates from `assets/` into your API package
(referred to generically here as `api/`). After that, every new
endpoint imports from those modules. The skill's job from then on is to
keep you using them, and to refresh FastAPI knowledge against the
installed version rather than guessing from training data.

## When to invoke this skill

Trigger on any of:

- "Add an endpoint", "wire up a route", "expose `/something` over HTTP"
- "Register a new error", "what error code should I use?", "add 410 for X"
- "Audit X for PII leakage", "a contact field shows up in errors"
- "Add a translation for X", "we need an English string for Y"
- "Set up FastAPI", "install dependencies for the API", "bootstrap the API"
- Any modification of files under your API package
- Any addition or change to the API's `pyproject.toml`
- "How does our error format work?" / convention questions in general

If a request mentions endpoints, routes, errors, validation,
middleware, or SSE events, treat it as a trigger.

## First action: refresh FastAPI knowledge against the installed version

Before writing FastAPI code, query context7 for the **specific feature**
you're about to use. The model's training data may lag the installed
version.

```
mcp__context7__resolve-library-id  libraryName="FastAPI"
mcp__context7__query-docs           libraryId="/fastapi/fastapi/<version>"
                                    query="<the exact thing you're doing>"
```

Good queries: "BackgroundTasks with async generator", "Depends with
yield for connection pool", "register custom exception handler for
specific subclass". Bad queries: "FastAPI" or "how to use FastAPI" —
too broad, returns dumps.

Skip context7 for things that aren't FastAPI-specific: vanilla Python,
database drivers, dataclasses, ContextVar, Pydantic v2 (look those up
separately if needed).

## The envelope contract

Every response — success or error — is one of these two JSON shapes.
Nothing else. The frontend is built against this contract; deviations
break it.

**Success (any 2xx):**

```json
{
  "success": true,
  "data": { "...": "..." },
  "error": null,
  "request_id": "req_01HXXXXXXXXX"
}
```

**Error (any 4xx, 5xx):**

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "FORM.VALIDATION_FAILED",
    "message_key": "errors.form.validation_failed",
    "params": { "fields": ["email"] }
  },
  "request_id": "req_01HXXXXXXXXX"
}
```

**Note**: there is no `message` field on the wire. The frontend
translates `message_key` against its own i18n table — that keeps the
server locale-agnostic and means non-browser clients (curl, ops
scripts) get the same payload regardless of `Accept-Language`.

`error.params` is a flat object of safe interpolation values: field
names, counts, resource types. **Never PII** — see PII discipline below
and `references/pii-redaction.md`.

## Adding an endpoint (6 steps)

Full worked example in `references/adding-an-endpoint.md`. The short form:

1. **Refresh** FastAPI docs via context7 for the feature you'll use
   (path params, dependencies, response models, BackgroundTasks…).
2. **Define** request/response Pydantic models in the route module.
   Project response models, not raw DB rows — strip PII at the boundary.
3. **Implement** the handler. On any failure, `raise AppError(...)`. Do
   not return a tuple, do not `return err(...)` directly, do not
   `raise HTTPException`.
4. **Register** any new failure mode as an `ErrorCode` (see "Adding an
   error code" below).
5. **Return** through `responses.ok(data)`. The envelope is built for
   you; the request_id is stamped from the ContextVar.
6. **Audit** the success `data`: any field carrying PII the wire
   shouldn't expose? Project the model first.

## Adding an error code (3 steps)

Full catalog in `references/error-catalog.md`. The short form:

1. Add a member to `ErrorCode` in `errors.py` and an entry to
   `_HTTP_STATUS` mapping it to a status code. Use the hierarchical
   form `DOMAIN.CONDITION` (e.g. `FORM.STALE`, `ITEM.NOT_FOUND`).
2. Add an entry to **both** `locales/en.yaml` and `locales/zh-TW.yaml`
   under the matching `errors.<domain>.<condition>` key. Both locales
   must stay in sync — if one has a key, the other has it.
3. Add a catalog entry in `references/error-catalog.md` documenting
   when to raise it and the required `params` shape.

Then `raise AppError(ErrorCode.X, params={...})` from anywhere; the
exception handler renders it.

## PII discipline (summary)

Full rules and the `redact()` helper in `references/pii-redaction.md`.

The hard rules:

- **`error.params` carries field names, never values.**
  `{"fields": ["email"]}` ✓.  `{"email": "<redacted-email>"}` ✗.
- **Pydantic validation errors** are flattened to field paths only —
  the validation handler in `handlers.py` does this. Don't override it
  to include `exc.body`.
- **Logger uses `extra=`**, not f-strings with user input.
  `log.warning("ev", extra={"code": "..."})` ✓.
- **`AppError.cause`** is for `exc_info=` only. It never serialises.
- **Known PII fields** (e.g. `name`, `email`, `message`, free-form user
  content): out of error responses, out of info-level logs. Maintain a
  per-project table like the one in `references/pii-redaction.md`.

When you suspect a leak, look at three places: the `error.params`
object, the log line `extra=` keys, and any `f"... {x}"` formatting
where `x` came from a request.

## SSE-specific notes

For streaming endpoints: once the first byte has streamed, you can no
longer return an HTTP error — the response body is already framed as
`text/event-stream`. Convention: **errors mid-stream emit a terminal
SSE event**, not an exception bubble.

Full flow and helper in `references/sse-error-flow.md`. The shape:

```
event: error
data: {"code":"STREAM.ABORTED","message_key":"errors.stream.aborted","params":{},"request_id":"req_..."}
```

The frontend treats `event: "error"` as terminal. The server then
closes the connection. Errors raised **before** the first stream byte
go through the normal handler and return a regular envelope. If the
stream is driven by an LLM agent loop, see the sibling
`building-llm-agent-loops` skill.

## Bootstrapping into a fresh project

If `api/errors.py` doesn't yet exist, the templates need to land before
any endpoint is written. Copy each `assets/*.tmpl` into your API
package, dropping the `.tmpl` suffix (the example path below is `api/`;
substitute your own package path):

```
assets/errors.py.tmpl           → api/errors.py
assets/responses.py.tmpl        → api/responses.py
assets/handlers.py.tmpl         → api/handlers.py
assets/i18n.py.tmpl             → api/i18n.py
assets/request_context.py.tmpl  → api/request_context.py
assets/locales/                 → api/locales/  (whole dir)
```

Then in your `main.py`:

```python
from .handlers import register_exception_handlers
from .request_context import set_request_id

app = FastAPI()
register_exception_handlers(app)

@app.middleware("http")
async def _request_id_mw(request, call_next):
    set_request_id(request.headers.get("x-request-id"))
    return await call_next(request)
```

Add deps from `assets/pyproject-deps.md` via `uv add` (see the sibling
`uv` skill). Confirm the FastAPI version against context7 before pinning.

## Sibling skills

- `testing-async-fastapi` — tests assert this exact envelope shape.
- `building-llm-agent-loops` — the SSE loop that drives a streaming route.
- `dockerizing-fastapi-uv` — packaging the API for deployment.
- `uv` — dependency management; never `pip install` globally.

## Files in this skill

- `SKILL.md` — this file
- `references/error-catalog.md` — the canonical error code list
- `references/pii-redaction.md` — full PII rules + `redact()` helper
- `references/sse-error-flow.md` — mid-stream error flow + helper
- `references/adding-an-endpoint.md` — worked example
- `assets/*.tmpl` — drop-in Python modules (drop the `.tmpl` suffix)
- `assets/locales/{en,zh-TW}.yaml` — seed translation tables
- `assets/pyproject-deps.md` — uv add commands
- `evals.json` — pressure-test scenarios
