# Phase playbook — prompts, dispatch tips, and the review hand-off

## Table of contents
- [How to read this file](#how-to-read-this-file)
- [Generic capability mapping](#generic-capability-mapping)
- [Phase 1 — Discovery: question templates](#phase-1--discovery-question-templates)
- [Phase 2 — Exploration: explorer prompts](#phase-2--exploration-explorer-prompts)
- [Phase 3 — Clarify: how to shape choices](#phase-3--clarify-how-to-shape-choices)
- [Phase 4 — Architecture: architect prompts](#phase-4--architecture-architect-prompts)
- [Phase 5 — Implementation: routing & TDD](#phase-5--implementation-routing--tdd)
- [Phase 6 — Review: dispatch & aggregation](#phase-6--review-dispatch--aggregation)
- [Phase 7 — Summary: shape](#phase-7--summary-shape)

## How to read this file

`SKILL.md` is the authoritative workflow. This file is reference material: copy
the prompt templates, adapt the bracketed placeholders, and discard what doesn't
fit the task. Nothing here is mandatory wording — it's a starting point so you
don't reinvent the prompts each time.

## Generic capability mapping

The workflow needs three capabilities. Map them to whatever your agent provides:

| Capability | What it does | Claude Code example |
|---|---|---|
| Subagent dispatch | Launch parallel read-only workers; read their reports | multiple `Agent` calls in one message |
| Structured questions | Multiple-choice ask; wait for a pick | `AskUserQuestion` |
| Task tracking | Visible, updatable phase checklist | `TaskCreate` / `TaskUpdate` |

If a capability is missing: for dispatch, do the exploration/architecture/review
yourself but still vary the *framing* across passes; for questions, present
numbered options inline and stop until answered; for tracking, keep an explicit
checklist in your replies.

## Phase 1 — Discovery: question templates

One batch, up to ~4 questions, 2–4 options each:

- **Problem** — "What problem does this solve?" Options framed as candidate user
  pains, plus free-form.
- **Acceptance** — "What must be true for this to be done?" Options as candidate
  acceptance criteria.
- **Constraints** — "Any hard constraints?" Options: deadline / performance
  budget / backward-compat / none.
- **Non-goals** — "Anything explicitly out of scope?" Options as candidate
  exclusions.

Then restate your understanding in one short paragraph and confirm.

## Phase 2 — Exploration: explorer prompts

Dispatch 2–3 in parallel, each a *different* angle. Each must return 5–10 key
files to read. Read-only.

- "Find features similar to [feature] and trace their implementation end to end —
  entry points, control flow, data storage. Return the 5–10 files most essential
  to understanding it."
- "Map the architecture and abstractions for [area]: layers, module boundaries,
  cross-cutting concerns (auth/logging/caching). Return the key files."
- "Analyze the current implementation of [existing feature/area] comprehensively.
  Return the key files."
- "Identify the UI patterns / testing approach / extension points relevant to
  [feature]. Return the key files."

Ask each explorer for: entry points with `file:line`, step-by-step flow,
component responsibilities, dependencies, and the essential file list. **After
they return, read those files yourself** before Phase 3.

## Phase 3 — Clarify: how to shape choices

- One concern per question. 2–4 mutually-exclusive options. Recommendation
  first, tagged `(Recommended)`.
- Short header chip (1–3 words), e.g. `Storage`, `Auth`, `Scope`, `PR shape`.
- Multi-select only when options genuinely co-exist (e.g. "which scanners to
  add").
- Group many questions into 2–3 topic batches (storage/infra, security/policy,
  scope/PR-shape) rather than one giant ask.
- If the user free-forms an answer, it's authoritative — don't re-ask. If it's
  ambiguous, ask one more structured question, never prose.

Dimensions worth probing: edge cases, error handling, integration points, scope
boundaries, design preferences, backward compatibility, performance, i18n,
accessibility, testing depth.

## Phase 4 — Architecture: architect prompts

Dispatch 2–3 in parallel with distinct framings. Read-only. Each returns a
blueprint.

- **Minimal-change:** "Design the smallest change that delivers [feature],
  reusing existing patterns maximally. List files to modify, component
  responsibilities, data flow, build sequence, and trade-offs."
- **Clean:** "Design the most maintainable, well-factored approach for [feature].
  Same deliverables."
- **Pragmatic:** "Design a balanced speed-vs-quality approach for [feature]. Same
  deliverables."

Before presenting: cross-check each blueprint against documented project
conventions/anti-patterns; drop any that violates them and say which and why.

Present a comparison table (approach / effort / risk / files touched), your
recommendation with reasoning, and the project conventions each touched area
routes into. Then ask the user to choose; wait for an explicit pick.

## Phase 5 — Implementation: routing & TDD

- **Route by touched area.** Before writing in an area that has an established
  convention — a framework surface, the test directory, infra/CI, a specific
  subsystem — load and follow that area's project skill/convention. Don't
  duplicate its content here; defer to it.
- **TDD where it fits.** Write the failing test → run it → *watch it fail* →
  write the minimal code to pass → refactor. Skipping "watch it fail" is the most
  common way a test silently never exercises the new code. Where your environment
  has a dedicated TDD discipline, defer to it.
- **Small commits.** One logical change per commit; update the task tracker as
  each phase task completes.

## Phase 6 — Review: dispatch & aggregation

1. Run the test suite; capture the summary.
2. Capture `git diff` (and staged diff) once — reviewers are read-only and often
   can't run it. Paste it inline into each reviewer prompt; chunk by file or
   directory if large.
3. Dispatch reviewers in parallel, one per dimension. **The dimension catalog
   lives in the sibling `reviewing-code` skill — delegate to it** rather than
   re-listing criteria here. Typical dimensions: correctness, hidden/silent
   failures, test/behavioral coverage, type design (only if types are
   introduced), comments/docstrings (only if they change), and a simplification
   pass (only on request).
4. Aggregate into one summary:

   ```
   # Review summary
   ## Critical (N)
   - [dimension]: issue [file:line]
   ## Important (N)
   - [dimension]: issue [file:line]
   ## Suggestions (N)
   - [dimension]: suggestion [file:line]
   ## Strengths
   - what's well done
   ## Recommended action
   1. Fix critical  2. Address important  3. Consider suggestions  4. Re-run
   ```

5. Ask the user how to proceed (`Fix now (Recommended)` / `Fix critical only` /
   `Defer all` / `Proceed as-is`). Act, then re-run the relevant reviewers.

## Phase 7 — Summary: shape

- What was built — one paragraph.
- Key decisions and why — the gate choices the user made.
- Files modified — grouped by directory.
- Suggested next steps / follow-ups — only if a natural trigger exists.
