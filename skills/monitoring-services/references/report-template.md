# Monitoring report template (healthy-by-default)

The default shape of a report is a **short healthy summary**. The Findings section
is locked behind the two gates from `SKILL.md`:

1. **Baseline gate** — the observation falls outside the per-hour band (diurnal)
   or the aggregate p25-p75 (narrow), for several consecutive samples.
2. **User-impact gate** — error rate, p99 latency, or DLQ/failed-records/lag is
   abnormal, OR a hard threshold in `baselines.md` is breached.

If neither gate is unlocked, do **not** include a Findings section, do **not**
propose next actions, and do **not** use words like "investigate", "capacity
risk", or "next action required".

## Table of contents

1. [Stale-baseline warning](#1-stale-baseline-warning-conditional)
2. [Healthy shape (the default)](#2-healthy-shape-the-default)
3. [Unlocking the Findings section](#3-unlocking-the-findings-section)
4. [Extended shape](#4-extended-shape-when-a-gate-is-unlocked)
5. [Forbidden patterns](#5-forbidden-patterns-any-report)

---

## 1. Stale-baseline warning (conditional)

If `baselines.md` `last_refreshed` is older than `freshness_threshold_days`, the
**first line** of the report is:

```
WARNING: baselines last refreshed <N> days ago (threshold <T>d) - run scripts/refresh_baselines.py before trusting numeric ranges
```

Omit this line entirely when baselines are fresh.

## 2. Healthy shape (the default)

```
OK <service> healthy - <N>/<N> components within normal ranges over <window>
- <component A>: within per-hour band
- <component B>: within per-hour band
- ...

User-impact signals over window:
- Error rate: <value>   normal
- p99 latency: <value>  within baseline
- DLQ / failed records / lag: <value>  zero

Components checked: <list>
Window: <START> to <END> UTC
```

That is the whole report when nothing is wrong. No causal chains, no analysis
paragraphs, no suggestions. **Brevity is a feature.**

## 3. Unlocking the Findings section

Include a Findings section only if at least one of:

- An observation falls outside its baseline band for several consecutive samples.
- Error rate is above baseline and sustained.
- p99 latency exceeds the actionable threshold in `baselines.md`.
- DLQ depth / failed records / processing lag exceeds its invariant.

If a candidate finding matches an entry in `known-chronic.md` (and is below that
entry's escalation threshold), it is **not** promoted - record it under Context.

## 4. Extended shape (when a gate is unlocked)

```
<stale-baseline warning, if applicable>

Summary
- One sentence: which user-impact signal (if any) is abnormal, and the dominant
  infra correlate.
- One sentence: the single most important next action.

User-impact signals
- Error rate: <evidence>   [normal | elevated | incident]
- p99 latency: <evidence>
- DLQ / failed records / lag: <evidence>

Findings
- <Finding title>
  - Observation: <numbers + UTC timestamp>
  - Window context: "X of N samples over the window also fall in this range"
    (REQUIRED for any "sustained" claim - quantify, never hand-wave)
  - Baseline: the per-hour or aggregate band from baselines.md for the affected
    hours
  - Cross-signal correlation: <which other metrics moved together, or
    "none - single-signal anomaly, weak evidence">
  - User-visible impact: <yes/no, with evidence>

Context (optional)
- Patterns matching known-chronic.md.
- Deviations inside the band that are worth recording but are not findings.

Causal chain (only if a gate is unlocked AND the mechanism is at least partly
proven - see causal-closure.md)
- One paragraph from root condition to symptom. If the root cause is not proven,
  state the best-supported mechanism and what remains unproven.

Suggestions (only when a gate is unlocked)
- Each suggestion MUST include:
  - the current value of any config knob it proposes to change,
  - the exact command used to read that current value,
  - the verification metric and expected shape change after the change.
- Allowed when only the baseline gate is unlocked but there is no user impact:
  "informational - record only", "monitor passively", "no immediate action".
```

## 5. Forbidden patterns (any report)

- Do not cite a baseline number you have not verified within this run for diurnal
  metrics - query the per-hour band or skip the comparison.
- Do not use the word "sustained" without quantifying it.
- Do not propose a config change without printing its current value first.
- Do not include Findings, Causal chain, or Suggestions sections when the report
  is healthy.
