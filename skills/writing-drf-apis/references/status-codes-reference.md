# Status Codes Reference

Full list of DRF status code constants.

> **DRF Docs:** https://www.django-rest-framework.org/api-guide/status-codes/

```python
from rest_framework import status
```

## Informational (1xx)

| Constant | Value |
|----------|-------|
| `HTTP_100_CONTINUE` | 100 |
| `HTTP_101_SWITCHING_PROTOCOLS` | 101 |
| `HTTP_102_PROCESSING` | 102 |
| `HTTP_103_EARLY_HINTS` | 103 |

## Success (2xx)

| Constant | Value | Common Use |
|----------|-------|------------|
| `HTTP_200_OK` | 200 | GET, PUT, PATCH success |
| `HTTP_201_CREATED` | 201 | POST creation success |
| `HTTP_202_ACCEPTED` | 202 | Async task accepted |
| `HTTP_204_NO_CONTENT` | 204 | DELETE success, no body |
| `HTTP_206_PARTIAL_CONTENT` | 206 | Paginated/range responses |

## Redirection (3xx)

| Constant | Value |
|----------|-------|
| `HTTP_301_MOVED_PERMANENTLY` | 301 |
| `HTTP_302_FOUND` | 302 |
| `HTTP_304_NOT_MODIFIED` | 304 |
| `HTTP_307_TEMPORARY_REDIRECT` | 307 |
| `HTTP_308_PERMANENT_REDIRECT` | 308 |

## Client Error (4xx)

| Constant | Value | Common Use |
|----------|-------|------------|
| `HTTP_400_BAD_REQUEST` | 400 | Validation errors |
| `HTTP_401_UNAUTHORIZED` | 401 | Not authenticated |
| `HTTP_403_FORBIDDEN` | 403 | Permission denied |
| `HTTP_404_NOT_FOUND` | 404 | Resource not found |
| `HTTP_405_METHOD_NOT_ALLOWED` | 405 | Wrong HTTP method |
| `HTTP_406_NOT_ACCEPTABLE` | 406 | Can't satisfy Accept header |
| `HTTP_409_CONFLICT` | 409 | State conflict |
| `HTTP_415_UNSUPPORTED_MEDIA_TYPE` | 415 | Wrong Content-Type |
| `HTTP_422_UNPROCESSABLE_ENTITY` | 422 | Semantic validation failure |
| `HTTP_429_TOO_MANY_REQUESTS` | 429 | Rate limited |

## Server Error (5xx)

| Constant | Value | Common Use |
|----------|-------|------------|
| `HTTP_500_INTERNAL_SERVER_ERROR` | 500 | Unhandled exception |
| `HTTP_502_BAD_GATEWAY` | 502 | Upstream failure |
| `HTTP_503_SERVICE_UNAVAILABLE` | 503 | Service down/maintenance |
| `HTTP_504_GATEWAY_TIMEOUT` | 504 | Upstream timeout |

## Helper Functions

```python
from rest_framework.status import is_success, is_client_error, is_server_error

is_success(200)        # True (2xx)
is_client_error(400)   # True (4xx)
is_server_error(500)   # True (5xx)
is_informational(100)  # True (1xx)
is_redirect(301)       # True (3xx)
```
