# Error Catalog

Every error code has one row in `ErrorCode` (Python enum), one row in
`_HTTP_STATUS` (status mapping), one entry per locale YAML, and one
section in this catalog. All four must be in sync.

## Table of contents

- [Adding a new code](#adding-a-new-code)
- [Domains](#domains)
- [Catalog entries](#catalog-entries)
  - [`VALIDATION.FAILED`](#validationfailed)
  - [`ITEM.NOT_FOUND`](#itemnot_found)
  - [`FORM.VALIDATION_FAILED`](#formvalidation_failed)
  - [`FORM.STALE`](#formstale)
  - [`STREAM.ABORTED`](#streamaborted)
  - [`STREAM.RATE_LIMITED`](#streamrate_limited)
  - [`UPSTREAM.ERROR`](#upstreamerror)
  - [`UPSTREAM.UNAVAILABLE`](#upstreamunavailable)
  - [`INTERNAL.UNEXPECTED`](#internalunexpected)

The codes below are illustrative. Rename the domains to your own
(`ORDER`, `ACCOUNT`, `DOCUMENT`, …); keep the `DOMAIN.CONDITION` form
and the four-place sync rule.

## Adding a new code

1. Add a member to `ErrorCode` in `api/errors.py`.
   - Name uses `UPPER_SNAKE_CASE`; value uses dotted form `DOMAIN.CONDITION`.
   - `FORM_STALE = "FORM.STALE"` ✓
2. Add the HTTP status to `_HTTP_STATUS` in the same file.
3. Add an entry to **both** `api/locales/en.yaml` and
   `api/locales/zh-TW.yaml` under the key `errors.<domain>.<condition>`
   (lowercase, dotted).
4. Add a section here describing **when** to raise and the required
   `params` shape.

The pre-merge checklist is in step 4 of `references/adding-an-endpoint.md`.

## Domains

Codes group by domain prefix so logs are easy to filter:

- `VALIDATION.*` — generic input validation (Pydantic, type errors)
- `<RESOURCE>.*` — per-resource lookup/state errors (e.g. `ITEM.*`)
- `<FLOW>.*` — a multi-step submission flow (e.g. `FORM.*`)
- `STREAM.*` — SSE / streaming endpoints
- `UPSTREAM.*` — external dependencies (other services, third-party APIs)
- `INTERNAL.*` — bugs, unhandled exceptions

Add new domains sparingly. A rate limit on a streaming endpoint belongs
in `STREAM` (`STREAM.RATE_LIMITED`); it does **not** become a top-level
domain.

---

## Catalog entries

### `VALIDATION.FAILED`

- **HTTP**: 422
- **When**: Pydantic request validation fails on any endpoint. The
  exception handler in `handlers.py` raises this automatically; you
  rarely raise it manually.
- **Required params**: `{"fields": [str, ...]}` — the list of dotted
  field paths that failed (no values).
- **Frontend key**: `errors.validation.failed`

### `ITEM.NOT_FOUND`

- **HTTP**: 404
- **When**: A request references a resource id that does not exist (or
  has been deleted).
- **Required params**: `{"resource": "item"}` (the resource type string,
  not the id — ids are PII-adjacent).
- **Frontend key**: `errors.item.not_found`
- **Raise**: `raise AppError(ErrorCode.ITEM_NOT_FOUND, {"resource": "item"})`

### `FORM.VALIDATION_FAILED`

- **HTTP**: 422
- **When**: Domain validation failure beyond Pydantic on a submission
  flow (e.g. a business-rule check that a category is in a known set).
- **Required params**: `{"fields": [str, ...]}`
- **Frontend key**: `errors.form.validation_failed`
- **Raise**: `raise AppError(ErrorCode.FORM_VALIDATION_FAILED, {"fields": ["category"]})`

### `FORM.STALE`

- **HTTP**: 410 Gone
- **When**: User submits a form tied to a resource older than the
  freshness window or already closed.
- **Required params**: `{"age_hours": int}` (NEVER include raw user
  input or PII).
- **Frontend key**: `errors.form.stale`
- **Raise**: `raise AppError(ErrorCode.FORM_STALE, {"age_hours": 30})`

### `STREAM.ABORTED`

- **HTTP**: 499 (client-closed; informational; usually surfaced as an
  SSE error event rather than an HTTP status — see
  `references/sse-error-flow.md`).
- **When**: An SSE stream terminates after the first byte due to an
  upstream error, client disconnect, or budget cap.
- **Required params**: `{}` or `{"reason": "upstream"|"client"|"budget"}`
  (a fixed enum, not a free-text reason).
- **Frontend key**: `errors.stream.aborted`

### `STREAM.RATE_LIMITED`

- **HTTP**: 429
- **When**: A per-client or per-IP rate limit fires before the request
  reaches the expensive work.
- **Required params**: `{"retry_after_seconds": int}`
- **Frontend key**: `errors.stream.rate_limited`
- **Raise**: `raise AppError(ErrorCode.STREAM_RATE_LIMITED, {"retry_after_seconds": 30})`

### `UPSTREAM.ERROR`

- **HTTP**: 502 Bad Gateway
- **When**: An external dependency returned a structured error (a 4xx
  from their side, a policy refusal you want to surface, etc.).
- **Required params**: `{"upstream": "<service-name>"}` (do NOT pass the
  upstream's `error.message`; it can echo request content).
- **Frontend key**: `errors.upstream.error`

### `UPSTREAM.UNAVAILABLE`

- **HTTP**: 503 Service Unavailable
- **When**: Network failure, timeout, or 5xx from an external dependency.
- **Required params**: `{"upstream": "<service-name>"}`
- **Frontend key**: `errors.upstream.unavailable`

### `INTERNAL.UNEXPECTED`

- **HTTP**: 500
- **When**: Catch-all in the unhandled-exception handler. You don't
  raise this — the handler fabricates it for any non-`AppError`
  exception that escaped.
- **Required params**: `{}` — the wire response carries nothing
  diagnostic. The actual exception is logged with `exc_info`.
- **Frontend key**: `errors.internal.unexpected`
