---
name: developing-features
description: >
  Use when building, implementing, designing, or scoping a non-trivial feature
  end-to-end — multi-file work that needs codebase exploration, clarifying
  questions, architecture choices, implementation, tests, and review. Triggers
  include "build feature X", "implement Y", "add support for Z",
  "design/scope the W system", "let's pick this up next", or any change that
  touches more than one or two files or has underspecified requirements. Runs a
  disciplined multi-phase loop with parallel read-only subagents for exploration
  and architecture, structured multiple-choice questions at every decision gate,
  TDD-first implementation, and a fan-out quality review. Skip for typo fixes,
  single-line bugs, urgent hotfixes, formatting-only changes, trivial dependency
  bumps, or single-file doc edits — those need no multi-phase loop and the
  orchestration is pure overhead. Keywords: feature development, implementation
  plan, architecture, clarifying questions, parallel subagents, code review, TDD,
  multi-phase, scope, design.
---

# Developing features

A disciplined, multi-phase loop for building a non-trivial feature end-to-end:
**Discover → Explore → Clarify → Architect → Implement → Review → Summarize.**
You are the *orchestrator*: you fan out read-only subagents for the parallel
phases, read what they surface, talk to the user at every real decision gate,
write the code yourself, and keep a visible task tracker as the single source of
truth for progress.

This skill is agent-agnostic. It describes the workflow in terms of three generic
capabilities your agent must provide:

- **Subagent dispatch** — launch parallel, read-only worker agents and read their
  reports (Claude Code: multiple `Agent` tool calls in one message).
- **Structured questions** — ask the user multiple-choice questions and wait for
  the answer (Claude Code: `AskUserQuestion`).
- **Task tracking** — a visible, updatable task list the user can watch (Claude
  Code: `TaskCreate` / `TaskUpdate`).

If your agent lacks one of these, emulate it as closely as you can (e.g. present
numbered options inline and wait; keep a checklist in your messages). The
methodology does not *require* any specific tool — only the disciplines below.

> **On Claude Code**, a richer command-driven version of this loop ships as the
> `feature-dev` plugin (`/feature-dev`), with dedicated explorer and architect
> subagents. This skill is the portable, agent-agnostic equivalent — use it on
> any agent, or when you want the methodology without the slash command.

## When NOT to fire

Work **directly**, skip the loop entirely, for:

- Single-line bug fixes
- Typo corrections
- Formatting-only / lint-only changes
- Urgent hotfixes where speed beats process
- Trivial dependency bumps
- Pure documentation edits inside a single file

The seven-phase loop is overhead the user did not ask for. If you are unsure
whether a request is "non-trivial", the tell is: **does it touch more than one
or two files, need a design choice, or have underspecified behavior?** If yes,
run the loop. If no, just do it.

## Two load-bearing disciplines

These two are what make the loop work. Everything else is scaffolding.

1. **Ask at every decision gate, with structured choices — never as prose.**
   At each gate (Phases 1, 3, 4, 6) surface 2–4 concrete, mutually-exclusive
   options and *wait* for the user to pick. Plain-prose questions lose the
   choice UI and force the user to retype; they also tempt you to assume an
   answer and march on. Put your recommendation first and label it
   `(Recommended)`. Most agents auto-append an "Other" free-form fallback — rely
   on it rather than hand-rolling one. Batch related questions (≈4 max per ask);
   split into multiple asks if you have more.

2. **Keep a visible task tracker — one item per phase.** Open the full
   seven-item list at the start of Phase 1 so the user sees the whole plan. Mark
   a phase in-progress on entry and completed on exit. When a phase fans out
   (Phase 2 explorers, Phase 4 architects, Phase 6 reviewers), spawn a child item
   per dispatched subagent so the parallelism is visible. This list — not prose
   status updates — is how the user knows where you are.

## The loop at a glance

| Phase | Goal | Subagents | Asks user? |
|---|---|---|---|
| 1 Discovery | Capture request; surface problem/goal/constraints | — | yes (if unclear) |
| 2 Exploration | Understand relevant existing code & patterns | 2–3 explorers (parallel) | — |
| 3 Clarify | Resolve every ambiguity **before** designing | — | **yes (critical)** |
| 4 Architecture | Design 2–3 framings; choose one *with* the user | 2–3 architects (parallel) | yes |
| 5 Implementation | Build it, TDD-first where it fits | — | (approval gate) |
| 6 Quality review | Review the diff across dimensions | reviewers (parallel) | yes (triage) |
| 7 Summary | What was built, decisions, files, follow-ups | — | — |

For per-phase prompt wording, dispatch tips, and the review-dimension hand-off,
see `references/phase-playbook.md`.

---

## Phase 1 — Discovery

**Goal:** understand what needs to be built.

1. **Open the task tracker** — one item per phase, in order, Phase 1 marked
   in-progress immediately.
2. If the request is unclear, ask one batch of structured questions covering:
   the problem being solved, what the feature must do (acceptance criteria),
   constraints (deadline, scope, performance, compatibility), and non-goals.
   Provide 2–4 sensible options per question.
3. Summarize your understanding and confirm before moving on.
4. For a load-bearing feature (touches core control flow, schema, deploy
   topology, or spans multiple phases), write the plan to a durable location and
   reference it. For smaller features, keep the plan in-conversation. When in
   doubt, file it.

No subagents in this phase.

## Phase 2 — Codebase exploration

**Goal:** understand the relevant existing code and patterns, high and low level.

1. Dispatch **2–3 explorer subagents in parallel**, each targeting a *different*
   aspect — similar existing features / overall architecture / a specific
   subsystem / UI or extension points. Each is **read-only** and must return a
   list of 5–10 key files to read. (See the playbook for prompt templates.)
2. **When they return, *you* read the files they identified.** Their summaries
   are not a substitute for reading the actual code — the later phases depend on
   the context you build here.
3. Present a comprehensive summary of the patterns you found.

## Phase 3 — Clarifying questions

**Goal:** fill every gap before designing. **This is the most important phase. DO
NOT SKIP IT.**

1. Cross-reference the Phase 2 findings against the original request.
2. Hunt for underspecified aspects: edge cases, error handling, integration
   points, scope boundaries, design preferences, backward compatibility,
   performance, i18n, accessibility, testing depth.
3. **Ask with structured choices — never as prose.** 2–4 options per question,
   each a distinct choice; recommendation first, tagged `(Recommended)`; short
   1–3 word header chips. Use multi-select only when choices truly aren't
   mutually exclusive. Batch into 2–3 topic groups if you have many questions.
4. **Wait for answers before designing.** If the user picks free-form, treat the
   typed answer as authoritative; if it's itself ambiguous, ask one more
   structured question rather than falling back to prose.

No subagents in this phase.

## Phase 4 — Architecture design

**Goal:** produce 2–3 implementation approaches with different trade-offs, then
choose one *with* the user.

1. Dispatch **2–3 architect subagents in parallel**, each with a *different*
   framing:
   - **Minimal-change** — smallest diff, maximum reuse of existing patterns.
   - **Clean** — maintainability, well-factored abstractions.
   - **Pragmatic** — speed + quality balance.
   Each is read-only and returns a blueprint: files to create/modify, component
   responsibilities, data flow, and a build sequence.
2. Form your own opinion on the best fit (weigh size, urgency, complexity).
3. Cross-check every approach against the project's stated conventions and any
   documented anti-patterns; drop an approach that violates them and say so.
4. Present to the user: a brief summary of each approach, a trade-offs
   comparison, **your recommendation with reasoning**, the concrete files each
   would touch, and **which project conventions/skills each touched area routes
   into** (see Phase 5).
5. **Ask the user which approach to take**, recommended one first. Wait for an
   explicit selection before Phase 5.

## Phase 5 — Implementation

**Goal:** build the feature.

**DO NOT START WITHOUT EXPLICIT USER APPROVAL OF THE CHOSEN ARCHITECTURE.**

You (the orchestrator) implement inline — there is no implementer subagent.

1. Wait for explicit approval of the Phase 4 choice.
2. Re-read the files identified in Phases 2 and 4.
3. **Route each touched area to whatever project conventions or skills apply.**
   Before writing in an area with an established convention (a framework
   surface, a test layout, an infra/CI directory, a specific subsystem), load
   and follow that project's skill/convention for it. Skills evolve and live
   closer to the code than your training data — trust them on conflict.
4. **Use TDD where it fits** — write the failing test first, run it, *watch it
   fail*, then write the minimal code to pass. Don't skip the "watch it fail"
   step. (Where your environment offers a dedicated TDD discipline, defer to it.)
5. Follow codebase conventions strictly. Keep commits small — one logical change
   per commit — and update the task tracker as you go.

## Phase 6 — Quality review

**Goal:** ensure the change is correct, free of silent failures, well-tested, and
elegant.

1. **Run the test suite first.** Include the run summary in each reviewer's
   prompt alongside the diff.
2. **Pre-stage the diff.** Read-only reviewers usually can't run `git diff`
   themselves, so *you* capture the diff once and paste it inline into each
   reviewer's prompt. Chunk by file/directory if it's large.
3. **Dispatch reviewer subagents in parallel**, one per review dimension.
   **Delegate the dimensions to the sibling `reviewing-code` skill** — it owns
   the catalog (correctness, hidden/silent failures, test coverage, type design,
   comments/docstrings, simplification). Add a dimension only when the diff
   warrants it (e.g. type-design review only if types are introduced; comment
   review only if docstrings/comments change; a simplification pass only if the
   user wants polish).
4. **Aggregate** findings into one summary bucketed by severity (Critical /
   Important / Suggestions / Strengths) with a recommended action order.
5. **Ask the user how to proceed** — e.g. `Fix now (Recommended)`,
   `Fix critical only`, `Defer all`, `Proceed as-is` — and act on their choice.
   Re-run the relevant reviewers after fixes.

## Phase 7 — Summary

**Goal:** document what was accomplished.

1. Mark all tasks complete.
2. Summarize: what was built (one paragraph); key decisions and why; files
   modified (grouped by directory); suggested next steps.
3. Offer a follow-up only when a natural trigger exists (a flag/rollout to
   evaluate, a new monitor to triage, a "remove once X" TODO, a soak window to
   verify). Skip the offer for plain refactors, tested bug fixes, or when the
   user signalled closure.

---

## Notes for the orchestrator

- **All explorer, architect, and reviewer subagents are read-only.** They produce
  maps, blueprints, and findings; *you* read code, design, implement, and act on
  findings.
- **Parallel dispatch matters.** Phases 2, 4, and 6 each launch all their
  subagents in a single batch. Sequential dispatch wastes wall-clock time.
- **Project conventions are the source of truth.** This skill names *when* to
  route into them; it does not duplicate their content. On conflict, the closer
  artifact (a documented architecture decision, then a project skill) wins.
- **The two disciplines are non-negotiable.** Skipping the structured-question
  gate or the visible tracker "for speed" is a regression — both surfaces are how
  the user stays in control of the work.

## Related skills

- `reviewing-code` — owns the Phase 6 review dimensions; delegate to it.
- `writing-skills` — for authoring or editing skills (including this one).
- `agents-md` — for repo-level agent operating manuals that these conventions
  plug into.
