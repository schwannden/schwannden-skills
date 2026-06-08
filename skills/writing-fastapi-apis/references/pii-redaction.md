# PII Redaction

Many APIs accept raw user input that frequently contains personal
information: names, descriptions, phone numbers, email addresses; a
form may capture contact info by design. All of it flows through the
backend. Two failure modes to avoid:

1. **PII echoed in error responses** — a validation error that includes
   the failing value, an upstream error message that quotes the user's
   input, a "user X not found" with a real identifier.
2. **PII in logs** — info-level log lines that interpolate request
   bodies for "debugging".

## Table of contents

- [Hard rules](#hard-rules)
  - [1. `error.params` carries field names, never values](#1-errorparams-carries-field-names-never-values)
  - [2. Pydantic validation errors are flattened to field paths only](#2-pydantic-validation-errors-are-flattened-to-field-paths-only)
  - [3. Logger uses `extra=`, not f-strings](#3-logger-uses-extra-not-f-strings)
  - [4. `AppError.cause` is for `exc_info=` only](#4-apperrorcause-is-for-exc_info-only)
  - [5. Known PII fields and where they may NOT appear](#5-known-pii-fields-and-where-they-may-not-appear)
  - [6. Raw free-form text — debug-only and redacted](#6-raw-free-form-text--debug-only-and-redacted)
- [The redactor](#the-redactor)
- [Audit triggers](#audit-triggers)

## Hard rules

### 1. `error.params` carries field names, never values

```python
# OK
raise AppError(ErrorCode.FORM_VALIDATION_FAILED, {"fields": ["email"]})

# NOT OK — the value of email is PII
raise AppError(ErrorCode.FORM_VALIDATION_FAILED, {"email": "<redacted-email>"})
```

The frontend already has the value the user typed; it doesn't need it
echoed back in `params`. If the user needs to know **which** field was
wrong, the field name is enough.

### 2. Pydantic validation errors are flattened to field paths only

The handler in `handlers.py` does this:

```python
fields = sorted({".".join(map(str, e["loc"][1:])) for e in exc.errors()})
```

Don't override that to add `exc.body` or `e["input"]` — both carry the
raw values that triggered the error. FastAPI's default behaviour
(returning `exc.body`) is exactly the leak we're avoiding.

### 3. Logger uses `extra=`, not f-strings

```python
# OK
log.info("item_created", extra={"item_id": str(iid)})

# NOT OK — body may contain PII
log.info(f"item_created: {body}")

# NOT OK — email is PII
log.info("submission", extra={"email": body.email})
```

Keep the structured-log keys fixed and free of user input or contact
details.

### 4. `AppError.cause` is for `exc_info=` only

```python
try:
    await client.call(...)
except SomeUpstreamError as e:
    raise AppError(ErrorCode.UPSTREAM_ERROR,
                   {"upstream": "<service-name>"},
                   cause=e)
```

The handler logs `cause` via `exc_info=exc.cause` so you get the
traceback in your log sink. It never reaches the wire — the field is
not part of the response body builder.

### 5. Known PII fields and where they may NOT appear

These are EXAMPLES — substitute your own model's fields. The point is
to maintain such a table per project.

| Field | OK in error response? | OK in info-level log? |
|---|---|---|
| `name` | no | no |
| `email` / phone | no | no |
| `message` (free-form user text) | no | no, only debug+redacted |
| user-authored content | no | no, only debug+redacted |
| system/assistant-authored content | no | yes |
| `category` (an enum/tag) | no | yes (a category, not a free-form leak vector) |
| resource id (uuid) | yes (as resource ref) | yes |
| `request_id` | yes | yes |

### 6. Raw free-form text — debug-only and redacted

If you need to log a free-form turn for debugging, log it at DEBUG and
run it through the redactor first.

## The redactor

Add this to the project's logging config (e.g. `api/logging.py`):

```python
import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")

def redact(s: str) -> str:
    s = _EMAIL.sub("<email>", s)
    s = _PHONE.sub("<phone>", s)
    return s
```

The patterns are deliberately conservative — under-redaction gets
caught at code review. Aggressive patterns over-mask normal numbers
(prices, ages, durations) and make logs unreadable.

Note that names embedded in free text (in any language) aren't
detectable by regex; the policy is "don't log free-form user content
above DEBUG, redact when you must".

## Audit triggers

Look for PII leaks when:

- A new `ErrorCode` is added — verify its `params` shape in
  `error-catalog.md` declares only safe types.
- A new field is added to any request model.
- A new log call appears in a code review — read the `extra=` and the
  message string for any user-derived value.
- An upstream error wrapper is added — make sure the upstream's
  `message` field is not propagated.
