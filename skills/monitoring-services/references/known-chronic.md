# Known chronic patterns — DO NOT report as findings

This file is the skill's memory of "yes, we know, it's fine." It lists patterns
that are **long-term system characteristics**, not anomalies. Before promoting any
observation into Findings, cross-check it here. If it matches an entry:

1. **Skip it from Findings.**
2. Optionally mention it under "Context" with the phrase
   *"matches known chronic pattern (see known-chronic.md)"*.
3. **Never** attach an "investigate" / "next action" / "capacity risk" framing to
   it.

This file is what stops the skill from re-flagging the same non-issue every run.
It grows over time — that growth is the skill learning.

## Table of contents

1. [When to add an entry](#1-when-to-add-an-entry)
2. [Entry format](#2-entry-format)
3. [How suppression works in the workflow](#3-how-suppression-works-in-the-workflow)
4. [Example entries](#4-example-entries)

---

## 1. When to add an entry

Add an entry only when the team has *confirmed* — through a previous
investigation, an incident retro, or an explicit design decision — that the
pattern is expected and not cleanly fixable. The bar is: you closed an
investigation with the conclusion "this is normal, here's why."

This is the self-evolution loop in action. Every closed false-alarm should leave
a trace here so the next run is quieter. The skill should be a little less noisy
after each investigation than it was before.

## 2. Entry format

Each entry records four things:

- **Pattern** — the observable shape, in one or two sentences.
- **Root cause** — why it happens, in one sentence.
- **Verified** — the date confirmed, and (if applicable) the command used to
  verify it. A stale verification is itself a reason to re-check.
- **Not actionable unless** — the explicit escalation threshold beyond which the
  pattern *would* become a real finding. Never write an entry without this; an
  entry with no escape hatch can hide a genuine regression.

## 3. How suppression works in the workflow

Suppression happens *after* the baseline and user-impact gates, not before. An
observation must first look like a real deviation; only then do you check whether
it is a known one. Suppression also has a ceiling: if the observation breaches the
entry's "not actionable unless" threshold, it is **no longer suppressed** and must
be promoted to a finding. Known-chronic is a mute button, not a blindfold.

## 4. Example entries

> Synthetic illustrations of the format. Start your own file empty and let real
> investigations populate it.

### web-api cache hit rate diurnal trough
- **Pattern**: hit rate drops to ~20–22% during the daily traffic peak and
  recovers to ~28–32% during the overnight trough.
- **Root cause**: diurnal user-traffic mix; cache warmup cycle.
- **Verified**: 2026-01-01, against the per-hour band in `baselines.md`.
- **Not actionable unless**: a trough-hour reading stays below 17% for >2h, OR the
  daily peak stops reaching 25%.

### worker queue lag never reaches zero
- **Pattern**: the worker's processing lag sits at 2–8 s steady state across all
  hours and never hits zero.
- **Root cause**: the input stream is continuously fed; the worker keeps up but
  maintains a small lag floor by design.
- **Verified**: 2026-01-01.
- **Not actionable unless**: the maximum lag exceeds 60 s sustained.

### auth-api has near-zero traffic
- **Pattern**: request count, datastore read/write capacity, and invocations are
  all ~0. The service is provisioned but has no real production traffic yet.
- **Root cause**: a feature is launched but not yet routed to users.
- **Not actionable unless**: error count > 0 (something is hitting it and
  failing), OR instance count drops below the configured minimum.

### a datastore metric emits "no data" at low traffic
- **Pattern**: a latency metric on a low-traffic, on-demand table reports "no
  data" rather than a value.
- **Root cause**: a metrics-backend artifact for sparse series, not a service
  issue.
- **Not actionable**: do not request this metric as a debugging step; use consumed
  capacity and error counts instead.

### a tuning knob is already at its maximum
- **Pattern**: a parallelism / concurrency knob is pinned at the platform-imposed
  maximum.
- **Verified**: 2026-01-01, via `<command that prints the current setting>`.
- **Do not** suggest "increase it" — it cannot go higher. Note the ceiling
  instead.
