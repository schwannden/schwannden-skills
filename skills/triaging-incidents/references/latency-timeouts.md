# Example Playbook: Latency / Request Timeouts

> **Synthetic example.** Service `web-api`, the fields, and the queries are
> placeholders illustrating the playbook format. Replace them with your real
> service, timing fields, and tooling when adapting this skill.

## Table of contents

- [Symptom](#symptom-requests-are-slow-or-timing-out)
- [Timing mental model](#timing-mental-model)
- [Diagnostic steps](#diagnostic-steps)
- [Root-cause patterns](#root-cause-patterns)
- [Resolution](#resolution)
- [Notes and false alarms](#notes--false-alarms)

## Symptom: requests are slow or timing out

**Looks like:** clients report timeouts or sluggish responses from `web-api`;
latency dashboards show p99 climbing, or clients give up before a response.
**Blast radius cues:** all endpoints vs one; steady climb vs sudden spike vs
intermittent; correlated with a traffic surge, a deploy, or a batch job?

## Timing mental model

```
Client timeout threshold (e.g. 10s)
├─ Connection setup  (NOT in application logs)
│   DNS · TCP · TLS handshake
└─ Application time  (IN application logs)
    queue_time   — waiting for a free worker
    duration     — actual processing
Total app time = queue_time + duration
```

**Key insight:** if the client reports a timeout but no slow requests appear in
app logs, the delay was likely in connection setup (DNS/TCP/TLS) or the
load-balancer layer — not the application.

## Diagnostic steps

**1. Separate queue time from processing time.**

Hypothesis: the service is slow in processing. Aggregate both fields.

```text
fields @timestamp, queue_time, duration, url, status
| filter status = 200
| stats pct(queue_time,99) as p99_queue, pct(duration,99) as p99_proc,
        max(queue_time + duration) as max_total by bin(1m) as t
| sort t asc
```

- High `queue_time`, normal `duration` → **worker starvation** (not enough
  capacity for the load).
- Normal `queue_time`, high `duration` → **slow processing** (DB query,
  downstream call).
- Both rising together → **system overload / cascading failure.**

**2. Find requests that actually exceeded the client threshold.**

```text
fields @timestamp, (queue_time + duration) as total, url, user_id
| filter status = 200 and (queue_time + duration) > <THRESHOLD_MS>
| sort total desc
| limit 50
```

**3. If nothing in app logs exceeds the threshold — look below the app.**

Hypothesis: the delay is in connection setup or the load balancer. Compute the
gap = client timeout − max observed app total. A large gap points to
DNS/TLS/LB, not the application. Check LB target health and connection errors.

**4. If processing is slow — find the dependency.**

Hypothesis: a DB query or downstream call regressed. Check DB metrics
(CPU, connections, slow-query log) and the downstream service's latency
directly. Verify magnitude: does the dependency's slowdown account for the
observed `duration`?

## Root-cause patterns

| Signal seen | Likely cause | Confirm by |
|-------------|--------------|------------|
| p99 `queue_time` climbing steadily | Worker starvation under load | concurrency metric vs traffic |
| Sudden `duration` jump | DB/downstream slowdown | DB metrics; downstream latency |
| Both rising together | Overload / cascading failure | traffic source; saturation metrics |
| Intermittent spikes, then normal | Batch job, GC pause, conn-pool churn | correlate with cron schedule |
| Client timeout, no slow app logs | Connection setup or LB layer | gap analysis; LB target health |

## Resolution

- **Mitigation:** scale workers/capacity, shed load, or roll back a deploy that
  introduced the slow path.
- **Fix:** optimize the slow query/call, add an index, tune the connection pool
  or timeouts, or right-size capacity.
- **Verify:** p99 latency returns to baseline and holds through the next
  traffic cycle; no requests exceed the client threshold.

## Notes / false alarms

- "System-wide timeout" reports with zero slow requests in app logs are usually
  a client-side network issue, not a service problem.
- Checking only `duration` misses time spent waiting in the queue — always
  evaluate `queue_time + duration`.
- Watch the date near midnight: an alarm time in UTC may be the previous day in
  your local zone — query the correct UTC date.
