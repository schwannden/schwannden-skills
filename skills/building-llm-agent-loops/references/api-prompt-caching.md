# API reference: prompt caching

Prompt caching is the single biggest cost lever in a chat loop. Done right,
input tokens drop sharply from turn 2 onward. Done wrong, the cache silently
misses on every turn and your bill shows it.

**Authoritative doc**: <https://docs.claude.com/en/docs/build-with-claude/prompt-caching>

For guidance across model versions / SDKs, the built-in **`claude-api`** skill
also helps. This file focuses on the loop-specific mechanics.

## Table of contents

- [Mental model](#mental-model)
- [The setup](#the-setup)
- [TTL choice](#ttl-choice)
- [What invalidates the cache](#what-invalidates-the-cache)
- [Verifying cache hits](#verifying-cache-hits)
- [Debugging recipe](#debugging-recipe)
- [What not to cache](#what-not-to-cache)

---

## Mental model

A prompt-cache breakpoint is set by adding `cache_control: {"type":
"ephemeral"}` to a content block. Anthropic hashes that block — and **all
blocks before it** — to form the cache key. On a hit you pay a cheap cache-read
rate; on a miss you pay a slightly-higher cache-write rate.

Block order in a request, earliest to latest:

1. `system` (the system prompt)
2. `tools`
3. `messages` (the conversation)

So a breakpoint on the system block caches **system + tools** together. A
breakpoint on the last `messages` element caches the whole conversation up to
that point. A request supports up to **4 breakpoints**, but each adds
maintenance surface. For a short chat, only the first breakpoint matters: cache
system + tools. Conversations are short enough that caching the messages tail
is a marginal win.

---

## The setup

```python
SYSTEM = [
    {"type": "text", "text": SYSTEM_PROMPT,
     "cache_control": {"type": "ephemeral"}},
]

async with client.messages.stream(
    model=MODEL,
    system=SYSTEM,
    tools=TOOLS,            # constant — see rule 1
    messages=history,
    max_tokens=2048,
) as stream:
    ...
```

Two things to verify:

1. **`SYSTEM` is a list of blocks** with `cache_control` on the block. A bare
   string (`system="..."`) bypasses caching entirely.
2. **`TOOLS` is the same constant on every call.** A hit requires
   byte-identical preceding content (system + tools).

---

## TTL choice

`cache_control: {"type": "ephemeral"}` defaults to a 5-minute TTL. You can set
`ttl: "1h"` for one hour. Use 5m for chat: visitor sessions are typically
minutes, and 5m covers continuity comfortably. The 1-hour TTL costs more at
write time; reads are cheap regardless of TTL. For a chat shape, 5m wins.

```python
"cache_control": {"type": "ephemeral"}            # default — typical
"cache_control": {"type": "ephemeral", "ttl": "1h"}  # only with a reason
```

---

## What invalidates the cache

Any of these produces a cache miss:

- The `system` text changes by even one character.
- The `tools` array's serialized form changes — including reordering,
  adding/removing entries, or mutating any field.
- The `model` string changes.
- The `cache_control` block's TTL or position changes.
- More than the TTL elapses since the last cache write.

The first two are by far the most common in practice. If a developer adds a
"user locale" interpolation into the system prompt, or a feature flag that
conditionally registers `web_search`, the cache silently dies.

---

## Verifying cache hits

Every response includes a `usage` block:

```python
final.usage
# Usage(
#     input_tokens=42,
#     cache_creation_input_tokens=0,
#     cache_read_input_tokens=1842,
#     output_tokens=120,
# )
```

- `cache_creation_input_tokens`: tokens paid at the cache-write rate. Set on
  the turn that *populates* the cache.
- `cache_read_input_tokens`: tokens paid at the cache-read rate. Set on every
  subsequent hit.
- `input_tokens`: the *uncached* portion (tokens after your breakpoint, plus new
  tokens that didn't fit).

**Healthy steady state from turn 2 onward:**

- `cache_read_input_tokens` ≈ token count of (system + tools).
- `cache_creation_input_tokens` = 0.
- `input_tokens` = small (the new user message and any new history).

If `cache_creation_input_tokens` is non-zero on every turn, your inputs aren't
stable. Check tools, then system, then model.

---

## Debugging recipe

Symptom: cost higher than expected, suspected cache misses.

1. Log `usage` on every turn. Look at the creation:read ratio.
2. If creation > 0 every turn: dump the exact `system` and `tools` bytes you're
   sending and hash them. Compare across turns; find the variable that changes.
3. Common culprits, in order of likelihood:
   - `f"...{some_var}"` in `SYSTEM_PROMPT`.
   - `tools` reconstructed each turn from a function (order/repr may differ).
   - `cache_control` placed on a block other than the *last* system block.
   - Model env-var pointing somewhere different per environment.
4. If `cache_read_input_tokens` is set but lower than expected, the breakpoint
   only caches part of the system — move it to the last system block.

---

## What not to cache

- **Per-turn user messages**: ephemeral, low value.
- **The conversation tail**: at a handful of turns, history isn't long enough
  to pay for the breakpoint overhead. Add a second breakpoint on the last
  message only for much longer conversations or a long-form RAG surface.
- **`*_tool_result` blocks**: they live inside the assistant message
  mid-`messages`; a per-turn breakpoint rarely pays off.

---

## Cross-references

- Stable tools list as cache invariant: [`../SKILL.md`](../SKILL.md)
- Cache-killing patterns: [anti-patterns.md](anti-patterns.md)
