# API reference: tool-use loop and `stop_reason`

The whole agent loop is driven by `stop_reason`. The API has a small, fixed set
of values, and your loop must dispatch on them correctly. Getting any wrong
leads to silent bugs (truncated turns, lost tool results, or runaway loops).

**Authoritative docs:**
- Tool use overview: <https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview>
- Messages API reference: <https://docs.claude.com/en/api/messages>

## Table of contents

- [The stop-reason matrix](#the-stop-reason-matrix)
- [The loop](#the-loop)
- [Continuing after pause_turn](#continuing-after-pause_turn)
- [Dispatching a tool_use for a client tool](#dispatching-a-tool_use-for-a-client-tool)
- [tool_use vs server_tool_use](#tool_use-vs-server_tool_use)
- [What about max_tokens](#what-about-max_tokens)

---

## The stop-reason matrix

Every `Message` ends with exactly one `stop_reason`:

| `stop_reason` | Means | Loop action |
|---|---|---|
| `end_turn` | The model finished cleanly. | Return; emit SSE `end`. |
| `tool_use` | The model wants a *client* tool. | Dispatch it, append `tool_result` blocks, re-enter. |
| `pause_turn` | The model hit `max_uses` on a server tool mid-flight. | Re-enter immediately; the partial assistant message is already in `messages`. |
| `max_tokens` | The `max_tokens` budget was reached. | Usually a bug — raise, or re-enter with a continuation. |
| `stop_sequence` | A custom stop sequence matched. | If you don't use stop sequences, raise `UnexpectedStopReason`. |
| `refusal` | The safety system declined to continue. | Surface a friendly error; log the input for review. |

---

## The loop

The canonical loop is in
[architecture-patterns.md](architecture-patterns.md#the-thin-loop-25-lines).
The shape that matters for stop-reason dispatch:

```python
for _ in range(MAX_LOOP_ITERATIONS):  # cap, e.g. 3
    final = await stream_one_turn(client, history, tools, system)
    history.append(final.to_message_param())

    match final.stop_reason:
        case "end_turn":
            return
        case "pause_turn":
            continue            # server tool budget hit; resume
        case "tool_use":
            tool_results = await dispatch_client_tools(final)
            history.append({"role": "user", "content": tool_results})
            continue
        case "max_tokens":
            raise OutputBudgetExceeded(...)
        case "refusal":
            raise SafetyRefusal(...)
        case other:
            raise UnexpectedStopReason(other)

raise LoopBudgetExceeded(MAX_LOOP_ITERATIONS)
```

Three points to internalize:

1. **`tool_use` and `pause_turn` are the only continuing reasons.** Anything
   else ends the turn or is an error.
2. **The cap is a tripwire, not a target.** If you hit it, your `max_uses` is
   wrong or your prompt asks for too much. Adding more iterations masks the
   problem, it doesn't fix it.
3. **`pause_turn` is normal, not exceptional.** Don't log it as an error or
   treat it as a partial failure. The user shouldn't notice it.

---

## Continuing after `pause_turn`

When `pause_turn` fires, the partial assistant message is in `final` —
including any `server_tool_use` and `*_tool_result` blocks that completed before
the budget was hit. To continue:

```python
history.append(final.to_message_param())  # carries the partial state
final = await stream_one_turn(client, history, tools, system)  # resumes
```

You don't add a "please continue" user message — the partial state in
`messages` is the continuation signal. **Do not modify the assistant message**;
resume only works because the bytes match what Anthropic remembers. If you hit
`pause_turn` more than once per turn, raise `max_uses` or simplify the question.

---

## Dispatching a `tool_use` for a client tool

When `stop_reason == "tool_use"`, walk `final.content` for `tool_use` blocks
(lowercase `tool_use`, not `server_tool_use`):

```python
async def dispatch_client_tools(final: Message) -> list[ToolResultBlockParam]:
    results = []
    for block in final.content:
        if block.type != "tool_use":
            continue
        match block.name:
            case "book_appointment":
                results.append(await handle_book_appointment(block))
            case other:
                results.append(error_result(block.id, f"unknown tool: {other}"))
    return results
```

Every `tool_use` block must have a matching `tool_result` block in the next
user message — the API rejects continuations that leave a tool call unanswered.
If a tool fails, return `is_error: true` rather than silently skipping it. The
full render-then-submit flow for an async client tool is in
[architecture-patterns.md](architecture-patterns.md#client-tool-dispatch-the-two-phase-pattern).

---

## `tool_use` vs `server_tool_use`

These look similar but trigger different paths:

- **`tool_use`** (block type) → a *client* tool. Your code dispatches it. These
  cause `stop_reason == "tool_use"`.
- **`server_tool_use`** (block type) → a *server* tool. Anthropic dispatches it
  on its side; you only see it in the final assistant message as a record of
  what happened. These do **not** cause the loop to iterate — they're
  transparent.

The string-match on `.type` is the only signal. Don't try to distinguish by
name (you could in principle have a server tool and a client tool with the same
name; uniqueness is only enforced within a request).

---

## What about `max_tokens`

If `stop_reason == "max_tokens"`, the model was truncated mid-thought. Options:

1. **Raise the bug**. Your `max_tokens` is too tight; increase it.
2. **Continue** with a "continue your previous answer" user message — fragile,
   loses atomicity, avoid in production.

If you find yourself bumping `max_tokens` for normal conversation, the system
prompt is probably encouraging too-long answers.
