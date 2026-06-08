# API reference: citations from `web_search` / `web_fetch`

Citations are not optional. Per the Anthropic [`web_search`][cite-doc] and
[`web_fetch`][fetch-doc] docs, **when displaying API output to end users,
citations from `web_search_result_location` blocks must be surfaced.** That's a
contractual obligation, not a stylistic suggestion. If your UI collapses
citations behind a "show sources" disclosure that defaults closed, you're out
of compliance with the API terms. This file documents the wire shape coming out
of the loop; rendering them is your frontend's job.

[cite-doc]: https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-search-tool
[fetch-doc]: https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-fetch-tool

## Table of contents

- [How citations are produced](#how-citations-are-produced)
- [The block shape](#the-block-shape)
- [Streaming citation blocks](#streaming-citation-blocks)
- [Persistence](#persistence)
- [Common mistakes](#common-mistakes)

---

## How citations are produced

Citations are emitted automatically when:

- `web_fetch` is registered with `citations: {"enabled": True}`, and
- the model's text references content from a fetched page.

Each citation attaches to a span of assistant `text` and points to the source
URL it grounded in. You don't write code to generate them; you write code to
**not lose them**.

---

## The block shape

In the final assistant message, citations appear as
`web_search_result_location` blocks interleaved with `text` blocks:

```python
final.content = [
    {"type": "text", "text": "Beginner classes run on Wednesday mornings, "},
    {
        "type": "web_search_result_location",
        "url": "https://www.example.com/classes/beginner",
        "title": "Beginner classes",
        "cited_text": "...Wednesday mornings from 9am...",
        "encrypted_index": "<opaque>",
        # Character-range fields (e.g. start_char_index / end_char_index /
        # message_index) may also be present — verify names against the live
        # doc before consuming. Required fields: url / title / cited_text /
        # encrypted_index.
    },
    {"type": "text", "text": "and are open to all ages."},
]
```

Field meanings:

- `url`: the source page (always within `allowed_domains`).
- `title`: the source page's `<title>` (or fetch-tool best guess).
- `cited_text`: the fragment that grounded the claim. Used for hover-preview
  and auditing.
- `encrypted_index`: opaque string Anthropic uses to reference the citation
  across multi-turn conversations. Persist it verbatim; don't decode or modify.
- (Optional) character-range fields anchor the citation to a span in the
  preceding text block. Field names are documented in the [citations
  doc][live-cite] — don't speculate on names that may drift.

[live-cite]: https://docs.claude.com/en/docs/build-with-claude/citations

`cited_text`, `title`, `url`, and `encrypted_index` do **not** count toward
input/output token usage — free to include and free to forward.

---

## Streaming citation blocks

Citations arrive in the stream as their own content blocks:

```
content_block_start { type: "text", index: 0 }
content_block_delta { delta: { type: "text_delta", text: "..." } }
content_block_stop  { index: 0 }
content_block_start { type: "web_search_result_location", index: 1 }
content_block_stop  { index: 1 }   // usually a single chunk
content_block_start { type: "text", index: 2 }
```

In `translate_to_sse` (see [api-streaming.md](api-streaming.md)), emit a
`citation` SSE event on `content_block_stop` for `web_search_result_location`
blocks. The client receives them *after* the text they belong to — that's
expected; the char-range fields are how it back-anchors a marker into
already-displayed text.

---

## Persistence

Citation blocks are part of the assistant message's content, so they go into
your JSONB along with every other non-text block:

```python
tool_results = [b.model_dump(mode="json") for b in final.content
                if b.type in ("tool_result",
                              "web_search_tool_result",
                              "web_fetch_tool_result",
                              "web_search_result_location")]
```

Preserve them for two reasons: an **audit trail** (a future "did our bot make
this claim?" needs the URL + fragment), and **analytics** (citation density per
turn measures retrieval grounding).

---

## Common mistakes

- **Stripping citations during a "clean up" pass**. Someone writes
  `text = "".join(b.text for b in content if b.type == "text")` and the
  citation blocks are gone. Persist the full `content` list.
- **Dropping `cited_text`** to "save bandwidth". The fragment is small and the
  audit value is high.
- **Embedding citations in the text** as inline `[1]` markers + footer. This
  loses the structured form. Keep them as structured events on the wire and let
  the frontend render.

---

## Cross-references

- Server-tool registration with `citations.enabled`: [api-server-tools.md](api-server-tools.md#web_fetch)
- SSE event protocol: [api-streaming.md](api-streaming.md)
