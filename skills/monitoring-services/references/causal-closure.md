# Causal closure: tracing a symptom to its root cause

Use this module only **after** the daily workflow has surfaced a real anomaly
(both gates unlocked, not suppressed by known-chronic). This is the discipline
for not stopping at the symptom. A symptom ("p99 latency rose") is a starting
point, not a conclusion; closure means you reach a *mechanism* you can act on, or
you state precisely what remains unproven.

Output is a narrative that reads top to bottom. No Q&A blocks.

## Table of contents

1. [Lock the event definition](#1-lock-the-event-definition)
2. [Collect only falsifying evidence](#2-collect-only-falsifying-evidence)
3. [Falsify the top alternatives](#3-falsify-the-top-alternatives)
4. [Write the end-to-end causal chain](#4-write-the-end-to-end-causal-chain)
5. [Size the fix operationally](#5-size-the-fix-operationally)
6. [Decide severity from outcomes](#6-decide-severity-from-outcomes)
7. [Action items and verification](#7-action-items-and-verification)
8. [Worked generic example](#8-worked-generic-example)
9. [Anti-patterns](#9-anti-patterns)

---

## 1. Lock the event definition

- Time window in UTC (`Z`), explicit start and end.
- The symptom metric(s): name, dimensions, statistic, period.
- State the closure target: the single best-supported mechanism you expect to
  prove, plus the alternatives you intend to falsify.

## 2. Collect only falsifying evidence

- Pull the minimal metric set that can *distinguish* the candidate mechanisms,
  over the same window and period as the symptom.
- Pull logs only to confirm or falsify an app-layer error, and keep them inside
  the same UTC window. Do not go on a logging fishing trip.

## 3. Falsify the top alternatives

Enumerate at most five plausible causes and rule them in or out explicitly.
Typical candidates:

- A deploy or rolling restart during the window.
- An auto-scaling event (scale-out or scale-in).
- A datastore resource failure or saturation (CPU, memory, IO, connections).
- A network partition or connection error at the app layer.
- Application-driven churn (worker recycling, a connection-teardown storm).

Write each in a strict pattern:

> **Hypothesis** → **What would prove it** → **Observed** → **Conclusion**

## 4. Write the end-to-end causal chain

Connect, in order:

1. The root condition that introduces the problem (e.g. synchronization, a config
   change, a dependency slowdown).
2. The trigger threshold that tips it over.
3. Any herd / amplification behavior.
4. A secondary signal that supports the mechanism.
5. The primary symptom and why it is visible at the metric resolution you chose.
6. The recovery mechanism and why recovery was fast or slow.

If you cannot complete the chain, say so and name the missing link — an honest
"best-supported mechanism, X remains unproven" beats a confident guess.

## 5. Size the fix operationally

Do not size a fix by intuition. Define success as a measurable rate, then choose
the parameter that achieves it.

Example: tuning a periodic worker-recycle to avoid a synchronized "herd" recycle.

- Inputs: `N` = number of workers, `r` = per-worker request rate (req/min),
  `J` = recycle jitter parameter.
- Recycle window: `W ≈ J / r` minutes.
- Expected recycle rate: `recycles_per_min ≈ N / W ≈ N * r / J`.
- Target: keep `recycles_per_min` at ~1–2% of workers per minute. Solve for `J`,
  then verify against the next deploy window.

## 6. Decide severity from outcomes

Anchor severity to user impact (error rate, latency, error logs), not to fear. If
there was no user impact, say so — and explain why the pattern is still worth a
capacity note, if it is.

## 7. Action items and verification

- One minimal, reversible primary fix.
- A concrete verification window and the expected metric-shape change after the
  fix.
- An observability improvement only if it reduces future time-to-truth.

## 8. Worked generic example

**Symptom.** `web-api` p99 latency rose from ~0.31 s to ~0.9 s, sustained for
~25 minutes, 02:10–02:35Z. Error rate stayed near zero.

**Stop at the symptom?** No. "Latency rose" is not actionable. Trace it.

**Falsify alternatives.**

- *Deploy* → would show a new task/version in the same window → none observed →
  ruled out.
- *Scale-in* → would show running task count dropping → task count was flat at
  120 → ruled out.
- *Datastore CPU saturation* → would show DB CPU climbing with latency → DB CPU
  flat at 14% → ruled out.
- *Connection-teardown storm* → would show a >30% cliff in DB connections plus a
  commit-throughput wave with near-zero commit latency → **observed**: connections
  fell 180 → 60 at 02:09Z, commit throughput spiked, commit latency near zero →
  retained.

**Causal chain.** A periodic worker-recycle parameter caused many workers to hit
their max-request count within the same minute (root condition: synchronized
recycle). They tore down and rebuilt their DB connection pools simultaneously
(herd behavior). During the rebuild, in-flight requests queued behind connection
acquisition (mechanism), which is what surfaced as the p99 spike at 60 s
resolution. Recovery was gradual as pools refilled (~25 min), matching the latency
decay.

**Size the fix.** With `N=120`, `r≈30`, current `J` produces a recycle window so
short that dozens recycle per minute. Target ~1–2 workers/min → raise `J` so
`W ≈ N / target`. Before proposing, read the current value:
`<command that prints the current recycle/jitter setting>`.

**Severity.** No user impact (error rate flat, latency recovered without
intervention) — informational, with a capacity note: under higher load the same
herd could cause 5xx.

**Verification.** After raising `J`, the next deploy window should show DB
connections decaying smoothly rather than cliffing, and p99 staying under 0.4 s.

## 9. Anti-patterns

- Mixing UTC and local timestamps without an explicit conversion.
- Asserting "no deploy" or "no scaling" without showing the desired/running counts
  in the same window.
- Reporting everything that is OK instead of only what is wrong.
- Declaring a root cause without a falsification pass — that is a guess wearing a
  conclusion's clothes.
