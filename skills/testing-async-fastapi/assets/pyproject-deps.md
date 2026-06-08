# Test dependencies

READ THIS, then run the commands from your API project root.

```bash
uv add --dev pytest pytest-asyncio httpx pytest-cov
```

Optional but recommended for full-suite runs:

```bash
uv add --dev pytest-xdist          # parallel workers; needs the per-worker DB recipe in references/db-strategy.md
```

`asyncpg` is assumed to already be a runtime dependency. Tests reuse the same
driver — there's no separate test driver to install. See the built-in `uv`
skill for dependency-management details.

## What each one is for

| Package | Why it's pinned to dev |
|---|---|
| `pytest` | Test runner. Standard. |
| `pytest-asyncio` | Lets you write `async def test_...` directly. Configured with `asyncio_mode = "auto"` so you don't sprinkle `@pytest.mark.asyncio`. |
| `httpx` | The `AsyncClient` + `ASGITransport` used for HTTP tests. Already a runtime dep if the app uses it elsewhere. |
| `pytest-cov` | Coverage reporting. Use for spotting holes; not a CI gate. |
| `pytest-xdist` | Optional. `pytest -n auto` parallelises by file across CPU cores; pairs with the per-worker test DB pattern in `references/db-strategy.md` § "Parallelism". |

## Versions

Don't pin versions in your test scaffolding — `uv add --dev <pkg>` lets uv
pick the latest compatible release at install time, then `uv.lock` records
exactly what the team is on. When in doubt about a feature working across
versions, ask context7:

```
mcp__context7__resolve-library-id  libraryName="pytest-asyncio"
mcp__context7__query-docs          libraryId="<resolved>"
                                   query="loop scope session for module fixtures"
```
