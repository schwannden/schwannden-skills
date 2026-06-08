# Review dimensions — detailed lens guides

The depth behind each of the six lenses in `SKILL.md`. Read the section for the
lens you need; you rarely need all six at full depth on one change.

## Table of contents
- [1. Correctness / logic bugs](#1-correctness--logic-bugs)
- [2. Silent failures / error handling](#2-silent-failures--error-handling)
- [3. Test coverage](#3-test-coverage)
- [4. Type design](#4-type-design)
- [5. Comment accuracy](#5-comment-accuracy)
- [6. Simplification](#6-simplification)
- [Confidence rubric (shared)](#confidence-rubric-shared)

---

## 1. Correctness / logic bugs

**Question:** Will this code do the wrong thing?

Hunt for actual defects that change behavior, not theoretical concerns:

- **Logic errors** — off-by-one, inverted conditions, wrong operator, wrong
  branch taken, fencepost mistakes, incorrect boolean short-circuit.
- **Null / undefined / None handling** — dereferencing a value that can be
  absent; missing the empty-collection or zero case.
- **Concurrency** — race conditions, shared mutable state, missing locks, an
  `await` that should be there (or one that serializes what should be parallel),
  unawaited coroutines / dangling promises.
- **Security** — injection (SQL, shell, template), missing authz check,
  secrets in logs or responses, unvalidated input crossing a trust boundary,
  path traversal, SSRF.
- **Convention violations** — only when the project documents the convention.
  Cite the rule (section heading) so the author can find it.

**Confidence-based filtering is mandatory here.** This lens is the most prone to
false positives. Trace the actual path before reporting. Report only ≥ 80.
A "this might be a bug if X" where you didn't check X is not a finding.

**Output per finding:** file:line, description + confidence, the violated rule
or a clear bug explanation, a concrete fix. Group **Critical (90–100)** vs
**Important (80–89)**.

---

## 2. Silent failures / error handling

**Question:** Could an error here be swallowed, masked, or hidden?

Silent failures turn a crash (loud, debuggable) into wrong behavior (quiet,
expensive). Zero tolerance — but still confidence-filtered.

**Locate every error-handling site in the diff:**
- `try`/`except` (Python), `try`/`catch` (TS/JS), `Result`/`Option` handling.
- Error callbacks, error event handlers, conditional error branches.
- Fallback logic and default values returned on failure.
- Optional chaining (`?.`) / null-coalescing that can skip a failing operation.
- Retry loops and circuit breakers.

**Interrogate each one:**
- **Catch specificity** — does it catch only expected types? *Enumerate the
  unexpected errors this catch would also hide* — don't hand-wave. A
  `KeyboardInterrupt` or a programming `TypeError` swallowed by a broad catch is
  a real bug.
- **Logging quality** — logged at the right severity, with enough context (the
  operation, relevant IDs, request/correlation id) to debug it in six months?
- **User/caller feedback** — does the caller learn that something failed, and
  what to do about it? Or does it just get a plausible-but-wrong value?
- **Fallback justification** — is the fallback explicitly intended and
  documented, or is it masking the real problem? Is it falling back to a
  mock/stub/fake outside of test code? (That's an architectural smell.)
- **Propagation** — should this bubble to a centralized handler instead of being
  caught here? Does catching here skip needed cleanup?

**Always-flag patterns:**
- Empty `catch`/`except` block — **forbidden**.
- Bare `except:` (no type) in Python.
- `except Exception:` (or `catch (e)`) that only logs and continues, or that
  silently returns a default.
- `asyncio.gather(..., return_exceptions=True)` where results are never
  inspected for `isinstance(r, Exception)`.
- Swallowing an error then returning `None` / `[]` / `""` so the caller can't
  distinguish "no data" from "failed".
- A streaming/SSE endpoint that disconnects on error without emitting an error
  signal — the client can't tell a failure from a network drop.
- A test "fixed" by `skip`/`xfail`/disabling it with no comment naming the real
  defect.

**Severity:** CRITICAL (silent failure, broad/empty catch, dropped async
exceptions, masked data loss) · HIGH (poor message, unjustified fallback,
missing log context) · MEDIUM (could be more specific / richer context).

---

## 3. Test coverage

**Question:** Do the tests actually exercise the new behavior and edge cases?

Focus on **behavioral** coverage, not line percentage. Be pragmatic — do **not**
demand 100% or tests for trivial getters/setters.

**Find the gaps:**
- Untested error-handling paths (the exact places silent failures hide — lens 2).
- Missing edge / boundary cases (empty, zero, max, off-by-one, unicode, nulls).
- Uncovered critical business-logic branches.
- Absent negative cases for validation logic.
- Missing async/concurrent behavior tests where relevant.

**Judge test quality — vacuous tests are worse than none:**
- Does it assert **behavior/contract** or just **implementation details**?
- Would it actually fail if the behavior regressed? (A test that passes
  regardless of the logic is noise.)
- Is it resilient to reasonable refactoring, or coupled to private internals?
- Does it use clear, descriptive names (DAMP over DRY in test bodies)?

**Rate each gap 1–10** (10 = data loss / security / system failure; 7–8 =
user-facing errors; 5–6 = confusing edge cases; ≤4 = optional). Report 8–10 as
**Critical Gaps**, 5–7 as **Important Improvements**. For each: a concrete
failure it would catch, and **the actual path** the test should live at
(consistent with the layout in the diff — not a placeholder like
`tests/somefile.test.ts`). Check whether an existing integration test already
covers it before demanding a new one.

Anchor to the project's testing conventions if present (test runner, fixtures,
how external services are stubbed at the boundary, which tests are opt-in/marked).

---

## 4. Type design

**Question:** Do the types make illegal states unrepresentable and enforce
their own invariants?

Qualitative analysis plus a simple rating. Apply only when types are added or
changed. Stay pragmatic: a simpler type with fewer guarantees can beat a complex
one that does too much.

**Identify the invariants** the type implies: data-consistency rules, valid
state transitions, cross-field constraints, pre/postconditions.

**Rate 1–10 on four axes (brief justification each):**
- **Encapsulation** — are internals hidden? Can the invariant be violated from
  outside? Is the interface minimal and complete?
- **Invariant expression** — are constraints visible in the type's structure,
  enforced at compile/parse time where possible, self-documenting?
- **Invariant usefulness** — do the invariants prevent real bugs and match the
  domain, without being over- or under-restrictive?
- **Invariant enforcement** — checked at construction? Every mutation guarded?
  Is it impossible to build an invalid instance?

**Anti-patterns to flag:**
- Anemic models (data bag, no behavior, invariants enforced by convention only).
- Types exposing mutable internals.
- Invariants documented but not enforced.
- Validation missing at the construction/parse boundary.
- Primitive obsession — a bare `str`/`int` where a newtype/branded type would
  stop id mix-ups across module boundaries.
- Illegal states representable — e.g. `{ ok: bool, data?: T, error?: str }`
  where two fields can both be set or both absent. Prefer a discriminated union
  (`success | error`) / `token | end | error` over flat optionals.

**Stack notes (adapt to what you're reviewing):** prefer validation at the parse
boundary over use-site checks; immutable value objects for DTOs that shouldn't
mutate; structural constraints in the type rather than post-parse validators;
discriminated unions over flat types with optional fields; avoid unchecked
casts. Suggest improvements only when the safety gain justifies the complexity.

---

## 5. Comment accuracy

**Question:** Do the comments tell the truth, and will they stay true?

Comments are read by someone months later with no context. An inaccurate comment
is worse than none. **Advisory only — don't rewrite code, point out issues.**

**Verify factual accuracy** against the actual code:
- Signature matches documented params/returns; described behavior matches logic.
- Referenced types/functions/vars exist and are used as described.
- Edge cases the comment claims are handled actually are.
- Complexity/performance claims are true.

**Evaluate long-term value:**
- Comments that restate the code ("increment i") → flag for removal.
- Comments explaining **why** (a non-obvious constraint, a workaround for a
  specific bug, a surprising invariant) → valuable, keep.
- Comments referencing the current task/PR/caller ("added for the X flow",
  "handles issue #123") → rot; that belongs in the commit message / PR.
- TODO/FIXME that may already be done → verify.

**Categorize findings:** **Critical** (factually wrong or misleading) ·
**Improvement** (could add missing *why*) · **Removal** (adds no lasting value).
Default posture: a comment must earn its place by explaining something the code
can't say itself. Don't apply a blanket "no comments" or "more comments" rule —
judge each one.

---

## 6. Simplification

**Question:** Can this be simpler without changing behavior?

Quality only. **Never change what the code does — only how.** Advisory; the
author applies the fix.

**Look for:**
- Reuse — duplicated logic that an existing helper already covers.
- Dead code — unreachable branches, unused vars/params/imports introduced by
  the change.
- Unnecessary complexity — deep nesting that guard clauses / early returns would
  flatten; nested ternaries (prefer if/else or `match`/`case`); dense one-liners
  that hurt readability.
- Wrong altitude — a function doing too many things at mixed levels of
  abstraction; over-abstraction (a one-call indirection) just as much as
  under-abstraction.
- Naming — name things for what they are, not how they're used.

**Guard against over-simplification.** Don't trade clarity for fewer lines.
Don't merge unrelated concerns. Don't remove a helpful abstraction. **Verify the
suggestion is actually simpler** — count lines, branches, names; if it isn't,
drop it. Respect framework realities (e.g. if a compiler/runtime already handles
memoization or config, removing manual versions is the simplification — adding
them is not).

**Output per suggestion:** location, current snippet, suggested snippet, one-line
*why* (clarity / fewer branches / removed dead abstraction / matches a project
standard), and **Risk** (a behavioral note, or "none" for a pure refactor).
Group by file. If there's nothing to simplify, say so and stop — don't pad.

---

## Confidence rubric (shared)

Score every candidate finding before reporting:

- **0–25** — likely false positive, or a pre-existing issue the diff didn't touch.
- **26–50** — minor nitpick not backed by a documented project rule.
- **51–75** — valid but low-impact.
- **76–90** — important; needs attention.
- **91–100** — critical bug or explicit documented-rule violation.

**Report only ≥ 80.** Run each candidate through the adversarial gate (restate →
refute → decide) in `SKILL.md` first. When you can't push a finding over 80 with
evidence, drop it silently rather than reporting a hedge.
