# API reference: `web_search` + `web_fetch` server tools

These two tools can be your entire retrieval system. Together they let the
model search your site, then fetch full pages it found, all inside a single
`messages.create()` / `messages.stream()` call.

**Authoritative docs (always check before changing code):**
- `web_search`: <https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-search-tool>
- `web_fetch`: <https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-fetch-tool>

The version-dated `type` identifiers (`web_search_<date>`, `web_fetch_<date>`)
change over time. **Get the current dated id from the docs above or the
`claude-api` skill** before pasting a literal; bumping it requires reading the
doc and updating your `tools.py` in the same commit.

## Table of contents

- [Console gate (operational prerequisite)](#console-gate)
- [web_search](#web_search)
- [web_fetch](#web_fetch)
- [How they compose](#how-they-compose)
- [Persisting the result blocks](#persisting-the-result-blocks)
- [When this isn't enough](#when-this-isnt-enough)

---

## Console gate

Web search must be enabled by an org admin in the Claude Console privacy
settings (<https://platform.claude.com/settings/privacy>). Until that toggle is
on, every request that registers `web_search` returns an error. This is
**per-org, not per-API-key**, so flipping it once covers dev and prod under the
same Anthropic account. If you see a search-related 4xx in dev, check the
console before debugging code.

---

## `web_search`

```python
{
    "type": "<current web_search type>",
    "name": "web_search",
    "max_uses": 5,
    "allowed_domains": ["example.com", "www.example.com"],
    # Optional knobs you may not need:
    # "blocked_domains": [...],   # mutually exclusive with allowed_domains
    # "user_location": {...},
}
```

**What it does**: the model issues search queries (Anthropic-side; you don't
see them as a separate API call). Returns `web_search_tool_result` blocks
containing snippet/URL pairs.

**Knob semantics:**

- `max_uses`: hard cap on `web_search` invocations per turn. Hitting the cap
  mid-flight ends the turn with `stop_reason == "pause_turn"`; you re-issue to
  continue.
- `allowed_domains` / `blocked_domains`: mutually exclusive. Use
  `allowed_domains` to constrain search to your site only. Without it, search
  ranges over the open web.

**Result block shape** (in `final.content`):

```python
{
    "type": "web_search_tool_result",
    "tool_use_id": "srvtoolu_...",
    "content": [
        {"type": "web_search_result", "title": "...",
         "url": "https://www.example.com/...",
         "encrypted_content": "...", "page_age": "..."},
        ...
    ],
}
```

**Cost**: search requests are billed per request independently of tokens. At
`max_uses=5` the per-turn worst case is 5 search requests. Check current
pricing via the `claude-api` skill.

Newer revisions of `web_search` may support **dynamic filtering** (the model
runs code mid-search to filter results in-flight), which can improve accuracy
and reduce tokens but requires the code-execution tool registered alongside.
Check the live doc for the current revision and whether it applies to you;
swapping to it is a version bump plus adding the code-execution tool — no loop
changes.

---

## `web_fetch`

```python
{
    "type": "<current web_fetch type>",
    "name": "web_fetch",
    "max_uses": 5,
    "allowed_domains": ["example.com", "www.example.com"],
    "citations": {"enabled": True},
    "max_content_tokens": 20_000,
}
```

**What it does**: the model fetches the full HTML of a URL (server-side, on
Anthropic's infrastructure), parses it to text, and uses it to ground its
answer. Critically, it **cannot synthesize URLs** — `web_fetch` will only fetch
URLs that already appear somewhere in context (user messages, prior
`web_search_tool_result` blocks, or prior `web_fetch_tool_result` blocks). This
is why the pair (`web_search` → `web_fetch`) is necessary: search introduces
candidate URLs into context; fetch reads them.

**Knob semantics:**

- `max_uses`: per-turn cap. Same `pause_turn` semantics as `web_search`.
- `allowed_domains`: hard pin. Even if a URL ends up in context through an
  injection attempt, it cannot be fetched if it's outside this list.
- `citations.enabled`: when `true`, the model emits `web_search_result_location`
  blocks attached to its `text` blocks, anchoring claims to URLs. See
  [api-citations.md](api-citations.md).
- `max_content_tokens`: caps the size of the fetched-and-parsed page injected
  back into context. Raising it costs input tokens, not request fees.

**Result block shape:**

```python
{
    "type": "web_fetch_tool_result",
    "tool_use_id": "srvtoolu_...",
    "content": {
        "type": "document",
        "url": "https://www.example.com/...",
        "source": {"type": "text", "media_type": "text/html", "data": "..."},
        "title": "...",
        "citations": {"enabled": True},
    },
}
```

**Constraints worth knowing:**

- **No JS rendering**. `web_fetch` returns server-rendered HTML. If your site
  migrates critical content to client-side rendering, it becomes invisible to
  fetch.
- **No new URLs**. If you want the model to fetch a specific page by pattern
  (e.g. "always fetch /pricing for pricing questions"), put the exact URL in the
  system prompt or a user-facing instruction so it lands in context.
- **Fetch cost**: fetched content is charged as input tokens at the model's
  per-token rate. Check current pricing via the `claude-api` skill.

---

## How they compose

```
User: "What times are your beginner classes?"
   ↓
Model (server-side):
   web_search("beginner class schedule")
   ↓  web_search_tool_result: [3 URLs]
   web_fetch("https://www.example.com/classes/beginner")
   ↓  web_fetch_tool_result: <full page text + citations enabled>
   ↓
Model assembles answer with citations
   ↓
final.content = [
   text("Beginner classes run Wednesday mornings..."),
   web_search_result_location(url=..., cited_text="..."),
   server_tool_use(web_search, query=...),
   web_search_tool_result(...),
   server_tool_use(web_fetch, url=...),
   web_fetch_tool_result(...),
]
```

Your code never sees the search→fetch round-trip as separate API calls — it's
all inside the single `messages.stream()`. You only see the final assistant
message with all the blocks attached.

---

## Persisting the result blocks

Per [architecture-patterns.md](architecture-patterns.md#persistence), persist
all `server_tool_use` and `*_tool_result` blocks verbatim. The
`usage.server_tool_use` summary tells you *how many* of each ran; the per-block
detail tells you *what*.

---

## When this isn't enough

If retrieval quality drags — the model searches but consistently picks the
wrong page, or can't find content that exists — try these before adding a
vector store:

1. **System-prompt URL hints** — list 5-10 preferred URL paths in the
   knowledge-sourcing section so the first search is pre-biased.
2. **Tighter `allowed_domains`** — drop a redirect form; add specific subpaths
   to bias toward them.
3. **Dynamic-filtering revision** of the server tools (if available) — adds a
   code-execution step inside the search/fetch loop. Requires the
   code-execution tool registered alongside.

Don't jump to a local KB until those have been tried.
