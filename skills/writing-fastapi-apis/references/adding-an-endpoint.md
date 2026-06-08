# Adding an endpoint — worked example

The 6-step recipe with a hypothetical `GET /items/{id}` that returns a
single item resource.

## Table of contents

- [1. Refresh FastAPI knowledge via context7](#1-refresh-fastapi-knowledge-via-context7)
- [2. Define request/response Pydantic models](#2-define-requestresponse-pydantic-models)
- [3. Implement the handler — raise `AppError`, never `HTTPException`](#3-implement-the-handler--raise-apperror-never-httpexception)
- [4. Register any new failure mode as `ErrorCode`](#4-register-any-new-failure-mode-as-errorcode)
- [5. Return through `responses.ok(data)`](#5-return-through-responsesokdata)
- [6. Audit the success `data` for PII](#6-audit-the-success-data-for-pii)
- [Tests for the endpoint](#tests-for-the-endpoint)

## 1. Refresh FastAPI knowledge via context7

The features in play here are path parameters with type validation, an
async dependency for a resource pool, and a Pydantic response model.
Query for what you don't already remember accurately:

```
mcp__context7__resolve-library-id  libraryName="FastAPI"
mcp__context7__query-docs           libraryId="/fastapi/fastapi/<version>"
                                    query="async Depends with yield for resource lifecycle"
```

Skip queries you can answer from the existing project — reuse the
patterns already in the codebase.

## 2. Define request/response Pydantic models

In the route module (or a sibling `_schemas.py` if it grows):

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class ItemOut(BaseModel):
    id: UUID
    title: str
    created_at: datetime
```

**Important PII check**: if any field carries free-form user input that
shouldn't be exposed in the context this endpoint is called from
(admin tools? non-owner visitors?), project the model to omit or redact
it. For the owner of the resource it's usually fine — they typed it.

## 3. Implement the handler — raise `AppError`, never `HTTPException`

```python
from uuid import UUID
from fastapi import Depends
from .errors import AppError, ErrorCode
from .responses import ok
from .store.items import ItemRepo
from .store.pool import get_pool


async def get_repo(pool=Depends(get_pool)) -> ItemRepo:
    return ItemRepo(pool)


@app.get("/items/{item_id}")
async def get_item(
    item_id: UUID,
    repo: ItemRepo = Depends(get_repo),
):
    item = await repo.get(item_id)
    if item is None:
        raise AppError(
            ErrorCode.ITEM_NOT_FOUND,
            {"resource": "item"},
        )
    return ok(ItemOut.model_validate(item, from_attributes=True).model_dump())
```

Notes:

- `raise AppError(...)`, not `HTTPException`. The exception handler
  knows about `AppError`; `HTTPException` would route through
  FastAPI's default and produce the wrong envelope.
- The handler **returns through `responses.ok()`**. Don't return a
  `dict` directly — the envelope wrapping won't happen.
- The `params` for `ITEM_NOT_FOUND` is `{"resource": "item"}` — a
  category string, not the id. The frontend already knows the id (it's
  in the URL); echoing it back in `params` doesn't help and broadens the
  leak surface.

## 4. Register any new failure mode as `ErrorCode`

In this example `ITEM_NOT_FOUND` already exists in `error-catalog.md`.
If it didn't:

1. Add `ITEM_NOT_FOUND = "ITEM.NOT_FOUND"` to `ErrorCode`.
2. Add `ErrorCode.ITEM_NOT_FOUND: 404` to `_HTTP_STATUS`.
3. Add `errors.item.not_found: "Item not found"` to `locales/en.yaml`
   and `errors.item.not_found: "找不到項目"` to `locales/zh-TW.yaml`.
4. Add a section in `references/error-catalog.md`.

Pre-merge checklist (run mentally before opening a PR):

- [ ] `ErrorCode` enum entry exists
- [ ] `_HTTP_STATUS` entry exists
- [ ] Both locale YAMLs have the key
- [ ] `error-catalog.md` documents when to raise it
- [ ] No PII in the `params` shape

## 5. Return through `responses.ok(data)`

```python
return ok(payload)              # 200
return ok(payload, status=201)  # for create endpoints
```

The envelope, the request_id, and the `null` error block are filled
in for you. Don't construct envelopes by hand.

## 6. Audit the success `data` for PII

Walk the response shape and ask: "if a third party intercepted this,
would any field embarrass us or violate the user's expectation?"

For `GET /items/{id}`:

- `id`, `title`, `created_at` — fine.
- any free-form user content — sensitive but user-owned; the
  access-control decision happens at the auth layer (out of scope for
  the envelope contract). If the auth check is missing, that's the bug —
  not the envelope.

For a create endpoint, returning `{id, created_at}` is fine; returning
contact info back in the response is unnecessary and broadens the leak
surface (e.g. into proxy logs that capture response bodies).

## Tests for the endpoint

A minimal test set (see the sibling `testing-async-fastapi` skill):

```python
@pytest.mark.asyncio
async def test_get_item_success(client, fixture_item):
    r = await client.get(f"/items/{fixture_item.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["data"]["id"] == str(fixture_item.id)
    assert "request_id" in body


@pytest.mark.asyncio
async def test_get_item_not_found(client):
    r = await client.get("/items/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "ITEM.NOT_FOUND"
    assert body["error"]["message_key"] == "errors.item.not_found"
    assert body["error"]["params"] == {"resource": "item"}
    # The wire shape never carries a `message` field
    assert "message" not in body["error"]
```

These two tests pin the contract: success has the envelope, error has
the envelope, no leak, no `message` field on the wire.
