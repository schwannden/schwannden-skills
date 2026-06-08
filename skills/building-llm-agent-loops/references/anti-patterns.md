# Anti-patterns — what not to do, and why

Each item corresponds to a checkbox in the SKILL.md anti-pattern checklist. The
rationale matters as much as the rule: most of these silently degrade cost or
correctness without throwing a visible error, so understanding the failure mode
is what lets you catch adjacent variants the checklist doesn't enumerate.

## Table of contents

- [Dynamic tools[] membership across turns](#dynamic-tools-membership-across-turns)
- [Missing allowed_domains](#missing-allowed_domains)
- [Cache control missing on the system block](#cache-control-missing-on-the-system-block)
- [Per-turn variables interpolated into the system block](#per-turn-variables-interpolated-into-the-system-block)
- [Tool blocks not persisted](#tool-blocks-not-persisted)
- [pause_turn falling through](#pause_turn-falling-through)
- [max_uses set without a cost model](#max_uses-set-without-a-cost-model)
- [Client-managed conversation history](#client-managed-conversation-history)
- [Citations stripped before reaching the user](#citations-stripped-before-reaching-the-user)
- [Exceptions escaping to the stream](#exceptions-escaping-to-the-stream)
- [API keys committed to the repo](#api-keys-committed-to-the-repo)
- [Premature migration to the Agent SDK](#premature-migration-to-the-agent-sdk)

---

## Dynamic `tools[]` membership across turns

**Symptom**: input-token cost higher than expected from turn 2 onward.
`usage.cache_read_input_tokens` is consistently 0 even though
`cache_creation_input_tokens` was set on turn 1.

**Why**: prompt-cache breakpoints key on the *exact* bytes of cached content
(system + tools at the same breakpoint). Conditionally registering `web_search`
only when the user message contains certain keywords invalidates the cache on
every other turn. Same for reordering, adjusting `max_uses` per turn, or
dynamically generating tool descriptions.

**Fix**: define `TOOLS` as a module-level `Final` constant. Pass the same
reference every turn. If you genuinely need conditional behavior, push the
conditional into the system prompt's instructions or into a single tool that
branches internally on its inputs.

---

## Missing `allowed_domains`

**Symptom**: probably none in development. In production, eventually a fetched
page contains a URL pointing off-domain, the model considers it (it's now "in
context"), and either fetches it or includes it in an answer.

**Why it matters**: `web_fetch` cannot synthesize URLs from training data, but
it *can* fetch any URL that has appeared in conversation context — user
messages, prior search results, or links inside a previously fetched page. A
prompt-injection attack would aim to plant a URL that looks helpful. Without
`allowed_domains`, that URL becomes fetchable.

**Fix**: pin both `web_search` and `web_fetch` to your own domain(s). This is a
**security control**, not a performance knob. The cost of forgetting it is much
higher than the inconvenience of opt-in-only domains.

---

## Cache control missing on the system block

**Symptom**: `cache_creation_input_tokens` is high every single turn. You're
paying full freight for the system prompt repeatedly.

**Why**: caching is opt-in per content block. If you write `system="..."` (a
bare string) instead of the structured
`[{"type": "text", "text": "...", "cache_control": {...}}]` form, nothing is
cached.

**Fix**:
```python
system = [
    {"type": "text", "text": SYSTEM_PROMPT,
     "cache_control": {"type": "ephemeral"}},
]
```
Verify by reading `usage.cache_creation_input_tokens` (set once) and
`usage.cache_read_input_tokens` (set on every subsequent turn).

---

## Per-turn variables interpolated into the system block

**Symptom**: cache write happens *every* turn — `cache_creation_input_tokens`
set every time instead of just once.

**Why**: someone added `f"...the user's locale is {locale}..."` to the system
string. Even a one-character change — timestamps, conversation ids, prior-topic
summaries — invalidates the cache.

**Fix**: anything per-conversation goes into the **first user message** of
`messages`, not into `system`. The system block should be identical across all
conversations on the same model.

---

## Tool blocks not persisted

**Symptom**: analytics dashboards have nothing useful. You can see *that* a
search happened but not *what* was searched or *which* URL was returned.

**Why**: the assistant message has many block types (`text`, `tool_use`,
`server_tool_use`, `web_search_tool_result`, `web_fetch_tool_result`). A naive
`text = "".join(b.text for b in content if hasattr(b, "text"))` writes the
visible answer but loses the rest. Or a "clean up" pass dropped
"non-displayable" blocks before persisting.

**Fix**: persist `tool_calls` (every `tool_use` / `server_tool_use`) and
`tool_results` (every `tool_result` / `web_search_tool_result` /
`web_fetch_tool_result`) as raw JSONB via `block.model_dump(mode="json")`. See
[architecture-patterns.md](architecture-patterns.md#persistence).

---

## `pause_turn` falling through

**Symptom**: occasionally a turn ends with a half-finished assistant message —
the model trails off mid-sentence.

**Why**: `stop_reason == "pause_turn"` means the model hit the server-tool
`max_uses` budget mid-flight and *paused*. It is not an error. If your loop
only handles `end_turn` and `tool_use` and treats everything else as terminal,
this is what you'll see.

**Fix**: explicitly handle `pause_turn` by re-issuing the API call with the
partial assistant message in `messages`. The model picks up where it left off.
Cap re-entries (e.g. 3); if it can't finish, raise the loop-budget exception.

```python
if final.stop_reason == "pause_turn":
    continue  # re-enter with history including the partial turn
```

See [api-tool-use-loop.md](api-tool-use-loop.md).

---

## `max_uses` set without a cost model

**Symptom**: month-end bill is surprising; you can't tell which conversations
drove the spike.

**Why**: someone bumped `max_uses` from 5 to 20 because "a complex question
needed more searches", without doing the math. More searches + more fetched
tokens can multiply per-turn cost, and the increase is invisible until billing.

**Fix**: anchor `max_uses` to a per-turn cost ceiling. If you raise the limit,
write the new ceiling in a comment in `tools.py`. Log the per-turn
`usage.server_tool_use` counts and alert on outliers. Check current per-search
and per-token pricing via the `claude-api` skill.

---

## Client-managed conversation history

**Symptom**: the client sends an array of prior messages on every POST.
Conversations break on browser refresh; users can spoof prior context to bypass
refusal heuristics; analytics can't tell what the model actually saw.

**Why**: it's the obvious shape if you've built a chat UI before. But it
bypasses the database, breaks across tabs, and is a security hole.

**Fix**: the client sends only `{ conversation_id, message }`. The server
reloads the last N messages from storage and assembles `messages` itself.
Set the `conversation_id` server-side; the frontend never manages it.

---

## Citations stripped before reaching the user

**Symptom**: users can't see where a claim came from — and you're in violation
of the Anthropic display obligation.

**Why**: a "clean up" pass over the streaming text filtered out anything
looking like markup or metadata. Citation blocks attach to text spans via
character offsets — collapsing structured content to a plain string loses them.

**Fix**: forward citation blocks to the client as their own SSE events. Keep
the original message-index / char-range pairs intact. See
[api-citations.md](api-citations.md).

---

## Exceptions escaping to the stream

**Symptom**: occasionally the connection dies mid-stream with no `error` event;
the client shows a blank reply.

**Why**: the `except` chain around the loop doesn't cover every path the SDK
can raise — connection errors, status errors, the `TypeError` the SDK raises
when the API key is unset, or an unexpected exception — so one escapes to the
streaming writer and aborts the connection.

**Fix**: wrap the whole stream so that *no* exception escapes. Catch the SDK's
connection / status errors, catch the unset-key `TypeError`, re-raise
`AssertionError` so test fixtures still surface, and add a final catch-all that
emits a structured error event. Pin it with tests that assert each path yields
an `error` event rather than an aborted stream. See
[api-streaming.md](api-streaming.md#error-handling).

---

## API keys committed to the repo

**Symptom**: GitHub's secret scanner emails you 30 minutes after the push.

**Why**: `.env` got staged because someone ran `git add -A` from the wrong
directory.

**Fix**: never commit `.env`; keep it gitignored. In production, mount
`ANTHROPIC_API_KEY` from a secret store; in dev use a gitignored `.env.local`.
If a key lands in git, **rotate it immediately** — the moment a key is in
public history, treat it as compromised.

---

## Premature migration to the Agent SDK

**Symptom**: more code than before, no new functionality, some bugs that didn't
exist in the old loop.

**Why**: someone read the Claude Agent SDK docs and got excited about the
abstractions. But with *one* client tool, the Agent SDK costs you a layer of
indirection without a payoff at that scale — it's built for cases with multiple
tools, complex permission gates, and multi-step orchestration.

**Fix**: don't migrate until you have at least ~3 client tools and genuinely
complex dispatch. Re-read the graduation criteria in
[`../SKILL.md`](../SKILL.md#graduation-when-to-leave-this-shape) before changing
direction.
