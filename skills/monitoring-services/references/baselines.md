# Baselines and interpretation rules

A baseline is the skill's memory of "normal". It is what turns a raw number into a
judgement. This file is meant to be **edited and refreshed** — it is a living
artifact, not a constant.

---
last_refreshed: 2026-01-01
source_window_days: 14
sample_period: 1h
freshness_threshold_days: 14
---

> The block above is load-bearing. The report template reads `last_refreshed`
> and `freshness_threshold_days` to decide whether to emit a stale-baseline
> warning. Update `last_refreshed` every time you re-run the refresh script.

## Table of contents

1. [What a baseline is](#1-what-a-baseline-is)
2. [How to define a threshold](#2-how-to-define-a-threshold)
3. [Diurnal metrics and the per-hour band](#3-diurnal-metrics-and-the-per-hour-band)
4. [Refresh cadence (self-evolution)](#4-refresh-cadence-self-evolution)
5. [Shape-anomaly detection](#5-shape-anomaly-detection)
6. [Illustrative baseline tables](#6-illustrative-baseline-tables)
7. [Backend versus dashboard discrepancies](#7-backend-versus-dashboard-discrepancies)

---

## 1. What a baseline is

A baseline answers: "for this metric, at this time of day, what range is normal?"
It is expressed as percentiles over a rolling window of recent history (commonly
14 days of hourly samples), not as a single guessed number.

Two principles govern every comparison:

- **A single spike is not an incident.** Look for sustained change AND correlated
  movement in a second signal before treating a deviation as real.
- **Anchor severity to user impact.** If error rate, p99 latency, and queue
  depth / failed records are all normal, no finding is more than informational —
  regardless of how unusual an infra metric looks.

## 2. How to define a threshold

For each tracked metric, record:

- **Stat**: the statistic you sample (Average, Sum, Maximum, p95, p99, …).
- **Band**: the rolling-window percentiles. Use **p25 / p50 / p75** for narrow,
  low-noise metrics and **p5 / p95** for noisy ones.
- **Actionable**: the explicit condition under which the metric becomes a finding
  — a hard threshold ("sustained p99 > 0.6 s") or a band-exit rule ("below the
  per-hour p5 for more than 2 consecutive hours").

Prefer band-relative rules over absolute magic numbers wherever the metric has a
natural daily shape. Reserve hard thresholds for invariants that must hold at all
times (e.g. "dead-letter queue depth must be 0", "system errors must be 0").

## 3. Diurnal metrics and the per-hour band

A diurnal metric has a strong daily cycle (cache hit rate, request rate, CPU,
connection count). For these, **do not** compare an observation to the 24h
aggregate p25/p75 — the aggregate p25 is dragged down by the daily-trough hours
and will make a perfectly normal trough reading look like a floor state.

Instead, compute a **per-UTC-hour** band: 24 buckets, each with its own p25/p50/p75
taken from the same hour-of-day across the window. Compare a reading only against
its own hour's band. The refresh script produces these buckets automatically for
any metric you flag as diurnal.

## 4. Refresh cadence (self-evolution)

Baselines drift as the system grows: more traffic, new endpoints, resized
capacity. A baseline that was right last quarter is wrong today. The skill's job
is to keep itself current.

- The window is rolling (default 14 days). Re-run `scripts/refresh_baselines.py`
  on a cadence at least as often as `freshness_threshold_days`.
- After a refresh, paste the new percentiles into § 6, bump `last_refreshed`, and
  note anything that moved materially.
- If `last_refreshed` is older than `freshness_threshold_days`, every report must
  open with the stale-baseline warning (see `report-template.md`), because numeric
  comparisons against rotten baselines are untrustworthy.
- A deliberate, sustained step-change (a capacity increase, a new feature launch)
  should trigger an *immediate* refresh, not wait for the cadence — otherwise the
  skill will flag the new normal as an anomaly on every run.

This is the loop that makes the skill "monitor its own evolution": the system
changes, the baselines follow, and the noise floor stays honest.

## 5. Shape-anomaly detection

After retrieving a series, do not only check for missing datapoints. Scan values
for:

- **Cliff**: sustained drop >30% from the preceding baseline lasting more than a
  few consecutive samples. Cross-reference instance / task count to tell a real
  cliff from a scale-in.
- **Spike**: a value several times the surrounding baseline.
- **Floor state**: metric stuck at a reduced level after a drop.

For windows longer than ~6h, segment into sub-windows (e.g. 2h blocks) and scan
each. Long-window averaging hides short-duration anomalies. For diurnal metrics,
evaluate "stuck below baseline" against the per-hour band, not the 24h aggregate —
a daily-trough reading inside its own hour's p25–p75 is not a floor state.

## 6. Illustrative baseline tables

> The numbers below are **synthetic illustrations** of the format. Replace them
> with real percentiles from the refresh script for your own services.

### web-api request latency
- Stat: p99
- 14-day band (p25 / p50 / p75): 0.29 / 0.31 / 0.33 s
- Actionable: sustained p99 > 0.6 s

### web-api error rate
- Stat: Sum (5xx per minute), expressed as % of requests
- 14-day band: 0.00 / 0.01 / 0.03 %
- Actionable: any sustained rate above 0.5 %, OR any single minute above 2 %

### web-api cache hit rate (DIURNAL)
- Stat: Average
- Diurnal: yes — use the per-hour band below, NOT the 24h aggregate
- 24h aggregate (headline only): p25 21 / p50 27 / p75 29 %
- Actionable: a trough-hour reading below that hour's p5 sustained > 2h

Per-UTC-hour band (synthetic, n≈14 per hour):

| UTC hour | p25 (%) | p50 (%) | p75 (%) |
|----------|---------|---------|---------|
| 00Z | 27 | 28 | 30 |
| 04Z | 30 | 31 | 33 |
| 08Z | 25 | 26 | 31 |
| 12Z | 21 | 22 | 28 |
| 16Z | 20 | 21 | 27 |
| 20Z | 21 | 22 | 27 |

(A real table has all 24 hours; this shows the shape only.)

### worker queue lag (DIURNAL, narrow band)
- Stat: Maximum
- 14-day band: p25 3.9 / p50 4.8 / p75 5.6 s (max 18 s)
- Actionable: sustained max > 60 s
- Note: never reaches zero — see `known-chronic.md`

### worker dead-letter queue depth
- Stat: Maximum
- Invariant: must be 0 at all times
- Actionable: any value > 0

### auth-api running instance count
- Stat: Average
- 14-day band: 2 / 2 / 2
- Actionable: drops below 2, OR plateaus at maximum capacity

## 7. Backend versus dashboard discrepancies

- Programmatic metric query says normal, but the dashboard looks wrong → dashboard
  wiring issue, not a service incident.
- Programmatic query shows a shape anomaly, dashboard looks fine → service-level
  anomaly; trust the query and report it.

Always trust the raw metric API over a rendered panel; panels can have stale
queries or wrong dimensions.
