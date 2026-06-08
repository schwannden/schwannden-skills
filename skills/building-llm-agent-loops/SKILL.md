---
name: building-llm-agent-loops
description: |
  Use when writing, debugging, or reviewing a thin agent loop on the
  Anthropic Python SDK — anything importing `anthropic` / `AsyncAnthropic`,
  calling `messages.stream()` / `messages.create()`, editing a `tools` list,
  registering the `web_search` / `web_fetch` server tools or a custom
  client-side tool, handling `pause_turn` or the `tool_use` loop, placing
  prompt-cache `cache_control`, or surfacing citations. Triggers on conceptual
  questions too: server tool vs client tool, prompt cache missing or input
  cost doubling, handling pause_turn, adding a tool without breaking the
  cache, or when to move to the Claude Agent SDK. Covers the
  stable-`TOOLS`-constant invariant, `allowed_domains` as a prompt-injection
  control, `cache_control: ephemeral` placement, verbatim persistence of
  `server_tool_use` / `*_tool_result` blocks, the `stop_reason` dispatch
  matrix, the streaming context-manager pattern, and citation handling. For
  model ids / pricing / API params see the `claude-api` skill; for Python
  deps the `uv` skill.
---

# Building LLM agent loops (Anthropic Python SDK)

A thin agent loop on the Anthropic Python SDK is **deliberately small** — about
25 lines of orchestration — because retrieval can live inside Anthropic's
infrastructure (`web_search` + `web_fetch` server tools) instead of your
process. Your code only iterates when the model calls one of *your* custom
client-side tools, or when a server tool pauses for budget.

This skill encodes the load-bearing decisions for building that loop well. The
examples use a single illustrative custom client tool, `book_appointment` — in
your app it is whatever one tool your loop dispatches. File paths like
`api/agent/loop.py` are illustrative, not prescriptive; put the code wherever
your project structure puts it.

## First action: refresh against the live docs

The Anthropic API moves quickly and training data lags. **Before you write or
modify code that touches a specific feature, fetch the current doc for it.**
The version-dated tool identifiers below (`web_search_<date>`,
`web_fetch_<date>`) change; the docs are authoritative.

| Topic | URL |
|---|---|
| `web_search` server tool | <https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-search-tool> |
| `web_fetch` server tool | <https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-fetch-tool> |
| Tool use overview & `stop_reason` | <https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview> |
| Prompt caching | <https://docs.claude.com/en/docs/build-with-claude/prompt-caching> |
| Streaming messages | <https://docs.claude.com/en/api/messages-streaming> |
| Citations | <https://docs.claude.com/en/docs/build-with-claude/citations> |
| Claude Agent SDK overview (graduation) | <https://docs.claude.com/en/api/agent-sdk/overview> |

Use the built-in `claude-api` skill for the current model ids (e.g.
`claude-sonnet-4-6`, `claude-opus-4-8` are recent examples — always verify the
live list), pricing, and the **current dated version** of each server tool
identifier. Do not hard-code a dated identifier you found in a blog post or in
training data; check the doc.

## Stack — the shape this skill assumes

| Layer | Choice | Why |
|---|---|---|
| SDK | **`anthropic` Python (async)** | `AsyncAnthropic`; `messages.stream()` context manager. Not the `claude-agent-sdk` yet — see [Graduation](#graduation-when-to-leave-this-shape). |
| Server tool: search | **`web_search`** (current dated `type`) with `allowed_domains` pinned, `max_uses` capped | Live retrieval, scoped to your site, capped. |
| Server tool: fetch | **`web_fetch`** (current dated `type`) with same `allowed_domains`, `max_uses`, `citations.enabled=true`, `max_content_tokens` capped | Reads pages discovered by `web_search`; cannot synthesize URLs. |
| Custom client tool | **one** tool (e.g. `book_appointment`), fires when intent detected | The only client-side dispatch in the loop. |
| Streaming | **SSE** to your client | One token event per delta; emit non-text events as they arrive. |
| Persistence | Store `server_tool_use` + `*_tool_result` blocks **verbatim** | This is your analytics / audit dataset. |
| Prompt cache | **`cache_control: {type: "ephemeral"}` on the system block** | Large input-token reduction from turn 2; `tools[]` must stay stable for the cache to hold. |

Get the current dated `type` strings (`web_search_…`, `web_fetch_…`) from the
live docs or the `claude-api` skill before pasting any literal.

## The five rules

These are the load-bearing invariants. Violating any one is a production bug or
a quiet cost overrun.

### 1. The `tools[]` list is stable across turns

Prompt caching keys on the **exact** `tools` array (alongside `system`).
Toggling a tool's registration on or off, reordering entries, or mutating a
`max_uses` value mid-conversation invalidates the cache and **silently doubles
your input cost**. Define `TOOLS` once as a module constant; pass the same
reference on every `messages.stream()` call.

```python
# api/agent/tools.py — defined once, reused everywhere
from typing import Final

ALLOWED_DOMAINS: Final = ["example.com", "www.example.com"]

TOOLS: Final = [
    {"type": "<current web_search type>", "name": "web_search", "max_uses": 5,
     "allowed_domains": ALLOWED_DOMAINS},
    {"type": "<current web_fetch type>", "name": "web_fetch", "max_uses": 5,
     "allowed_domains": ALLOWED_DOMAINS,
     "citations": {"enabled": True}, "max_content_tokens": 20_000},
    {"name": "book_appointment", "description": "...", "input_schema": {...}},
]
```

If you find yourself wanting a per-turn conditional tool, you're fighting the
cache. Either (a) move the conditional into the system prompt, or (b) accept
the cache miss and document why.

### 2. Every server tool has `allowed_domains` pinned

`web_fetch` can only fetch URLs that already appeared in context — but "in
context" includes URLs an attacker could plant via **prompt injection** inside
a fetched page or a user message. Without `allowed_domains`, the tool would
happily follow them.

Pin both `web_search` and `web_fetch` to your own domain(s). This is a
**security control**, not a tuning knob. See
[references/anti-patterns.md](references/anti-patterns.md#missing-allowed_domains).

### 3. The system block carries `cache_control: ephemeral`

The system prompt is re-sent on every turn. Without caching that's wasted
spend; with `cache_control: {type: "ephemeral"}` on the last system block you
pay a one-time cache-write and a cheap cache-read per turn thereafter. Default
TTL is 5 minutes. Use `ttl: "1h"` only with a specific reason.

```python
system = [
    {"type": "text", "text": SYSTEM_PROMPT,
     "cache_control": {"type": "ephemeral"}},
]
```

A bare string (`system="..."`) bypasses caching entirely. Combined with rule 1,
the cache hit rate from turn 2 should be high; if it's not, something is
mutating the inputs — check
[references/api-prompt-caching.md](references/api-prompt-caching.md).

### 4. Persist every `server_tool_use` and `*_tool_result` block verbatim

If you want analytics or an audit trail, the JSONB log of every tool call the
model made is your dataset. When you write the assistant turn back to storage,
persist **all** content blocks — not just the visible text:

```python
content_blocks = response.content  # list[ContentBlock]
store.insert_message(
    role="assistant",
    text="".join(b.text for b in content_blocks if b.type == "text"),
    tool_calls=[b.model_dump(mode="json") for b in content_blocks
                if b.type in ("tool_use", "server_tool_use")],
    tool_results=[b.model_dump(mode="json") for b in content_blocks
                  if b.type in ("tool_result",
                                "web_search_tool_result",
                                "web_fetch_tool_result")],
)
```

Don't filter, summarize, or "clean up" — the raw form is the dataset. Include
the search query string, the URLs returned, the URLs the model chose to fetch,
and the `usage.server_tool_use` summary. Detail in
[references/architecture-patterns.md](references/architecture-patterns.md#persistence).

### 5. Re-issue the call when `stop_reason == "pause_turn"`

When the model hits `max_uses` on a server tool mid-flight, the response ends
with `stop_reason: "pause_turn"`. This is **not** an error and **not**
`end_turn` — it's "I had to stop, please continue me." Feed the partial
assistant turn (with all its existing `server_tool_use` / `*_tool_result`
blocks) back into `messages` and call `messages.stream()` again with the same
parameters. Treat `tool_use` (for your client tool) and `pause_turn` as the
only two stop reasons that re-enter the loop; `end_turn` finishes.

```python
while True:
    response = await stream_response(client, history, tools=TOOLS, system=system)
    history += response.content_as_messages()
    if response.stop_reason == "end_turn":
        break
    if response.stop_reason == "pause_turn":
        continue
    if response.stop_reason == "tool_use":
        history += await dispatch_client_tools(response)
        continue
    raise RuntimeError(f"unexpected stop_reason: {response.stop_reason}")
```

**Cap the loop** (e.g. 3 iterations) — if the model hasn't terminated after a
few re-entries, something is wrong (usually `max_uses` set too low for the
question). Detail in
[references/api-tool-use-loop.md](references/api-tool-use-loop.md).

## Anti-pattern checklist

Run through this before opening a PR that touches the loop. Rationale for each
lives in [references/anti-patterns.md](references/anti-patterns.md).

- [ ] **Dynamic `tools[]` membership** — same array reference on every call?
- [ ] **`allowed_domains` set** — on both `web_search` and `web_fetch`?
- [ ] **Cache control on system** — `cache_control: ephemeral` present, on the
      *last* system block?
- [ ] **Stable system prompt** — does any per-turn variable interpolate into
      the system block? (If yes: move it into `messages`.)
- [ ] **Server-tool blocks persisted** — full JSONB, not summarized?
- [ ] **`pause_turn` handled** — loop re-enters, doesn't fall through?
- [ ] **`max_uses` budgeted** — total search+fetch cost per turn known and
      acceptable?
- [ ] **No client-managed history** — the client never sends prior messages;
      the server reloads them by conversation id?
- [ ] **Citations preserved** — `web_search_result_location` blocks surfaced,
      not stripped server-side?
- [ ] **No secrets in repo** — `ANTHROPIC_API_KEY` from env / secret store only?
- [ ] **Loop catches every SDK escape path** — the `except` chain wraps the
      whole stream so that *no* exception escapes to your streaming response.
      Catch the SDK's connection / status errors, the `TypeError` the SDK
      raises when the API key is unset, re-raise `AssertionError` so test
      fixtures still surface, and add a final catch-all that emits a structured
      error event. **Never let an exception escape to the SSE writer** — the
      connection dies mid-stream with no `error` event and the client shows a
      blank reply. Pin this with tests.

## Patterns (deep dives)

Each lives under `references/`:

- [references/architecture-patterns.md](references/architecture-patterns.md) —
  The thin-loop shape, server-tool registration, client-tool dispatch with a
  two-phase (render-then-submit) example, verbatim persistence, system-prompt
  structure.
- [references/anti-patterns.md](references/anti-patterns.md) — Each checklist
  item with rationale + concrete failure mode.
- [references/api-server-tools.md](references/api-server-tools.md) — The
  `web_search` + `web_fetch` pair: schemas, limits, citation block format,
  Console gate, no-JS-rendering caveat.
- [references/api-tool-use-loop.md](references/api-tool-use-loop.md) —
  `stop_reason` matrix, `pause_turn` re-entry, `tool_use` dispatch, cap-the-loop
  heuristic.
- [references/api-prompt-caching.md](references/api-prompt-caching.md) —
  `cache_control` placement, TTL choice, what invalidates the cache, how to
  verify a hit in the response `usage` block.
- [references/api-streaming.md](references/api-streaming.md) — `messages.stream`
  context-manager pattern, event types, the final-message accessor, why
  server-tool blocks don't stream incrementally.
- [references/api-citations.md](references/api-citations.md) —
  `web_search_result_location` schema, the display obligation, how to forward
  citations on the wire.

## Graduation: when to leave this shape

The most important graduation is migrating from the raw `anthropic` SDK to the
**Claude Agent SDK** when the loop sprouts more than ~3 client-side tools.
Symptoms you've outgrown the thin loop:

- Your client-tool dispatch switch has 4+ branches.
- Tool dispatch needs retries, its own streaming, or multi-step side-effect
  orchestration.
- You're hand-rolling permission gates, intermediate state, or per-tool context
  budgeting.

When that day comes, read <https://docs.claude.com/en/api/agent-sdk/overview>
and reframe the loop as an agent definition with your existing tools attached.
The system prompt, `allowed_domains`, and persistence schema carry over
unchanged — only the **dispatch** code changes. Until then, **don't
preemptively migrate**: adding the SDK before ~3 client tools costs you a layer
of abstraction with no payoff.

## Cross-skill boundaries

This skill is narrow on purpose. Adjacent concerns:

| Concern | Skill |
|---|---|
| Current model ids, pricing, batch, extended thinking, files API, model migration | `claude-api` (built-in) |
| FastAPI route shape / error envelope around the loop | `writing-fastapi-apis` |
| Testing the async loop / streaming endpoint | `testing-async-fastapi` |
| Dockerfile / container build for the service | `dockerizing-fastapi-uv` |
| Python deps, `uv add`, running scripts | `uv` (built-in) |

If a question touches this skill and one of the above, invoke both — they're
complementary.

## What this skill is not for

- The system prompt's *content* (voice, refusal wording) — that's a content
  concern. This skill governs the system prompt's *structure* and caching.
- General Python / asyncio mechanics.
- Storage schema design beyond the JSONB columns the model writes into.
- Provider switching (Vertex / Bedrock) — usually an env-var swap.

## When in doubt

1. Fetch the live Anthropic doc for the specific feature. Don't trust training
   data on tool-version identifiers, parameter names, or field shapes.
2. Prefer the simplest thing that satisfies the five rules. If a change forces
   you to violate one, that's a signal to redesign the change, not break the
   rule.
3. Cite the doc URL in PR descriptions so future-you remembers why.
