# Mode: Autopilot — design end-to-end

Produce a complete reference design by walking the full backbone, after
gathering real facts in parallel.

## Step 1 — Fan out research (parallel, when there's anything to look up)

When the design depends on facts you can check — current capabilities/limits of
a candidate technology, real production numbers, what already exists in a
codebase — gather them concurrently before designing. Dispatch parallel
read-only subagents (see `superpowers:dispatching-parallel-agents` if installed).
Each returns findings, not opinions.

| Agent | Job | Tooling |
|---|---|---|
| Currency | Confirm current capabilities/limits/new features for the candidate technologies; return doc URLs + a trade-off per choice. | `recipes/fundamentals-over-products.md` |
| Numbers | Pull the real numbers the design needs (QPS, p99, DAU/MAU, data volumes). | `recipes/capacity-and-numbers.md` |
| Source trace | Map what already exists in the codebase for this area (models, flows). | a code-exploration subagent |

Skip an agent only if its input is irrelevant (e.g. a greenfield system with no
production data yet) and say so. For a pure thought-experiment with nothing to
look up, design directly from first principles.

## Step 2 — Compose the reference design

Walk the backbone (`SKILL.md`) and emit, in order. Pull the matching
`guides/NN-*.md` as an exemplar if the problem is a known archetype.

1. **Scope** — functional + non-functional, cuts named.
2. **Non-functional requirements table** — metric | target | reasoning, with
   real numbers from research.
3. **Capacity (worked)** — show the math; flag the numbers that drove choices.
4. **API** — code block.
5. **Data model** — key entities and the load-bearing fields.
6. **Architecture** — ASCII box-and-arrow diagram.
7. **Deep dives** — the 2–3 hardest components in full depth.
8. **Consistency / CAP** — committed choice per path.
9. **Cost** — $/mo table with the named dominator.
10. **Failure modes & blast radius** — table: failure | blast radius | behavior.
11. **Operability** — SLOs, key metrics/logs, deploy + rollback, on-call burden.
12. **Evolution at 10×** — seams that change vs don't; own vs delegate.
13. **Verdict** — from `rubric.md`, with named open items.

Reach for `recipes/design-patterns.md` primitives wherever they fit.

## Step 3 — Offer to persist and hand off

The doc is **not** saved by default. Offer: (a) write it to a doc file or a
Confluence page (use `recipe-atlassian`), and (b) hand off to the
`developing-features` skill (or a `/feature-dev` command if installed) if it's
becoming real work.
