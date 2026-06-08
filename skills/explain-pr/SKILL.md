---
name: explain-pr
description: Use when the user wants to be walked through a PR they are about to review — produces a warm, paced orientation covering the full set of commits the branch adds on top of its base (default base `main`), with high-level architectural and behavioral/interface changes, terminal-renderable ASCII diagrams of the new flow, design decisions worth flagging, and any workarounds or compromises. Treat the reader like they've just woken up and it's still kind of fuzzy in their head and they need to get warmed up before they can start reviewing this PR. This is NOT a quality review (use a dedicated code-review skill for that); this skill explains WHAT the PR does and WHY so the user can review it themselves. Accepts an optional PR number, PR URL, or branch ref to override the default scope. Trigger phrases include "walk me through this PR", "explain this PR", "I need to review this PR, get me warmed up", "what does this PR do".
---

# Explain PR

Produce a warm walkthrough that gets a groggy reviewer ready to review a PR. The output answers "what does this change, why, and where should I look first?" — it does not flag bugs or suggest fixes.

## Determining scope

The under-review change is the set of commits that the PR adds on top of its base branch — not a single commit. Resolve scope into a `<base>..<head>` range, then read every commit in that range together.

The skill operates in one of two modes. Pick the cheapest mode that can answer the question.

### Mode A — Local branch (default)

Use this mode when the user gives no argument, or when the branch under review is already checked out locally.

1. **Resolve base.** Default to the repo's main integration branch (commonly `main`, `master`, or `develop` — detect it; don't assume). Override only if the user names a different base (e.g., a release branch, or a parent branch in a stacked-PR setup).
2. **Ensure the base is fresh.** Run `git fetch origin <base> --no-tags`. Then compare:
   - If `git rev-parse <base>` equals `git rev-parse origin/<base>`, the local base is current — use `<base>` directly.
   - If they differ, either fast-forward local `<base>` or just use `origin/<base>` for the rest of the workflow. Do not silently diff against a stale base — the range would include commits already merged into the real base, which pollutes the walkthrough.
3. **Resolve head.** Default to the current branch (`HEAD`). Override if the user names a different local branch.
4. **Compute the range.** Use `<base>..<head>` (e.g., `origin/main..HEAD`). This is "every commit on this branch not yet on base" — exactly the PR's contents.
5. **Pull material locally** (all reads are free from the local checkout):
   - `git log <base>..<head> --format=fuller` — commit messages, authors, ticket refs
   - `git diff <base>..<head>` — combined diff for all commits in the range
   - `git diff --stat <base>..<head>` — file surface area
   - Read full files from the working tree on demand for surrounding context

Prefer this mode whenever possible: file reads are free, you can grep the whole tree, and you can resolve symbols across the codebase without API budget.

### Mode B — Remote PR reference

Use this mode when the user supplies a PR number, a PR URL, or a remote branch ref that is **not** checked out locally. The user may explicitly want to inspect a PR they have not pulled, and the PR's base may not be the default branch (release branches, stacked PRs).

1. **Resolve identity from the PR**, not from local assumptions:
   ```
   gh pr view <ref> --json number,title,body,baseRefName,headRefName,baseRefOid,headRefOid
   ```
   The `baseRefName` / `headRefName` returned by GitHub are authoritative — use them as `<base>` and `<head>`.
2. **Try to localize the PR** (cheaper path): `git fetch origin pull/<n>/head:pr-<n>` followed by `git fetch origin <baseRefName>`. If both succeed, drop into Mode A using the fetched refs and stop here.
3. **Pure-remote fall-back** (only when fetching is unavailable or undesirable):
   - `gh pr diff <n>` — combined diff in one call
   - `gh api repos/{owner}/{repo}/contents/{path}?ref=<headRefOid>` — per-file content for surrounding context

Warn the user before entering the pure-remote fall-back: each surrounding-context read is a separate API call, and reading a handful of files burns noticeably more tokens than reading the same files locally. Proceed if the user confirms.

### Ambiguity

If the user's input could mean either mode (e.g., a bare branch name that exists both locally and on the remote PR list), ask one short clarifying question before fetching anything.

## Workflow

1. **Resolve scope** using the rules above. Record `<base>`, `<head>`, and the mode chosen.

2. **Gather raw material** for the resolved `<base>..<head>` range, in parallel:
   - `git log <base>..<head> --format=fuller` — commit messages, often hold the "why"
   - `git diff --stat <base>..<head>` — surface area
   - `git diff <base>..<head>` — full combined diff
   - If a PR exists for this range: `gh pr view <ref> --json title,body` for the PR description (often the richest source of "why")
   - If any commit message or PR body references an issue tracker ticket (e.g., `PROJ-1234`, `#123`) and an issue-tracker skill (such as `recipe-atlassian`) is available, fetch the ticket title + description for the original problem statement

3. **Read the actual code**, not just the diff. Pull surrounding context for any non-trivial change (the diff shows the delta, but reviewers need to understand the new behavior end-to-end). Pay attention to:
   - New public functions / endpoints / classes (interface surface)
   - Changed signatures (behavioral interface change — likely callers affected)
   - New modules / files (architectural addition)
   - Deleted code (regression risk surface)
   - Config / env / migration files (operational surface)

4. **Classify each meaningful change** into one of:
   - **Architecture** — module structure, layering, new abstractions, data flow
   - **Interface / behavior** — API surface, contracts, side effects, error semantics
   - **Design decision** — a non-obvious choice with alternatives that were rejected
   - **Workaround / compromise** — TODO, FIXME, "for now", deferred cleanup, awkward shape forced by a constraint
   - **Mechanical** — renames, formatting, test plumbing (mention briefly, don't dwell)

5. **Produce the walkthrough** in the structure below.

## Output structure

Use this exact section order. Skip a section if genuinely empty (don't fabricate workarounds). Keep paragraphs short — the reader is fuzzy-headed.

### ☕ TL;DR

Two sentences max. What changed and why. The user reads this and the rest of the doc anchors to it.

### 🗺️ Where to look first

Ordered file list, most important first. One line each: `path/to/file.py` — one-phrase reason. Cap at ~5 entries. This is the reading order, not an exhaustive list.

### 🏛️ Architectural changes

Bulleted list of structural changes only. Each bullet: what got added/moved/restructured and what role it plays. No more than 5 bullets — if there are more, group them.

### 🔌 Behavioral / interface changes

Bulleted list of changes a *caller* would notice. New endpoints, changed return shapes, new headers, new env vars, new exceptions. Mark **breaking** vs **additive** explicitly. If something is wire-visible but semantically subtle (e.g., "cookie now slides on every refresh"), say so.

### 🧭 Diagram(s)

Use **terminal-renderable ASCII** — the reader is in a CLI chat surface that does not render image-based or markup-rendered diagrams. Anything that requires a renderer (a fenced block tagged with a diagram language, an embedded SVG, etc.) will show as raw markup and be unreadable. Pick the ASCII format that best fits the change:

- **ASCII sequence diagram** — request/response or multi-actor flow. Most common for PRs touching login, auth, callback, or service-to-service flows.
- **ASCII decision tree / flowchart** — for routing decisions, branching, state transitions (e.g., "if claimed → IdP, else → password").
- **Indented tree** — for new module layout, file structure, or call hierarchy.
- **Pipe table** — for before/after comparisons (e.g., cookie behavior before vs after the PR).

Diagram guidance:
- Keep participants / nodes to ~7 or fewer. If the real flow is bigger, draw the *new* portion only and add a one-line `(... existing pre-flow elided)` note.
- Label arrows / edges with the actual function name, endpoint, or payload field from the code so the reader can grep for it.
- Use plain ASCII (`| - + > < v ^`) or Unicode box-drawing (`┌ ┐ └ ┘ │ ─ ▶`) — pick one and stay consistent within a single diagram.
- Wrap the diagram in a fenced code block so the terminal preserves alignment.

Example — sequence diagram:

```
FE              api-server      RoutingTable
 |                |                  |
 | POST /login/email                 |
 |--------------->|                  |
 |                | lookup_claim(d)  |
 |                |----------------->|
 |                |<-----------------|
 |                |   tenant_id|none |
 | 200 {auth: idp | password}        |
 |<---------------|                  |
```

Example — decision tree:

```
POST /login/email
        |
        v
  domain claimed?
   /           \
 yes            no
  |              |
  v              v
 IdP          password
```

If nothing flow-shaped changed (pure refactor, config-only PR), skip the diagram and say so in one sentence.

### 🎯 Design decisions worth noting

Each item: **Decision**, then **Why**, then **What was rejected** (if you can infer it from the code or commit message). One short paragraph each. Examples of what counts:

- Choosing a local cache vs a remote lookup
- Encoding IDs as opaque tokens vs human-readable strings
- Eager validation vs lazy
- New table vs adding a column to an existing one

If a decision is obvious or forced, don't pad. It's fine to have 0–2 items.

### 🩹 Workarounds & compromises

Things that smell like tech debt, deferred work, or shape-forced-by-constraint. Look explicitly for:

- `TODO`, `FIXME`, `HACK`, `XXX` comments added in the diff
- Conditional branches gated on a flag that's hardcoded `True`/`False`
- Duplicated logic the commit message acknowledges (e.g., "will dedupe in follow-up")
- Strange retry / sleep / catch-all-Exception patterns
- Schemas with nullable fields that "should be required eventually"
- Skipped tests, `@pytest.mark.skip`, commented-out assertions

For each: one sentence on the workaround, one sentence on **why it's acceptable for now** (deadline, depends on other team, etc.), one sentence on **what would clean it up later**.

### 👀 What to watch while reviewing

Three to five concrete things the reviewer should mentally check while reading the code. Frame as questions, not commands:

- "Does the cache invalidate when the claim changes?"
- "What happens if both the local table and the remote lookup disagree?"
- "Is the new endpoint behind the same auth class as its siblings?"

This section converts "fuzzy attention" into "directed attention" — it's the most valuable section for a groggy reviewer.

## Tone

The reader just woke up. Imagine handing them a cup of coffee.

- **Lead with TL;DR.** They should know the gist before they finish their first sip.
- **Short paragraphs, short sentences.** No walls of text.
- **Bold the keywords** in dense lists so eyes can skim.
- **Cite file:line** when pointing at something specific so they can click.
- **Friendly, not cute.** "Here's what's going on" beats "Buckle up!". No emoji storms — the section headers already have one each, that's enough.
- **Don't editorialize quality.** "This is a clever trick" or "this looks risky" is review work, not warmup work. Just describe.

## Anti-patterns

Avoid these — they make the walkthrough useless:

- **Restating the diff line-by-line.** The reader can read the diff. Add interpretation, not transcription.
- **Listing every file touched.** Mechanical files (lockfile bumps, formatter churn) belong in one sentence at the end, not the "Where to look first" list.
- **Making up rationales.** If the commit message and code don't explain *why*, say "rationale not stated in commit" — don't invent one.
- **Drawing a diagram of the unchanged system.** The diagram must show the new/changed flow. If nothing flow-shaped changed, skip the diagram and say so.
- **Treating it as a quality review.** Don't flag bugs, don't suggest improvements, don't rate code quality. This skill orients; the user reviews.

## Quick checklist before sending

- [ ] TL;DR is ≤ 2 sentences
- [ ] At least one ASCII diagram (or an explicit "no flow-shaped change" note)
- [ ] Design decisions section has *why*, not just *what*
- [ ] Workarounds section actually scans the diff for TODO/FIXME/HACK
- [ ] "What to watch" is phrased as questions
- [ ] Total length is digestible — if it's longer than the diff itself, cut it down
