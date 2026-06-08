# Dependencies

Run from your API package root. Use `uv` — never `pip install`, never
global. (See the sibling `uv` skill.)

## Runtime

```bash
uv add fastapi 'uvicorn[standard]' pydantic-settings sse-starlette pyyaml
```

Add any project-specific runtime deps (database driver, HTTP/SDK
clients, etc.) separately, e.g. `uv add asyncpg` or `uv add httpx`.

## Dev

```bash
uv add --dev pytest pytest-asyncio httpx pytest-cov ruff
```

`ruff` is a good default linter and formatter; one tool covers what
`flake8 + isort + black` used to. A small `[tool.ruff]` block keeps the
config discoverable:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["B", "SIM"]
```

`pytest-cov` lets `uv run pytest --cov` work out of the box; treat
coverage as a diagnostic, not necessarily a CI gate.

## Pinning FastAPI

Before pinning a specific version, refresh against context7:

```
mcp__context7__resolve-library-id  libraryName="FastAPI"
```

The output lists the latest known versions. Pick the highest stable
one and pin in `pyproject.toml`:

```toml
fastapi = ">=0.128,<0.129"
```

If the project's existing `pyproject.toml` already pins a version,
**don't downgrade silently** — confirm with the user before bumping
or pinning a different range.

## Why each dep

| Package | Why |
|---|---|
| `fastapi` | The framework |
| `uvicorn[standard]` | ASGI server with the optional speedups (uvloop, httptools) |
| `pydantic-settings` | Typed env-var loading |
| `sse-starlette` | `EventSourceResponse` for SSE streaming endpoints |
| `pyyaml` | Reading the locale YAMLs |
| `pytest`, `pytest-asyncio`, `httpx` | Tests, including async client |
| `pytest-cov` | Coverage reporting — diagnostic only |
| `ruff` | Linter + formatter |

`sse-starlette` is only needed if you have streaming endpoints; drop it
otherwise.
