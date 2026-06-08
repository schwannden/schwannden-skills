---
name: writing-drf-apis
description: >
  Senior Django REST Framework (DRF) expert for writing correct, consistent API views,
  serializers, and error responses. Use when: (1) Creating new API views or endpoints,
  (2) Writing or reviewing serializers, (3) Designing error responses with codes for i18n,
  (4) Handling exceptions in views, (5) Ensuring API response consistency across the codebase.
  Establishes best practices for all future DRF work.
---

# Writing DRF APIs

Best-practice guidance for Django REST Framework views, serializers, and API responses.
This skill defines the patterns all new DRF code should follow.

## Core Principles

1. **Consistent error contract** — Every error response uses `{"error": "CODE", "detail": "msg"}` so frontends can parse reliably
2. **Error codes for i18n** — Every error carries a machine-readable `error` code (UPPER_SNAKE_CASE) the frontend maps to localized strings
3. **Explicit over implicit** — Declare serializer fields, permissions, and status codes explicitly
4. **Validation in serializers, not views** — Views orchestrate; serializers validate
5. **Use DRF exceptions, not raw Response()** — Let a unified exception handler produce consistent responses

---

## Quick Reference: API Response Contract

### Success Responses

```python
from rest_framework.response import Response
from rest_framework import status

# Single object
return Response(serializer.data, status=status.HTTP_200_OK)

# Created
return Response(serializer.data, status=status.HTTP_201_CREATED)

# No content (delete)
return Response(status=status.HTTP_204_NO_CONTENT)

# List
return Response(serializer.data)  # 200 is default
```

**Rule:** Always use `rest_framework.status` constants, never bare integers.

### Error Responses (the consistent error contract)

All errors — validation, permission, throttle, server — MUST render as:

```json
{
  "error": "MACHINE_READABLE_CODE",
  "detail": "Optional human-readable message for triage."
}
```

- **`error`** (string, required): UPPER_SNAKE_CASE machine-readable code. Clients use this for i18n lookup.
- **`detail`** (string, optional): Human-readable English message for logging/debugging. NOT for end-user display.

For field-level validation errors:

```json
{
  "error": "VALIDATION_ERROR",
  "email": ["This field is required."],
  "password": ["Please choose a stronger password."]
}
```

The `"error": "VALIDATION_ERROR"` key is injected at the top level. Flat field keys are preserved as-is from DRF's default `ValidationError` serialization.

For rate limit errors:

```json
{
  "error": "RATE_LIMITED",
  "detail": "Too many requests.",
  "retry_after": 60
}
```

This is achieved via a **unified exception handler** wired into `REST_FRAMEWORK['EXCEPTION_HANDLER']` (see reference: `error-handling-patterns.md`).

---

## Pattern 1: APIView (Recommended for Complex Logic)

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

class MyResourceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = MyModel.objects.filter(owner=request.user)
        serializer = MySerializer(items, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # <-- ALWAYS raise_exception=True
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

**Key rules:**
- Always set `permission_classes` explicitly
- Always use `raise_exception=True` on `is_valid()` — never manually check `.errors`
- Return `Response(serializer.data)`, not hand-built dicts

### See also: `references/view-patterns.md`

---

## Pattern 2: Serializer Validation

### Field-Level Validation

```python
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if is_disposable_email(value):
            raise serializers.ValidationError(
                "Disposable emails are not allowed.",
                code="disposable_email"  # <-- ALWAYS provide a code for field-level errors
            )
        return value
```

### Object-Level Validation

```python
def validate(self, data):
    if data['start'] > data['end']:
        raise serializers.ValidationError(
            {"non_field_errors": "End must be after start."},
            code="invalid_date_range"
        )
    return data
```

### Custom Error Messages on Fields

```python
class MySerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = ['email', 'name']
        extra_kwargs = {
            'email': {
                'error_messages': {
                    'required': 'Email is required.',
                    'invalid': 'Enter a valid email address.',
                    'blank': 'Email cannot be blank.',
                }
            }
        }
```

**Key rules:**
- Always pass `code=` when raising `ValidationError` — frontends depend on it for i18n
- Use `validate_<field>` for single-field logic, `validate()` for cross-field logic
- Keep validation in the serializer, not in the view

### See also: `references/serializer-patterns.md`

---

## Pattern 3: Custom Exceptions with Error Codes

```python
from rest_framework.exceptions import APIException

class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable.'
    default_code = 'SERVICE_UNAVAILABLE'

class ConflictError(APIException):
    status_code = 409
    default_detail = 'Resource conflict.'
    default_code = 'CONFLICT'

class ResourceAlreadyClaimed(APIException):
    status_code = 409
    default_detail = 'Resource already claimed by another owner.'
    default_code = 'RESOURCE_ALREADY_CLAIMED'

# Usage — raise, don't return Response manually
raise ConflictError(detail="Username already taken.", code="USERNAME_TAKEN")
raise ResourceAlreadyClaimed()
```

**Key rules:**
- Subclass `APIException` for domain-specific errors
- Always set `default_code` in **UPPER_SNAKE_CASE** — this becomes the `"error"` value in the response
- Raise exceptions; don't construct `Response({...}, status=4xx)` manually
- The unified exception handler converts them to the contract: `{"error": "CODE", "detail": "msg"}`

### See also: `references/error-handling-patterns.md`

---

## Pattern 4: Permission Error Messages

```python
from rest_framework.permissions import BasePermission

class IsAccountOwner(BasePermission):
    message = "You do not own this account."  # Custom detail text
    code = "NOT_ACCOUNT_OWNER"               # UPPER_SNAKE_CASE error code for i18n

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user
```

---

## Pattern 5: Generic Views & Mixins

```python
from rest_framework import generics, permissions

class MyListCreateView(generics.ListCreateAPIView):
    serializer_class = MySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MyModel.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        if MyModel.objects.filter(owner=self.request.user).count() >= 10:
            raise serializers.ValidationError(
                "Maximum 10 items allowed.",
                code="limit_exceeded"
            )
        serializer.save(owner=self.request.user)
```

**Key rules:**
- Override `get_queryset()` not `queryset` for user-scoped data
- Use `perform_create` / `perform_update` for pre-save logic
- Raise `ValidationError` in `perform_*` hooks — DRF handles the 400 response

---

## Anti-Patterns (Do NOT Do)

| Anti-Pattern | Why It's Wrong | Correct Approach |
|---|---|---|
| `return Response({"detail": "msg"}, status=400)` | No `error` code, bypasses exception handler | `raise ValidationError("msg", code="SOME_CODE")` or custom `APIException` |
| `return Response({"error": "msg"}, status=400)` | Bypasses exception handler, won't get consistent formatting | `raise` a custom `APIException` subclass with `default_code` |
| `if not serializer.is_valid(): return Response(serializer.errors, 400)` | Verbose, bypasses handler | `serializer.is_valid(raise_exception=True)` |
| `except Exception: return Response({"detail": "error"}, 500)` | Swallows stack trace, hides bugs | Let DRF's exception handler catch `APIException`; let 500s propagate |
| Validation logic in the view body | Mixes concerns, hard to reuse | Move to serializer `validate_*` or `validate()` |
| Bare `raise ValidationError("msg")` without `code=` | Frontend can't map to i18n string | Always include `code=` in UPPER_SNAKE_CASE |
| `default_code = 'lowercase_code'` | Inconsistent with target format | Use UPPER_SNAKE_CASE: `default_code = 'SOME_CODE'` |
| `status=400` instead of `status=status.HTTP_400_BAD_REQUEST` | Less readable, harder to grep | Use `rest_framework.status` constants |

---

## Decision Tree: Where to Put Logic

```
Is it input validation?
  ├── Single field? → validate_<field>(self, value)
  ├── Cross-field?  → validate(self, data)
  └── Uniqueness?   → Meta.validators with UniqueValidator / UniqueTogetherValidator

Is it a business rule at save time?
  └── perform_create() / perform_update() → raise ValidationError

Is it an authorization check?
  └── Custom Permission class with .message and .code

Is it a domain error (not validation)?
  └── Custom APIException subclass with default_code

Is it an unexpected error?
  └── Let it propagate → DRF returns 500 via exception handler
```

---

## Reference Files

| File | Contents |
|------|----------|
| `references/error-handling-patterns.md` | Custom exception handler, ErrorDetail, get_codes(), 500 handling |
| `references/serializer-patterns.md` | ModelSerializer, nested serializers, validators, custom fields |
| `references/view-patterns.md` | APIView vs GenericAPIView vs ViewSet, dispatch flow, decorators |
| `references/status-codes-reference.md` | Full DRF status code constants list |
