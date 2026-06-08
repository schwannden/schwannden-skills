# Architecture patterns — agent loop deep dive

Long-form companion to the SKILL.md "five rules". If the rules tell you *what*
to do, this file explains *how* a thin loop is built and *why*. Read it when
designing a non-trivial change to the loop, the tools list, or persistence —
not for a one-line edit.

## Table of contents

- [The thin loop (~25 lines)](#the-thin-loop-25-lines)
- [Server-tool registration](#server-tool-registration)
- [Client-tool dispatch (the two-phase pattern)](#client-tool-dispatch-the-two-phase-pattern)
- [Persistence: tool blocks as the analytics dataset](#persistence)
- [System prompt structure](#system-prompt-structure)
- [Cross-references](#cross-references)

---

## The thin loop (~25 lines)

The whole point of this design is that the loop fits on a screen and is still
correct. Canonical shape (paths are illustrative):

```python
# api/agent/loop.py
async def run_turn(
    client: AsyncAnthropic,
    history: list[MessageParam],
    user_text: str,
) -> AsyncIterator[StreamEvent]:
    history = history + [{"role": "user", "content": user_text}]

    for _ in range(MAX_LOOP_ITERATIONS):  # cap, e.g. 3
        async with client.messages.stream(
            model=MODEL,
            system=SYSTEM,            # cached: cache_control ephemeral
            tools=TOOLS,              # constant — see rule 1
            messages=history,
            max_tokens=2048,
        ) as stream:
            async for event in stream:
                for sse in translate_to_sse(event):
                    yield sse
            final = await stream.get_final_message()

        history.append(final.to_message_param())

        if final.stop_reason == "end_turn":
            return
        if final.stop_reason == "pause_turn":
            continue
        if final.stop_reason == "tool_use":
            tool_results = await dispatch_client_tools(final)
            history.append({"role": "user", "content": tool_results})
            continue
        raise UnexpectedStopReason(final.stop_reason)

    raise LoopBudgetExceeded(MAX_LOOP_ITERATIONS)
```

**What this loop is doing**: in any given turn, the model may search and/or
fetch one or more pages *inside a single API call* — those tool steps happen on
Anthropic's side, so you don't see them as separate loop iterations. They show
up as `server_tool_use` and `*_tool_result` content blocks in the final
assistant message. The only reasons your loop *iterates* are:

1. **`tool_use` for your client tool** — the model wants something only your
   code can do. You dispatch it, append the `tool_result`, and re-enter.
2. **`pause_turn`** — the model hit the `max_uses` budget on a server tool
   mid-flight. You re-enter with the partial assistant message in history;
   Anthropic continues from where it left off.

Anything else (`end_turn`, an unrecognized reason) ends the turn or errors. The
iteration cap is a tripwire — in practice you rarely hit even 2.

---

## Server-tool registration

The `TOOLS` constant is defined once and imported wherever the loop runs.
Defining it once (and only once) is what makes the prompt cache hold across
turns; see [api-prompt-caching.md](api-prompt-caching.md).

```python
# api/agent/tools.py
from typing import Final

ALLOWED_DOMAINS: Final = ["example.com", "www.example.com"]

TOOLS: Final = [
    {
        "type": "<current web_search type>",  # verify dated id in live docs
        "name": "web_search",
        "max_uses": 5,
        "allowed_domains": ALLOWED_DOMAINS,
    },
    {
        "type": "<current web_fetch type>",   # verify dated id in live docs
        "name": "web_fetch",
        "max_uses": 5,
        "allowed_domains": ALLOWED_DOMAINS,
        "citations": {"enabled": True},
        "max_content_tokens": 20_000,
    },
    {
        "name": "book_appointment",
        "description": (
            "Example custom client tool: signal that the user wants to book "
            "an appointment so your code can handle the booking. Replace with "
            "your app's one custom tool."
        ),
        "input_schema": {
            "type": "object",
            "required": ["topic", "message"],
            "properties": {
                "name": {"type": "string"},
                "contact": {"type": "string"},
                "topic": {"type": "string"},
                "message": {"type": "string"},
            },
        },
    },
]
```

**Notes on each entry:**

- The two server tools (`web_search`, `web_fetch`) use Anthropic's built-in
  implementations. You write no dispatch code for them; they execute on
  Anthropic infrastructure, scoped by `allowed_domains`.
- `max_uses: 5` per tool means the model can perform up to 5 searches *and* up
  to 5 fetches per turn (not combined). This is your hard upper bound on
  per-turn cost.
- `citations.enabled: true` on `web_fetch` makes the model emit
  `web_search_result_location` blocks — see [api-citations.md](api-citations.md).
- `book_appointment` is a *client tool*: it has a `name` and an `input_schema`
  but no `type`. You dispatch it yourself via `dispatch_client_tools`. In your
  app this is whatever single custom tool you expose.

**Don't add a `cache_control` entry to any individual tool object** — the cache
key covers the entire `tools` array. Putting `cache_control` inside one tool is
a no-op at best and a footgun at worst.

---

## Client-tool dispatch (the two-phase pattern)

When `stop_reason == "tool_use"`, the only client tool here is
`book_appointment`. A useful pattern for tools whose result arrives
asynchronously (the user must fill out a form, confirm, etc.) is **render then
submit**:

```python
# api/agent/tools.py (continued)
async def dispatch_client_tools(
    final: Message,
) -> list[ToolResultBlockParam]:
    results: list[ToolResultBlockParam] = []
    for block in final.content:
        if block.type != "tool_use":
            continue
        if block.name != "book_appointment":
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": [{"type": "text", "text": f"unknown tool: {block.name}"}],
                "is_error": True,
            })
            continue
        # The "result" here is a placeholder; the real result arrives
        # asynchronously when the user submits the form. We tell the model
        # the form was rendered, then on submit we re-issue the turn with
        # the actual data.
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": [{"type": "text", "text": "form rendered to user"}],
        })
        # Side-effect: emit a UI event to the client.
        await emit_sse({
            "event": "form_required",
            "data": {"tool_use_id": block.id, "prefill": block.input},
        })
    return results
```

The two-phase shape matters because the user has to act. The "I rendered the
form" acknowledgement keeps the loop terminable — the model can write a holding
sentence ("I'll get that set up") and end the turn. When the user submits, you
persist the data, then trigger a synthetic continuation so the model can write
a graceful closing message.

**Every `tool_use` block must have a matching `tool_result`** in the next user
message — the API rejects continuations that leave a tool call unanswered. If a
tool fails, return `is_error: true` rather than silently skipping it.

---

## Persistence

If you want analytics or an audit trail, don't filter or summarize tool blocks
at write time — the raw form is the dataset.

```python
# api/store/conversations.py
async def insert_assistant_turn(conn, conversation_id, final: Message) -> None:
    text_blocks  = [b for b in final.content if b.type == "text"]
    tool_calls   = [b.model_dump(mode="json") for b in final.content
                    if b.type in ("tool_use", "server_tool_use")]
    tool_results = [b.model_dump(mode="json") for b in final.content
                    if b.type in ("tool_result",
                                  "web_search_tool_result",
                                  "web_fetch_tool_result")]
    text = "".join(b.text for b in text_blocks)
    await conn.execute(
        """INSERT INTO messages
               (id, conversation_id, role, content, tool_calls, tool_results, created_at)
           VALUES ($1, $2, 'assistant', $3, $4::jsonb, $5::jsonb, NOW())""",
        uuid4(), conversation_id, text,
        json.dumps(tool_calls), json.dumps(tool_results),
    )
```

**What lives in the JSONB:**

- `server_tool_use` blocks — every search query the model formed, every URL it
  chose to fetch.
- `web_search_tool_result` — the URL lists search returned (the candidate set).
- `web_fetch_tool_result` — the URLs actually fetched, with `citations` blocks
  if `web_fetch.citations.enabled = true`.
- The `usage.server_tool_use` summary — per-turn rollup of how many
  searches/fetches were billed.

This is also how you **debug retrieval quality** in production: if a user
reports "the bot couldn't find X", inspect the row to see what the model
actually searched for. `block.model_dump(mode="json")` is Pydantic v2's
JSON-safe dump.

---

## System prompt structure

Keep the system prompt as a module-level string constant. Carve it into
clearly-labelled sections — models follow headed instructions far better than a
wall of prose. A working skeleton:

```python
# api/agent/prompts.py
SYSTEM_PROMPT = """\
You are a helpful assistant for <your app>.

# Knowledge sourcing

For any factual claim about the product/service, use the `web_search` tool
first (scoped automatically to your domain). Cite the URL inline. If search
returns nothing relevant, say so honestly — do not speculate.

# Refusals

- Out-of-scope requests: redirect politely back to what you can help with.
- Anything requiring a human / a booking: trigger the custom tool.

# Custom-tool trigger

Trigger `book_appointment` when the user expresses concrete intent to book or
needs a human follow-up.

# Style

- Concise, suited for a chat widget — keep paragraphs short.
- Cite sources as inline links beneath the relevant sentence.
"""
```

**Why structured headings**: each section is independently inspectable and
removable, so you can edit one (e.g. refusal language) without disturbing
others. When you change *anything* here, the prompt cache invalidates — that's
expected; it rebuilds on the next turn.

**What does NOT belong in the system prompt**: anything per-conversation or
per-user. Locale, conversation id, prior-topic summaries — those go in
`messages`, not `system`. Interpolating per-turn variables into the system
block silently invalidates the cache on every turn.

---

## Cross-references

- The five rules: [`../SKILL.md`](../SKILL.md)
- Anti-pattern rationale: [anti-patterns.md](anti-patterns.md)
- Cache mechanics: [api-prompt-caching.md](api-prompt-caching.md)
- Stop reasons: [api-tool-use-loop.md](api-tool-use-loop.md)
- Server-tool reference: [api-server-tools.md](api-server-tools.md)
