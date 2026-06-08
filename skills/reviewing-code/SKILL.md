---
name: reviewing-code
description: Use when reviewing a pull request or diff, after implementing a feature, or before committing or merging — "review this code", "check my changes", "is this PR ready". Applies a multi-dimension review methodology across six lenses (correctness/logic bugs, silent failures and error handling, test coverage, type design, comment accuracy, and simplification) over the changed code, with confidence-based filtering and adversarial verification so only high-signal, high-impact findings surface and false alarms are suppressed. Separates must-fix from nice-to-have, anchors findings to the project's conventions, and can run the lenses as independent parallel passes for thorough reviews. Keywords: code review, pull request, diff, bugs, logic errors, security, silent failures, error handling, test coverage, type design, comment accuracy, simplification, confidence filtering, adversarial verification.
---

# Reviewing code

A single, portable methodology for reviewing a code change. It distills six
distinct review **lenses** into one discipline. A reviewer applies each lens to
the **diff** (the changed work), gathers findings, then filters them hard so the
report carries only what matters.

This is the review step of a development workflow — pair it with the sibling
skill `developing-features` (this is its review phase). Domain examples it leans
on appear in `testing-async-fastapi` (test conventions) and `writing-fastapi-apis`
(API conventions). Adapt all examples to whatever stack you are reviewing.

> **On Claude Code**, a richer command-driven version ships as the `pr-review`
> plugin (`/review-pr`), with one specialist subagent per lens run in parallel
> and findings aggregated by severity. This skill is the portable, agent-agnostic
> equivalent — use it on any agent, or for a single-pass review without the command.

## When to use

- Reviewing a PR or a diff someone hands you.
- After you finish implementing a feature, before you commit or open a PR.
- "Check my changes" / "is this ready to merge" / "review this code".

## The cardinal rules (apply to every lens)

These cross-cutting disciplines matter more than any single lens. They are what
separates a useful review from a noisy one.

1. **Review the diff, not the codebase.** Focus on changed/unstaged work unless
   told otherwise. Get the diff first (`git diff`, `git diff --staged`, or
   `git diff <base>...HEAD` for a PR). Read surrounding code only for context —
   never report pre-existing issues the change didn't introduce or touch.

2. **Verify adversarially before reporting.** For every candidate finding, try
   to **refute** it: trace the code path, check the types, look for the guard
   you might have missed, read the called function. A finding survives only if
   you cannot talk yourself out of it. **When uncertain, default to "not a real
   issue"** — a confident false positive costs more trust than a missed nit.

3. **Filter by confidence and impact.** Score each finding 0–100 on how sure you
   are it is real and consequential. **Report only ≥ 80.** Do not flood the
   review with style nits, speculative concerns, or "you could also" asides.
   Quality over quantity. If nothing clears the bar, say the code looks good.

4. **Separate must-fix from nice-to-have.** Group findings: **Critical /
   must-fix** (correctness, security, silent data loss) vs **Suggestions /
   nice-to-have** (quality, simplification, comment polish). Never bury a real
   bug under a pile of opinions.

5. **Anchor to the project's conventions.** If the project ships a style guide,
   `CLAUDE.md`/`AGENTS.md`, an architecture doc, or testing/API conventions,
   cite the specific rule a finding violates (name the section). A finding
   backed by a project rule is actionable; a personal preference is noise.

6. **Be specific and constructive.** Every finding: file path + line, what's
   wrong, why it matters, and a concrete fix. Acknowledge what's done well when
   it's genuinely notable — not as filler.

## The six lenses

Each lens is one pass with one question. Apply all six (a small change may clear
several in seconds). Detailed prompts, rating rubrics, and anti-patterns for each
live in `references/dimensions.md` — read it when a lens needs depth.

| Lens | The question it asks | Reports |
|---|---|---|
| **1. Correctness / logic** | Will this code do the wrong thing? Real bugs, logic errors, race conditions, async/await mishaps, security holes, convention violations. | High-confidence bugs only (≥ 80). |
| **2. Silent failures** | Could an error here be swallowed, masked, or hidden? Empty/over-broad catches, errors logged-and-continued, bad fallbacks, inappropriate defaults, dropped async exceptions. | Anything that turns a failure into invisible wrong behavior. |
| **3. Test coverage** | Do the tests actually exercise the new behavior and its edge cases — or are they vacuous? | Critical gaps + brittle/meaningless tests. |
| **4. Type design** | Do the types make illegal states unrepresentable and enforce their invariants? | Qualitative read + a simple rating; pragmatic fixes only. |
| **5. Comment accuracy** | Do the comments tell the truth, and will they stay true? Lies, rot, over-documentation that becomes debt. | Comments that mislead or add no lasting value. |
| **6. Simplification** | Can this be simpler without changing behavior? Dead code, duplication, needless complexity, wrong altitude. | Quality-only suggestions; behavior must be preserved. |

### How the lenses combine

- **Lenses 1–2 are must-fix territory.** A real logic bug or a swallowed error
  is a blocker. Apply them first and hardest.
- **Lens 3 backstops 1–2:** an untested error path is exactly where silent
  failures hide. When lens 2 flags a fragile error path, lens 3 should ask
  whether a test pins the correct behavior.
- **Lenses 4–6 are quality.** Real, but rarely merge-blockers on their own.
  Type-design and simplification findings must never change behavior; comment
  findings are advisory.
- **Default to advisory for 4–6.** Suggest; don't demand. The author owns the
  trade-off between a stronger type and added complexity.

## Adversarial verification — worked discipline

Before writing any finding, run it through this gate:

1. **Restate the claim precisely.** "This `except` swallows the DB timeout and
   returns an empty list, so callers see 'no results' instead of an error."
2. **Try to refute it.** Is the exception re-raised later? Does a caller check a
   sentinel? Is the empty list actually the documented contract? Read the code
   that proves or disproves it — don't assume.
3. **Decide.** Survives refutation and impact is real → report (note confidence).
   Otherwise → drop it silently. Do **not** report "I wasn't sure but maybe".

This gate is why a good review can read a 600-line diff and report three findings
instead of thirty. The dropped twenty-seven were not real.

## Running the review

**Solo / sequential (default).** One reviewer walks the diff once per lens, or
holds all six questions in mind on a single read for a small change. Collect
candidates, run each through the adversarial gate, then assemble the report.

**Parallel / thorough.** For a large diff or a high-stakes change, run the lenses
as **independent passes** — each lens gets the same diff and reports
independently, then you merge and de-duplicate. This is just fan-out: the lenses
share no state, so they parallelize cleanly. (On agent platforms that support it,
each lens can be a separate subagent dispatch — e.g. on Claude Code, one `Agent`
per lens running concurrently. This is an optimization, **not** a requirement:
the methodology is identical run by one reviewer.)

When merging parallel results: de-duplicate overlapping findings, re-apply the
confidence filter to the combined set, and resolve any lens-vs-lens conflicts
(e.g. simplification suggesting a change that the type lens would weaken).

## Output format

```
## Reviewed
<what you looked at: the diff range, files, scope>

## Critical / must-fix
- <file:line> — <issue> (confidence NN). Why it matters: <…>. Fix: <…>.
  [cite the violated project rule if any]

## Suggestions / nice-to-have
- <file:line> — <issue>. <concrete suggestion>. Risk: none / <behavioral note>.

## Type design   (only if types changed)
<per-type rating + concerns, see references/dimensions.md>

## Notes
<what's well done, if genuinely notable; coverage you couldn't verify>
```

If nothing clears the confidence bar, say so plainly and stop. A short, honest
"this looks good, here's what I checked" is a valid and valuable review.

## Anti-patterns

| Don't | Why |
|---|---|
| Report every style preference and "you could also…" | Buries real findings; trains the author to ignore your reviews. |
| Flag pre-existing code the diff didn't touch | Out of scope; review the change, not the repo. |
| Report a finding you couldn't verify | Confident false positives erode trust faster than missed nits. |
| Demand behavior changes from the simplification/type/comment lenses | Those are quality lenses; preserve behavior, stay advisory. |
| Treat "no comments" / "more comments" as a blanket rule | Comments earn their place by explaining *why*; judge each one. |
| Skip the diff and "review the architecture" | That's a different task; this skill reviews a change. |
| Pile on nits to look thorough | Thoroughness is catching the one real bug, not listing twenty nits. |
