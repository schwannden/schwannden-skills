# Error Handling Patterns

Comprehensive guide to DRF error handling. All error responses follow one consistent contract.

> **DRF Docs:** https://www.django-rest-framework.org/api-guide/exceptions/

---

## Contents

1. Error Response Contract
2. How a Unified Exception Handler Works
3. The ErrorDetail Class
4. Built-in Exception Classes Reference
5. Creating Custom Exceptions
6. Raising ValidationError with Codes
7. Handling 5xx Errors
8. Overriding handle_exception on a View
9. Key Rule: Raise, Don't Return

## 1. Error Response Contract

### Single Error

All non-validation errors render as:

```json
{
  "error": "MACHINE_READABLE_CODE",
  "detail": "Optional human-readable message for triage."
}
```

- **`error`** (string, required): UPPER_SNAKE_CASE machine-readable code. Clients use this for i18n lookup.
- **`detail`** (string, optional): Human-readable English message for logging/debugging. NOT for end-user display.

### Validation Error

```json
{
  "error": "VALIDATION_ERROR",
  "email": ["This field is required."],
  "password": ["Please choose a stronger password."]
}
```

The `"error": "VALIDATION_ERROR"` key is injected at the top level by the unified exception handler. Flat field keys are preserved as-is from DRF's default `ValidationError` serialization.

### Rate Limit Error

```json
{
  "error": "RATE_LIMITED",
  "detail": "Too many requests.",
  "retry_after": 60
}
```

---

## 2. How a Unified Exception Handler Works

Wire a custom handler into your settings:

```python
# settings.py
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "myapp.exception_handler.custom_exception_handler",
}
```

The handler intercepts all exceptions and normalizes them into the contract above:

| Exception Type | Handler Behavior | Response |
|---|---|---|
| Custom `APIException` subclasses (4xx) | Extracts `error` from `detail.code` or `default_code` | `{"error": "CODE", "detail": "msg"}` |
| Custom `APIException` subclasses (5xx, `return_json=True`) | Same as 4xx — returns structured JSON | `{"error": "CODE", "detail": "msg"}` |
| Custom `APIException` subclasses (5xx, default) | Returns `None` → DRF re-raises → Django renders the default HTML 500 page | HTML error page |
| `ValidationError` (dict-form) | Injects `"error": "VALIDATION_ERROR"` into existing field-keyed response | `{"error": "VALIDATION_ERROR", "field": ["msg"]}` |
| `ValidationError` (list-form) | Passes through as bare array — no wrapping (see Section 2a) | `["msg1", "msg2"]` |
| Rate limit exceptions | Returns `RATE_LIMITED` with `retry_after` | `{"error": "RATE_LIMITED", ...}` |
| Detail-scrubbing exceptions | Always replaces dynamic detail with `default_detail` so sensitive internals never reach the client | `{"error": "CODE", "detail": "default_detail"}` |
| Unhandled exceptions | Falls through → Django 500 | N/A |

### 2a. Why Only ValidationError Can Produce List-Form Responses

DRF's `ValidationError.__init__` has **unique coercion logic** that no other exception class has:

```python
# ValidationError.__init__ (rest_framework/exceptions.py)
if isinstance(detail, tuple):
    detail = list(detail)
elif not isinstance(detail, dict) and not isinstance(detail, list):
    detail = [detail]  # <-- STRING WRAPPED INTO LIST
```

This means `raise ValidationError("some message")` stores `detail = ["some message"]` — a **list**. DRF's `exception_handler` then sets `response.data = exc.detail`, producing a bare JSON array response.

In contrast, `APIException.__init__` (the base class for all other exceptions) stores `detail` **as-is**:

```python
# APIException.__init__ (rest_framework/exceptions.py)
self.detail = _get_error_details(detail, code)
# String stays string → exception_handler returns {"detail": "some message"} (always a dict)
```

**Summary of `detail` storage by exception type:**

| Exception | `raise Exc("msg")` | `exc.detail` | `response.data` |
|---|---|---|---|
| `ValidationError` | String coerced to list | `["msg"]` | `["msg"]` (bare array) |
| `ValidationError` | Dict passed through | `{"field": ["msg"]}` | `{"field": ["msg"]}` (dict) |
| `ValidationError` | List passed through | `["msg1", "msg2"]` | `["msg1", "msg2"]` (bare array) |
| Any other `APIException` | String stays string | `"msg"` | `{"detail": "msg"}` (always dict) |

**Consequence for the unified handler:** An `isinstance(response.data, dict)` check in the generic catch-all branch is safe for all non-`ValidationError` exceptions — they always produce dicts. Only `ValidationError` can produce a list. If you have legacy clients that expect bare-array responses, pass list-form responses through unchanged; otherwise normalize them to dict-form.

### Best Practice: Align ValidationError with the Target Format

When raising `ValidationError` outside a serializer context (e.g. in view or utility code), always use **dict-form** to ensure the unified handler can inject `"error": "VALIDATION_ERROR"`:

```python
# WRONG — produces bare array, handler cannot inject "error" key
raise serializers.ValidationError(["Please choose a stronger password."])

# RIGHT — handler injects "error": "VALIDATION_ERROR" into the dict
raise serializers.ValidationError({"non_field_errors": ["Please choose a stronger password."]})
```

For field-specific errors raised outside a serializer:

```python
# RIGHT — handler injects "error": "VALIDATION_ERROR" into the dict
raise serializers.ValidationError({"password": ["Please choose a stronger password."]})
```

Inside serializer `validate_*` methods, DRF automatically nests the error under the field name as a dict, so string/list raises are fine there — they will always produce dict-form responses.

### Error Code Priority

When extracting the `error` code, the handler checks in order:
1. `exc.detail.code` — set at the raise site: `raise PermissionDenied(code="INVALID_CREDENTIAL")`
2. `exc.default_code` — set on the exception class: `default_code = "ACCOUNT_LOCKED"`
3. Fallback: `"ERROR"`

---

## 3. The ErrorDetail Class

DRF wraps every error string in `ErrorDetail`, which carries both a message and a code:

```python
from rest_framework.exceptions import ValidationError

exc = ValidationError({"name": "This field is required."})

# .detail — the human-readable text
print(exc.detail)
# {"name": [ErrorDetail(string="This field is required.", code="required")]}

# .get_codes() — just the machine-readable codes
print(exc.get_codes())
# {"name": ["required"]}

# .get_full_details() — both message and code
print(exc.get_full_details())
# {"name": [{"message": "This field is required.", "code": "required"}]}
```

**This is the foundation for i18n:** the `code` is what the frontend uses to look up the localized string.

---

## 4. Built-in Exception Classes Reference

| Exception | Status | Default Code | When Raised |
|-----------|--------|-------------|-------------|
| `ParseError` | 400 | `parse_error` | Malformed request body |
| `ValidationError` | 400 | `invalid` | Serializer validation failure |
| `AuthenticationFailed` | 401 | `authentication_failed` | Bad credentials |
| `NotAuthenticated` | 401/403 | `not_authenticated` | No credentials provided |
| `PermissionDenied` | 403 | `permission_denied` | Insufficient permissions |
| `NotFound` | 404 | `not_found` | Resource doesn't exist |
| `MethodNotAllowed` | 405 | `method_not_allowed` | Wrong HTTP method |
| `NotAcceptable` | 406 | `not_acceptable` | Can't satisfy Accept header |
| `UnsupportedMediaType` | 415 | `unsupported_media_type` | Wrong Content-Type |
| `Throttled` | 429 | `throttled` | Rate limit exceeded |

All accept `detail=` and `code=` parameters to override defaults:
```python
raise NotFound(detail="User not found.", code="USER_NOT_FOUND")
raise PermissionDenied(detail="Invalid credential", code="INVALID_CREDENTIAL")
```

**Always use UPPER_SNAKE_CASE for `code=` values.**

---

## 5. Creating Custom Exceptions

For domain-specific errors, create `APIException` subclasses:

```python
from rest_framework.exceptions import APIException

class ConflictError(APIException):
    """409 Conflict — resource state prevents the operation."""
    status_code = 409
    default_detail = 'A conflict occurred.'
    default_code = 'CONFLICT'

class ResourceAlreadyClaimed(APIException):
    """409 — resource claimed by another owner."""
    status_code = 409
    default_detail = 'Resource already claimed by another owner.'
    default_code = 'RESOURCE_ALREADY_CLAIMED'
```

Usage — always raise, never return `Response(...)` manually:
```python
raise ResourceAlreadyClaimed()
raise ConflictError(detail="Username already taken.", code="USERNAME_TAKEN")
```

The unified exception handler will produce:
```json
{"error": "RESOURCE_ALREADY_CLAIMED", "detail": "Resource already claimed by another owner."}
{"error": "USERNAME_TAKEN", "detail": "Username already taken."}
```

**Rules:**
- `default_code` MUST be UPPER_SNAKE_CASE
- Prefer defining a custom exception class over passing `code=` at the raise site
- The exception class name should describe the error condition
- Set `status_code`, `default_detail`, and `default_code` on every custom exception

### 5a. A `return_json` Marker for 5xx Exceptions

A useful convention: by default, let **5xx `APIException` subclasses return `None`** from the unified handler. This causes DRF to re-raise, and Django renders the default HTML error page (optionally with an error-reference id you can correlate to logs). This is correct for unexpected internal errors — users see a generic page, ops can look up the reference.

However, some 5xx errors are **expected external-dependency failures** (cache down, an upstream service unavailable, a missing credential). These endpoints are JSON APIs called by JavaScript frontends. The default HTML 500 response cannot be parsed by `response.json()` — the client gets a parse error and cannot handle the failure programmatically. The client needs a machine-readable JSON error code so it can branch on the error (retry, show a specific message, fall back to an alternative flow).

Set `return_json = True` on the exception class to bypass the HTML path:

```python
class ServiceUnavailable(APIException):
    """Known external-dependency failure — returns JSON, not HTML."""
    status_code = 503
    default_detail = 'Service temporarily unavailable.'
    default_code = 'SERVICE_UNAVAILABLE'
    return_json = True  # Handler returns {"error": "SERVICE_UNAVAILABLE", "detail": "..."} as JSON
```

**When to use `return_json = True`:**
- The endpoint is a **JSON API** consumed by a frontend or another service (not a browser page)
- The 5xx is caused by an **expected external-dependency failure** (cache, upstream API, third party), not a bug in your code
- The client needs to **handle the error programmatically** based on the error code — branch logic on it (retry, fallback, redirect)

**When NOT to use it (leave the default HTML path):**
- Unexpected internal errors, programming bugs, unhandled exceptions
- Browser-facing endpoints where an HTML error page is appropriate
- Any case where the error represents a bug that should be investigated, not an expected condition

**Note:** Diagnostic info for debugging (root cause, dependency details) should go into your logs — not into the client response body. If an exception carries sensitive internals in its dynamic detail (e.g. crypto or upstream internals), have the handler scrub it to `default_detail` in the response and keep the raw detail only in logs.

---

## 6. Raising ValidationError with Codes

### Simple field error
```python
raise serializers.ValidationError(
    "Email is invalid.",
    code="INVALID_EMAIL"
)
```

### Multiple field errors
```python
raise serializers.ValidationError({
    "email": serializers.ValidationError("Already registered.", code="EMAIL_EXISTS"),
    "username": serializers.ValidationError("Too short.", code="USERNAME_TOO_SHORT"),
})
```

### Non-field error (cross-field validation)
```python
raise serializers.ValidationError(
    {"non_field_errors": ["Passwords do not match."]},
    code="PASSWORD_MISMATCH"
)
```

**Always use UPPER_SNAKE_CASE for `code=` values.**

---

## 7. Handling 5xx Errors

A unified handler typically has two 5xx paths:

**Default (HTML):** 5xx `APIException` subclasses return `None` from the handler. DRF re-raises and Django renders its default 500 page. This is correct for unexpected internal errors — bugs, unhandled exceptions, programming mistakes.

**JSON (`return_json=True`):** Exception classes that set `return_json = True` bypass the HTML path and return structured JSON. Use this only for *expected* external-dependency failures where the client needs a machine-readable code. See Section 5a.

```python
# Unexpected bug → HTML 500 (default)
raise InternalError("something broke")

# Expected external failure → JSON with error code
raise ServiceUnavailable("Cache cluster unreachable")  # return_json=True on class
```

---

## 8. Overriding handle_exception on a View

For per-view customization (rare — prefer the unified handler):

```python
class MyView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, SomeSpecialError):
            # Log, transform, etc.
            pass
        return super().handle_exception(exc)
```

A view can also override `handle_exception` to return a plain-text `HttpResponse` for clients that do not expect JSON, matching whatever the unified handler does.

---

## 9. Key Rule: Raise, Don't Return

If you return `Response({...}, status=400)` directly, the exception handler is NOT invoked. This means the response won't follow the consistent contract.

**Always raise exceptions:**
```python
# WRONG — bypasses the handler
return Response({"detail": "Resource not found"}, status=404)

# RIGHT — handler formats it as {"error": "RESOURCE_NOT_FOUND", "detail": "..."}
raise ResourceNotFound()
```

If you need to include diagnostic information for the client, put it in the `detail` string rather than adding extra response fields.
