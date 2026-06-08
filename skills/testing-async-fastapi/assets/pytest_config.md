# pytest config block

READ THIS, then drop the block into your API `pyproject.toml`. Everything is
wired so `uv run pytest` Just Works without flags.

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
pythonpath = ["src"]      # so `from api.main import app` resolves
addopts = [
    "-ra",                # short summary for failures
    "--strict-markers",
    "--strict-config",
    "-m", "not live_llm",
]
markers = [
    "live_llm: hits the real LLM — deselected by default; nightly CI only",
    "slow: mark a test as slow (>1s); deselected via `-m 'not slow'` for fast loops",
]
```

## Notes

- **`asyncio_mode = "auto"`** is what removes the `@pytest.mark.asyncio`
  noise from every test. Don't drop it.
- **`asyncio_default_fixture_loop_scope = "function"`** matches what most
  fixtures want. The DB session fixtures in `conftest.py` override to
  `loop_scope="session"` explicitly where they need to outlive a single
  test.
- **`pythonpath = ["src"]`** assumes a `src/`-layout package. Adjust if your
  package isn't under `src/`.
- **`-m "not live_llm"`** in `addopts` belt-and-suspenders the marker filter.
  The `pytest_collection_modifyitems` hook in `conftest.py` is the primary
  defense; this is the second line so a user-passed `-m` doesn't accidentally
  include them.
- **`--strict-markers`** turns typos in `@pytest.mark.foo` into errors at
  collection time. Worth its weight in saved debugging.
- **`--strict-config`** does the same for pyproject typos.

## Coverage (optional)

If you want a coverage report on every run:

```toml
[tool.pytest.ini_options]
# ... as above, plus:
addopts = [
    "-ra", "--strict-markers", "--strict-config",
    "-m", "not live_llm",
    "--cov=src/api", "--cov-report=term-missing",
]
```

Treat coverage as a **diagnostic for hot spots**, not a CI gate. A gate of
"X%" tends to push tests toward gaming coverage rather than testing
behaviour.
