# Example Playbook: Elevated 5xx / Error-Rate Spike

> **Synthetic example.** Services `web-api` and `worker` and the queries below
> are placeholders that illustrate the playbook format. Replace them with your
> real services, log sources, and queries when adapting this skill.

## Table of contents

- [Symptom](#symptom-elevated-5xx--error-rate-spike)
- [Diagnostic steps](#diagnostic-steps)
- [Root-cause patterns](#root-cause-patterns)
- [Resolution](#resolution)
- [Notes and false alarms](#notes--false-alarms)

## Symptom: elevated 5xx / error-rate spike

**Looks like:** error-rate dashboard for `web-api` jumps above baseline; clients
see 500/502/503; may be one endpoint or all of them.
**Blast radius cues:** all users vs one endpoint; one region/AZ vs all; one
host/replica vs the fleet; correlated with a deploy or a traffic surge?

## Diagnostic steps

Follow the discipline: one hypothesis per query, stop at the first concrete
signal, verify magnitude before committing.

**1. Quantify and locate — is it one surface or the whole service?**

Hypothesis: the errors concentrate on a specific endpoint. Bin error counts by
endpoint and time. (Logs Insights flavor; the SQL/Loki/Datadog equivalent is
the same group-by.)

```text
fields @timestamp, status, url
| filter status >= 500
| stats count() as errors by url, bin(5m) as t
| sort t desc, errors desc
```

**2. Is it one host/replica or the fleet?**

Hypothesis: a single bad task is serving errors. Group by host/instance.

```text
fields @timestamp, status, host
| filter status >= 500
| stats count() as errors by host, bin(5m) as t
| sort errors desc
```

If errors collapse onto one host → likely a bad task; the fix is to cycle it.
If spread evenly across hosts → a code/config/dependency cause.

**3. Did something change? Check deploy history.**

Hypothesis: a deploy introduced the regression. Compare the spike's start time
to release/IaC timestamps. **Do not skip this** — "what changed and when" is the
fastest path to root cause and the most commonly forgotten step.

**4. Is a dependency failing? Check the dependency's own signals.**

Hypothesis: `web-api` 5xx is caused by `worker` (or a DB) failing. Check the
dependency's error rate and latency directly — not `web-api`'s exception type.
A caller's exception only says which code path ran, not what the dependency
actually returned.

```text
# dependency-side error rate (synthetic)
fields @timestamp, status, dependency
| filter service = 'worker' and status >= 500
| stats count() as errors by bin(5m) as t
```

Verify magnitude: does the dependency's failure volume actually account for the
observed `web-api` error count? A small dependency blip cannot explain a full
spike.

## Root-cause patterns

| Signal seen | Likely cause | Confirm by |
|-------------|--------------|------------|
| 5xx on one host only | Bad task/replica (OOM, wedged) | per-host error count; host resource metrics |
| Spike begins exactly at a deploy | Regression in the release | diff the deploy; check if rollback clears it |
| 5xx track a dependency's errors 1:1 | Dependency outage (`worker`/DB) | dependency error rate + magnitude match |
| 503 + saturated CPU/connections | Capacity exhaustion under load | concurrency/connection metrics vs traffic |
| 502 with no app log entries | Crash before app handled request / LB-to-app conn reset | LB access logs; container restart events |

## Resolution

- **Mitigation:** roll back the implicated deploy, or cycle the bad host, or
  shed/scale for capacity — whichever stops the bleeding fastest.
- **Fix:** the code/config change that removes the regression, the dependency
  fix, or a durable capacity/timeout/retry adjustment.
- **Verify:** error rate returns to baseline on the dashboard and stays there
  through the next traffic cycle.

## Notes / false alarms

- A brief 502/503 burst exactly at deploy time that self-heals in seconds is
  often normal rolling-restart behavior, not an incident.
- 5xx that appear only in synthetic-monitor checks but not in real user traffic
  usually mean the monitor's assertion or auth went stale.
- Always verify the dependency hypothesis by magnitude — a correlated 1–2%
  dependency blip rarely explains a full service spike.
