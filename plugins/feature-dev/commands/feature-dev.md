---
description: "Guided feature development with codebase understanding, architecture focus, and explicit user-confirmation gates at each major transition"
argument-hint: "Optional feature description"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task", "TaskCreate", "TaskUpdate", "AskUserQuestion"]
---

# Feature Development

You are helping a developer implement a new feature. Follow a systematic approach: understand the codebase deeply, identify and ask about all underspecified details, design elegant architectures, then implement.

## Core Principles

- **Ask clarifying questions**: Identify all ambiguities, edge cases, and underspecified behaviors. Ask specific, concrete questions rather than making assumptions. Wait for user answers before proceeding with implementation. Ask questions early (after understanding the codebase, before designing architecture).
- **Understand before acting**: Read and comprehend existing code patterns first.
- **Read files identified by agents**: When launching agents, ask them to return lists of the most important files to read. After agents complete, read those files to build detailed context before proceeding.
- **Simple and elegant**: Prioritize readable, maintainable, architecturally sound code.
- **Track every phase as a task**: At Phase 1, create one task per phase via `TaskCreate`. Whenever you enter a phase, immediately `TaskUpdate` it to `in_progress`. Whenever you finish a phase (before presenting the next gate, or before moving to the next phase if there is no gate), `TaskUpdate` it to `completed`. Never leave a finished phase as `pending`.
- **Reuse domain skills**: During design and implementation, prefer invoking any installed domain skill whose `description` matches the topic (e.g. a framework or API skill) over re-deriving patterns from raw codebase greps. Let the available skills catalog be the source of truth — do not hard-code a skill list.

## Checkpoint Gate Protocol

This workflow has **3 checkpoint gates**, all *before* implementation begins. After Gate 3, implementation, tests, and the quality review run automatically without further approval gates. At each gate you MUST stop, summarize where you are, and present the gate as an `AskUserQuestion` tool call. Never pose a gate in plain prose — always use the tool so the user gets explicit multiple-choice options.

Standard gate options:
- **Proceed** — advance to the next phase.
- **Modify** — user provides feedback; re-run the current phase with their input appended.
- **Cancel** — halt cleanly, summarize completed work, and exit the workflow.

Some gates add a context-specific fourth option (noted inline). The `AskUserQuestion` tool automatically offers "Other" for free-form input — do not add it yourself. Put the recommended option first and suffix its label with `(Recommended)`. Keep the `header` field ≤ 12 characters.

Each gate prints a fixed header line: `✋ CHECKPOINT [N/3] — <phase name>` followed by a 3–8 line summary of what was just produced and what the next phase will do. The `AskUserQuestion` call immediately follows the summary. Do not proceed until the user has answered.

**Status discipline at every gate**: before the summary, `TaskUpdate` the phase you just finished to `completed`. After the user selects `Proceed`, `TaskUpdate` the next phase to `in_progress` before doing any work in it. This keeps the task list a faithful record of progress.

---

## Phase 1: Discovery

**Goal**: Understand what needs to be built.

Initial request: $ARGUMENTS

**Actions**:
1. Create one task per phase via `TaskCreate`, then immediately `TaskUpdate` Phase 1 to `in_progress`.
2. If the feature is unclear, ask the user for:
   - What problem are they solving?
   - What should the feature do?
   - Any constraints or requirements?
3. Summarize understanding and confirm with the user.
4. `TaskUpdate` Phase 1 to `completed` right before presenting CHECKPOINT [1/3].

---

### ✋ CHECKPOINT [1/3] — Ready to explore the codebase?

Summarize the feature intent in 3–5 bullets. Then call `AskUserQuestion`:

- **question**: "Ready to launch `code-explorer` agents to map the relevant parts of the codebase?"
- **header**: "Explore?"
- **options**:
  - `Proceed (Recommended)` — launch the explorer agents now
  - `Modify intent` — refine the feature intent before exploring
  - `Cancel` — exit the workflow

---

## Phase 2: Codebase Exploration

**Goal**: Understand relevant existing code and patterns at both high and low levels.

**Actions**:
1. Launch 2-3 `code-explorer` agents in parallel. Each agent should:
   - Trace through the code comprehensively and focus on getting a comprehensive understanding of abstractions, architecture, and flow of control.
   - Target a different aspect of the codebase (e.g. similar features, high-level understanding, architectural understanding, user experience).
   - Include a list of 5-10 key files to read.

   **Example agent prompts**:
   - "Find features similar to [feature] and trace through their implementation comprehensively"
   - "Map the architecture and abstractions for [feature area], tracing through the code comprehensively"
   - "Analyze the current implementation of [existing feature/area], tracing through the code comprehensively"
   - "Identify UI patterns, testing approaches, or extension points relevant to [feature]"

2. Once the agents return, read all files identified by the agents to build deep understanding.
3. Present a comprehensive summary of findings and patterns discovered.

---

## Phase 3: Clarifying Questions

**Goal**: Fill in gaps and resolve all ambiguities before designing.

**CRITICAL**: This is one of the most important phases. DO NOT SKIP.

**Actions**:
1. Review the codebase findings and original feature request.
2. Identify underspecified aspects: edge cases, error handling, integration points, scope boundaries, design preferences, backward compatibility, performance needs.
3. **Present questions to the user.** When a question has a small discrete set of answers (≤ 4 options), ask it via `AskUserQuestion` — you may batch up to 4 questions in a single tool call. For open-ended questions that need free-form text, a plain prose list is fine.
4. **Wait for answers before proceeding to architecture design.**

If the user says "whatever you think is best", provide your recommendation and get explicit confirmation (also via `AskUserQuestion` when options are enumerable).

---

### ✋ CHECKPOINT [2/3] — Ready to design architectures?

Summarize the answered clarifying questions and remaining open items (if any). Then call `AskUserQuestion`:

- **question**: "Clarifications captured. Ready to launch `code-architect` agents to design 2–3 candidate architectures?"
- **header**: "Design?"
- **options**:
  - `Proceed (Recommended)` — launch the architect agents
  - `Modify clarifications` — tweak answers before designing
  - `Cancel` — exit the workflow

---

## Phase 4: Architecture Design

**Goal**: Design multiple implementation approaches with different trade-offs.

**Actions**:
1. Launch 2-3 `code-architect` agents in parallel with different focuses: minimal changes (smallest change, maximum reuse), clean architecture (maintainability, elegant abstractions), or pragmatic balance (speed + quality).
2. Every architecture proposal MUST be a **complete plan** covering all three change categories:
   - **Source code changes** — files to add/modify, functions/classes affected, data flow, integration points.
   - **Documentation changes** — README / AGENTS.md / inline-doc / API-spec / comment updates, or an explicit "no doc change needed" with reasoning.
   - **Test changes** — files to add/extend, which fixtures/factories/helpers to reuse, what edge cases to cover.
   Gate 3 approves the whole plan; there are no later gates to re-approve docs or tests separately.
3. Review all approaches and form your opinion on which fits best for this specific task (consider: small fix vs large feature, urgency, complexity, team context).
4. Present to the user: a brief summary of each approach (all three change categories), a trade-offs comparison, **your recommendation with reasoning**, and concrete implementation differences.
5. **Ask the user which approach they prefer via `AskUserQuestion`.** Each candidate architecture is one option; put the recommended one first with the `(Recommended)` suffix. Use the `preview` field when a short code/diagram snippet helps the user compare options side-by-side.

---

### ✋ CHECKPOINT [3/3] — Architecture selected. Ready to implement?

This is the **final gate** before autonomous execution. After `Proceed`, Phase 5 (implementation: source code + docs + tests) and Phase 6 (quality review) run without further gates — so the approved plan must fully cover source-code, documentation, and test changes.

After the user has picked an architecture, call `AskUserQuestion`:

- **question**: "Architecture `[name]` selected. Proceed with implementation (source + docs + tests) and automated code review exactly to this plan?"
- **header**: "Implement?"
- **options**:
  - `Proceed (Recommended)` — execute the full plan, then auto-run the review
  - `Modify design` — tweak the chosen plan (code, docs, or tests) before implementing
  - `Cancel` — exit the workflow

---

## Phase 5: Implementation

**Goal**: Execute the complete plan approved at Gate 3 — source code, documentation, and tests — in one phase.

**DO NOT START WITHOUT USER APPROVAL FROM CHECKPOINT [3/3]**

**Actions**:
1. Read all relevant files identified in previous phases.
2. **Source code**: implement exactly per the plan. Follow codebase conventions (`AGENTS.md`, `CLAUDE.md`, linter/formatter config). Invoke any relevant installed domain skill when its topic applies. Comment policy: no WHAT comments, only non-obvious WHY.
3. **Documentation**: apply the doc changes from the plan (README / AGENTS.md / API spec / inline docs). Skip only if the plan explicitly said no doc change is needed.
4. **Tests**: write tests per the approved test plan using the project's existing test conventions (fixtures, factories, mocked external services). Run the tests locally — do not advance to review with failing tests.
5. Update todos as you progress.
6. Summarize at the end: source files changed, doc files changed, tests added/updated, local test-run result.

---

## Phase 6: Quality Review

**Goal**: Delegate review to a single canonical review workflow — no duplicated selection logic, no duplicated output format.

**Actions**:

1. If the companion **`pr-review`** plugin is installed, invoke its `/review-pr all parallel` command automatically once Phase 5 completes — no gate precedes this. `/review-pr` handles applicable-agent selection, parallel launch, structured aggregation (Critical / Important / Suggestions / Strengths), and a recommended action plan. If `pr-review` is not available, do a focused inline review of the diff for correctness, security, tests, and clarity instead.

2. Relay the review summary back to the user, then call `AskUserQuestion` to decide next steps:

   - **question**: "How do you want to proceed on the review findings?"
   - **header**: "Findings?"
   - **options**:
     - `Fix issues` — loop back into Phase 5 scoped to the flagged issues, then re-run the review on affected aspects
     - `Defer` — record open items in the Phase 7 summary and advance without fixing
     - `Proceed as-is` — advance without changes (user acknowledges any Critical findings)
     - `Cancel` — exit the workflow

3. If the user chose `Fix issues`, iterate until the review returns no Critical or Important issues, or the user switches to `Defer` / `Proceed as-is`.

Any changes to the review matrix, output format, or agent list belong in the `pr-review` plugin — not here.

---

## Phase 7: Summary

**Goal**: Document what was accomplished.

**Actions**:
1. Mark all todos complete.
2. Summarize:
   - What was built
   - Key decisions made (at each checkpoint)
   - Files modified
   - Test coverage added
   - Review findings addressed vs deferred
   - Suggested next steps

---
