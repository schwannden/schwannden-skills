---
name: monitoring-services
description: A tool-agnostic service-monitoring workflow that runs per-service health checks, compares observations against self-maintained baselines, traces symptoms to root cause (causal closure), suppresses known/chronic issues so they stop being re-flagged, and reports only what is wrong with concrete next actions. The skill maintains and refreshes its own baselines and known-chronic registry on a cadence, so it evolves as the system evolves. Use when asked to run a routine health check, a release watch, an anomaly scan, or a post-incident review on one or more services; when baselines look stale or drifted; or as a TEMPLATE to build a team's own monitoring skill on any metrics backend (CloudWatch, Prometheus, Datadog, SQL). Output is narrative, healthy-by-default, and brief when nothing is wrong.
---

# Monitoring services

Check one service and answer three questions: **Is it healthy? What is wrong? What to do next?**

This skill is not a dashboard. A dashboard is correct the day you build it and stale the next quarter when the system changes. This skill is an **artifact that accumulates operational wisdom**: it carries its own baselines and its own list of known-chronic patterns, refreshes them on a cadence, and gets sharper every time you use it. That self-evolution loop is the heart of this skill — treat it as a first-class responsibility, not an afterthought.

## Guardrails

- **Read-only by default.** Query metrics and logs for facts. Never change service config as part of a health check; only *propose* changes, and only with evidence (see below).
- **Healthy by default.** Report only anomalies. If everything is within baseline, write the short healthy summary and stop. Brevity is a feature.
- **Narrative output.** No "checked X: OK / checked Y: OK" enumerations. No Q&A blocks.
- **One timezone.** Keep every timestamp in UTC (suffix `Z`). Never mix UTC and local without an explicit conversion.
- **Evidence before assertion.** Do not call something "sustained" without quantifying it ("X of N samples over the window"). Do not propose changing a config knob without first printing its current value and the exact command used to read it.

## Inputs (use these defaults if the caller omits them)

- **Service**: one of the configured services (e.g. `web-api`, `worker`, `auth-api`). See `references/healthchecks/`.
- **Environment**: `prod`.
- **Window**: `2h` for a routine check, `24h` for a release watch, `72h` for a trend review.
- **Metrics backend + credentials**: whatever your stack uses (CloudWatch profile/region, Prometheus URL, Datadog API, SQL DSN). Keep these in the healthcheck file, never hardcoded in queries scattered around.

## The two gates (why most observations are NOT findings)

A raw deviation is not a finding. To be reported, an observation must pass **both** gates:

1. **Baseline gate** — the value falls *outside* the baseline band for that metric. For diurnal metrics, compare against the per-hour band, not the 24h aggregate (the daily-trough hours will lie to you otherwise). The deviation must persist across multiple consecutive samples, not a single spike.
2. **User-impact gate** — a user-facing signal is abnormal (error rate, p99 latency, dead-letter queue / failed records / processing lag), OR the observation breaches a hard threshold explicitly listed in `references/baselines.md`.

If neither gate is unlocked: write the healthy summary from `references/report-template.md` and stop. Do **not** use words like "investigate", "capacity risk", or "next action" for something that passed neither gate.

If an observation passes the gates but matches an entry in `references/known-chronic.md`, it is **suppressed** — mention it under "Context" at most, never as a finding or next action.

## Monitoring workflow

Load on every run: `references/baselines.md`, `references/known-chronic.md`, `references/report-template.md`. Then:

1. **Load the service's healthcheck file** (`references/healthchecks/<service>.md`) → get the resource IDs, the metric list, the backend connection details, and which components to check.
2. **Check user-impact signals first** — error rate, p99 latency, DLQ / failed records / lag. These *cap* the maximum severity of every other finding. If user-facing signals are clean, nothing downstream is worse than informational.
3. **Pull each tracked metric** for the window, using the query templates in the healthcheck file. Keep the period appropriate to the window (high-resolution for short windows; coarser for long ones, and note any resolution downgrade).
4. **Scan each series for shape anomalies**, not just missing data:
   - **Cliff**: sustained drop >30% from the preceding baseline lasting more than a few consecutive samples.
   - **Spike**: a value several times the surrounding baseline.
   - **Floor state**: metric stuck at a reduced level after a drop.
   - For windows longer than ~6h, segment into sub-windows (e.g. 2h blocks) and scan each — long-window averaging hides short anomalies.
5. **Apply the baseline gate.** For every provisional observation, compare against the per-hour band (diurnal) or the aggregate p25–p75 (narrow metrics) from `references/baselines.md`. Drop anything inside the band.
6. **Apply the user-impact gate.** Anchor severity to the user-facing signals from step 2.
7. **Suppress known-chronic.** Cross-check `references/known-chronic.md` and drop matches (record under Context only).
8. **Cross-reference** the surviving findings across metrics — a real incident usually shows correlated movement in more than one signal. A lone single-signal deviation is weak evidence.
9. **Trace to root cause** when a finding survives. Do not stop at the symptom. Load `references/causal-closure.md` and follow the falsify-alternatives discipline until you reach a *mechanism*, or honestly state what remains unproven.
10. **Write the report** using `references/report-template.md`. Any proposed config change must include the current value, the command used to read it, and the verification metric + expected shape change.

## Self-evolution: the skill that monitors its own evolution

This is the defining behavior. The system you monitor keeps changing — traffic shifts, new endpoints appear, capacity is resized — so a static baseline rots. The skill's job is to **keep itself current**:

- **Refresh baselines on a cadence.** `references/baselines.md` carries a `last_refreshed` date and a `freshness_threshold_days`. If it is older than the threshold, the *first line* of any report is a stale-baseline warning, and you should run `scripts/refresh_baselines.py` to recompute the rolling percentiles, then update the doc. See `references/baselines.md` § "Refresh cadence".
- **Absorb every closed investigation.** When you finish chasing an anomaly and conclude it was expected and not cleanly fixable, add it to `references/known-chronic.md` with its root cause and the threshold beyond which it *would* become actionable. Next run, the noise is gone — the skill stops re-flagging what you already explained to it.
- **Grow the watch list in place.** When the team says "start watching the new export endpoint" or "add p99 to that metric", edit the healthcheck and baselines files. The next run already monitors it. No redeploy, no separate dashboard PR.
- **Teach it during releases.** Every release watch is a chance to encode a lesson ("ignore 404 spikes on `/health` during a rollout"). The skill should be a little better after each use than it was before, because it learned from that release.

In short: monitoring, investigation, and documentation are the same activity now. When you learn something, write it back into these files so the next invocation inherits it.

## How to adapt this to your stack

This skill is deliberately backend-agnostic. To stand up your own:

1. Copy `references/healthchecks/_template.md` to one file per service; fill in resource IDs, the metric list, the backend, and copy-paste-ready query commands.
2. Replace the illustrative numbers in `references/baselines.md` with real percentiles computed by `scripts/refresh_baselines.py` (wire its `fetch_metric` function to your backend — CloudWatch, Prometheus, Datadog, or SQL; one CloudWatch example is included).
3. Start `references/known-chronic.md` empty and let it grow from real investigations.
4. Keep `references/report-template.md` as-is — the healthy-by-default shape is the point.
5. Set a refresh cadence (a cron, a calendar reminder, or a hook) so baselines never silently drift.

## Reference files

| File | Purpose |
|------|---------|
| `references/baselines.md` | What a baseline is, how to define/refresh thresholds, the diurnal per-hour pattern, refresh cadence. |
| `references/causal-closure.md` | The trace-to-root-cause discipline with a worked generic example. |
| `references/known-chronic.md` | Format + suppression rules so noise does not recur. |
| `references/report-template.md` | The healthy-by-default monitoring report format. |
| `references/healthchecks/_template.md` | Per-service healthcheck template (placeholder services). |
| `scripts/refresh_baselines.py` | Computes rolling baselines from a pluggable metrics source. RUN this to refresh; READ it as the canonical refresh pattern. |
