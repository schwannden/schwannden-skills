# View Patterns

Guide to DRF views: APIView, generic views, ViewSets, function-based views, and the dispatch cycle.

> **DRF Docs:**
> - Views: https://www.django-rest-framework.org/api-guide/views/
> - Generic Views: https://www.django-rest-framework.org/api-guide/generic-views/
> - Responses: https://www.django-rest-framework.org/api-guide/responses/

---

## Contents

1. View Type Decision Tree
2. APIView — The Foundation
3. Generic Views — CRUD Shortcuts
4. Function-Based Views
5. Response Object
6. Exception Handling in Views
7. Status Codes Module

## 1. View Type Decision Tree

```
Do you need full control over the HTTP method logic?
  └── Yes → APIView

Is it standard CRUD on a model?
  ├── Single resource → RetrieveUpdateDestroyAPIView (or combination)
  ├── List + create  → ListCreateAPIView
  └── Full CRUD with router → ModelViewSet

Is it a simple one-off endpoint (no class needed)?
  └── @api_view function
```

---

## 2. APIView — The Foundation

All DRF class-based views inherit from `APIView`. It wraps Django's `View` with:
- DRF `Request` / `Response` objects
- Content negotiation
- Authentication, permissions, throttling enforcement
- Exception handling

### Dispatch Flow (What Happens on Every Request)

```
1. initialize_request()     — Wrap Django HttpRequest → DRF Request
2. initial()                — Run authentication, permissions, throttling
   ├── perform_authentication()
   ├── check_permissions()
   └── check_throttles()
3. handler()                — Call .get(), .post(), .put(), .patch(), .delete()
4. handle_exception()       — If handler raises, convert to Response
5. finalize_response()      — Content negotiation, render response
```

### Standard APIView Template

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, serializers

class ItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        item = get_object_or_404(Item, pk=pk, owner=request.user)
        serializer = ItemSerializer(item)
        return Response(serializer.data)

    def put(self, request, pk):
        item = get_object_or_404(Item, pk=pk, owner=request.user)
        serializer = ItemSerializer(item, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        item = get_object_or_404(Item, pk=pk, owner=request.user)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

### Policy Attributes

```python
class MyView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAccountOwner]
    throttle_classes = [UserRateThrottle]
    renderer_classes = [JSONRenderer]
    parser_classes = [JSONParser]
```

---

## 3. Generic Views — CRUD Shortcuts

### Concrete Views

| View | Methods | Mixins |
|------|---------|--------|
| `CreateAPIView` | POST | Create |
| `ListAPIView` | GET (list) | List |
| `RetrieveAPIView` | GET (detail) | Retrieve |
| `DestroyAPIView` | DELETE | Destroy |
| `UpdateAPIView` | PUT, PATCH | Update |
| `ListCreateAPIView` | GET, POST | List + Create |
| `RetrieveUpdateAPIView` | GET, PUT, PATCH | Retrieve + Update |
| `RetrieveDestroyAPIView` | GET, DELETE | Retrieve + Destroy |
| `RetrieveUpdateDestroyAPIView` | GET, PUT, PATCH, DELETE | Retrieve + Update + Destroy |

### Standard Generic View Template

```python
from rest_framework import generics, permissions

class ItemListCreateView(generics.ListCreateAPIView):
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Item.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
```

### Hook Methods

| Method | Called By | Purpose |
|--------|-----------|---------|
| `perform_create(serializer)` | CreateModelMixin | Pre-save logic for creation |
| `perform_update(serializer)` | UpdateModelMixin | Pre-save logic for updates |
| `perform_destroy(instance)` | DestroyModelMixin | Pre-delete logic |
| `get_queryset()` | All | Dynamic queryset (user-scoped, filtered) |
| `get_serializer_class()` | All | Dynamic serializer (by method, user role) |
| `get_object()` | Detail views | Object retrieval + permission check |

### Dynamic Serializer by Action

```python
class ItemView(generics.RetrieveUpdateAPIView):
    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ItemWriteSerializer
        return ItemReadSerializer
```

---

## 4. Function-Based Views

For simple endpoints that don't need class structure:

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)
```

**Available decorators** (apply AFTER `@api_view`):
- `@renderer_classes([...])`
- `@parser_classes([...])`
- `@authentication_classes([...])`
- `@permission_classes([...])`
- `@throttle_classes([...])`

---

## 5. Response Object

```python
from rest_framework.response import Response

# Constructor
Response(data, status=None, template_name=None, headers=None, content_type=None)
```

- `data` — Unrendered Python data (dict, list, etc.). DRF serializes it via the negotiated renderer.
- `status` — HTTP status code. Always use `rest_framework.status` constants.
- `headers` — Dict of additional HTTP headers.

### Key Attributes

| Attribute | Description |
|-----------|-------------|
| `.data` | The unrendered response data (Python primitives) |
| `.status_code` | Numeric HTTP status |
| `.content` | Rendered output (after `.render()`) |
| `.accepted_renderer` | The renderer selected by content negotiation |

### Setting Headers

```python
response = Response(data)
response['Cache-Control'] = 'no-cache'
response['X-Custom-Header'] = 'value'
```

---

## 6. Exception Handling in Views

### Default Behavior

When a view raises an exception:
1. `handle_exception(exc)` is called
2. It delegates to the configured `EXCEPTION_HANDLER` function
3. `APIException` subclasses → appropriate HTTP error response
4. `Http404` → 404 response
5. `PermissionDenied` → 403 response
6. Anything else → 500 (unhandled)

### Per-View Override

```python
class MyView(APIView):
    def handle_exception(self, exc):
        # Custom logging, transformation, etc.
        if isinstance(exc, ExternalServiceError):
            exc = ServiceUnavailable()  # Map to DRF exception
        return super().handle_exception(exc)
```

### Important: Exception Handler Only Catches Raised Exceptions

If you return `Response(..., status=400)` directly, the exception handler is NOT invoked.
This is why you should raise exceptions, not return error responses manually.

---

## 7. Status Codes Module

```python
from rest_framework import status

# Success
status.HTTP_200_OK
status.HTTP_201_CREATED
status.HTTP_204_NO_CONTENT

# Client errors
status.HTTP_400_BAD_REQUEST
status.HTTP_401_UNAUTHORIZED
status.HTTP_403_FORBIDDEN
status.HTTP_404_NOT_FOUND
status.HTTP_405_METHOD_NOT_ALLOWED
status.HTTP_409_CONFLICT
status.HTTP_429_TOO_MANY_REQUESTS

# Server errors
status.HTTP_500_INTERNAL_SERVER_ERROR
status.HTTP_503_SERVICE_UNAVAILABLE

# Helpers
status.is_success(200)       # True
status.is_client_error(400)  # True
status.is_server_error(500)  # True
```

Full list: see `references/status-codes-reference.md`
