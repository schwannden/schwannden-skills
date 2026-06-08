---
name: triaging-incidents
description: >
  A tool-agnostic incident-triage workflow that classifies a report, gathers
  signals from logs/metrics/DB, routes to a matching symptom playbook,
  diagnoses to root cause, recommends a resolution, and then captures what was
  learned back into the skill so triage gets faster and smarter over time. Use
  when investigating a production incident or support report (elevated 5xx,
  auth/login failures, latency or timeouts, CORS errors, database alarms),
  triaging a ticket end to end (intake to root cause to documentation), running
  a hypothesis-driven log/metric investigation, or building your own
  team-specific triage skill from this template. Read-only by default — it
  observes and recommends; humans take the actions.
---

# Triaging Incidents

A triage agent that **learns from every incident**. Each investigation either
follows an existing symptom playbook or, when it surfaces something new,
permanently improves this skill by appending a playbook entry. Knowledge that
used to live in one engineer's head becomes a reproducible routine the whole
team — and the agent — can run next time.

This skill is **read-only by default**: it observes signals, forms hypotheses,
and recommends resolutions. Humans (or a separate change-approval process)
take the actions that mutate infrastructure. The safety boundary is not whether
the agent *touches* your stack — it is whether it can *change* it.

It is also a **template**. The example playbooks use synthetic services
(`web-api`, `worker`, `auth-api`) and placeholder queries. Replace them with
your own stack to stand up a team-specific triage skill — see
[How to adapt this to your stack](#how-to-adapt-this-to-your-stack).

## The core loop

```
classify → gather signals → route to playbook → diagnose to root cause
   → recommend resolution → CAPTURE what was learned
                                  │
                                  └──► back into a symptom playbook
```

The last step is the one that compounds. Every incident is a chance to make the
next one cheaper. See [Capturing what you learned](#capturing-what-you-learned).

## Investigation discipline

These rules keep triage fast and honest. They matter more than any specific
query syntax.

### Hypothesis-driven, one question per query

Every query must test **a single hypothesis**. Do not run broad exploratory
matches hoping something jumps out — you will drown in noise and slow yourself
down. State the hypothesis, then write the narrowest query that confirms or
kills it.

Default order unless the report dictates otherwise:

1. Confirm the subject exists and its state (account, resource, deployment).
2. Identify the failing surface — which endpoint / job / dependency, and the
   error pattern (filter by an identifier plus a status/error code).
3. Compare success vs failure for the same subject side by side (URL, headers,
   timing, region — look for the one thing that differs).
4. Once a concrete signal appears, **stop querying and inspect code or config.**

### Evidence before claims

When the suspect is an upstream or downstream service, **check that service's
own logs/metrics** before asserting what it returned. The caller's exception
type tells you which code path ran — not what the dependency actually did.
Never describe a dependency's behavior you have not directly observed.

### Correlation is not causation

A metric spiking *at the same time* as the incident is a lead, not a verdict.
Before you commit to a root cause, confirm the suspected cause is **large
enough to explain the observed impact**. A 2% blip in one dependency rarely
explains a full outage. Quantify the magnitude, not just the timing.

### Stop conditions

Stop expanding the search when any of these is true:

- A concrete root-cause signal is visible (a specific malformed request, a
  consistent error code, a saturated resource).
- The same hypothesis has been confirmed from two independent angles.
- The evidence points to a code/config problem that needs source inspection,
  not more log data.

Do not keep mining logs after a high-confidence signal is found. More data
after that point is procrastination, not diligence.

### Common mistakes

- Speculating about a dependency's response from code paths instead of checking
  its actual logs/metrics.
- Running a broad text search before narrowing to a specific surface.
- Filtering by IP/host before confirming which requests belong to the subject.
- Mixing multiple investigation angles into one query.
- Not comparing success vs failure early.
- Treating a correlated metric as the proven cause without checking magnitude.
- Quoting/escaping errors in query strings — wrap query bodies in single quotes
  or escape embedded quotes consistently.

## Signal sources (tool-agnostic)

Triage draws on a few classes of signal. This skill names them generically;
plug in whatever your stack provides.

| Signal class | What it answers | Interchangeable tools |
|--------------|-----------------|-----------------------|
| **Recent logs** | What happened in the last N days, per request/job | CloudWatch Logs Insights, Loki, Datadog Logs, OpenSearch |
| **Historical logs** | What happened beyond log retention | Athena / Presto / BigQuery over archived logs in object storage |
| **Metrics** | Rates, latencies, saturation over time | CloudWatch Metrics, Datadog, Prometheus/Grafana |
| **Database** | Subject state, counts, direct evidence | SQL via a read replica / read-only role |
| **Edge / proxy** | Requests blocked before the app (WAF, CDN, LB) | CDN/WAF logs, load-balancer access logs |
| **Deploy history** | What changed and when | CI/CD records, release tags, IaC change log |

> **Read-only access is the safety mechanism.** Grant the agent read-only roles
> to these sources. It should never hold credentials that can mutate state.

## Triage scenario quick table

Route the report to the playbook whose symptom matches. These ship as synthetic
examples; you will add your own rows over time.

| Symptom | Primary signal | Typical window | Playbook |
|---------|----------------|----------------|----------|
| Elevated 5xx / error-rate spike | Metrics + recent logs + deploy history | 1–24h | `references/elevated-5xx.md` |
| Auth / login failures | Recent logs (filter by user + endpoint) | 24h–7d | `references/auth-login-failures.md` |
| Latency / request timeouts | Metrics + logs (queue vs processing time) | 2–24h | `references/latency-timeouts.md` |
| CORS errors / FE-only outage | Edge/CDN config + edge logs | incident window | `references/cors-errors.md` |
| _(your symptom here)_ | _(your signal)_ | — | `references/<your-symptom>.md` |

## Support / reporter interaction

How you talk to whoever filed the report. Full guide in
`references/support-workflow.md`.

### Intake — normalize the report

Capture before investigating:

- **Subject identifier(s)** — user id, account, request id, resource name.
- **Time window** — and convert to UTC immediately. Timezone errors are the
  single most common reason a triage query returns nothing.
- **Symptom** — the exact error message, status code, or behavior observed.
- **Surface** — which endpoint / page / job / platform (web vs mobile matters).
- **Blast radius** — one user or many? one region? since when?

Ask **one** clarifying question only if a critical handle is missing. Otherwise
start investigating.

### Severity classification

| Severity | Definition | Response |
|----------|------------|----------|
| **SEV1** | Broad outage / data risk / security exposure | Investigate now; recommend escalation to on-call immediately |
| **SEV2** | Significant degradation, subset of users/region | Investigate now; timebox |
| **SEV3** | Single user / minor / has a workaround | Normal queue |

### What to hand back

- The hypothesis, the **key evidence** (the query and a redacted sample), and
  the precise conclusion — or what was ruled out.
- Whether it is a **user action** vs a **system issue**, and whether escalation
  is needed.
- Links to the relevant code/config, not giant log dumps.
- **Mask PII.** Use `user@example.com` and redacted ids in anything shared.

## Diagnose to root cause

1. Form one hypothesis. Write it down.
2. Pull the narrowest signal that tests it (right source from the table above).
3. Confirm or pivot. If confirmed from a second angle, stop.
4. Verify magnitude — does the cause fully explain the impact?
5. Inspect the code/config the evidence points to.
6. State the root cause with the evidence that proves it.

## Recommend resolution

Recommend; do not execute. Give the human:

- The **immediate mitigation** (often a rollback or a flag flip — fastest path
  to stop the bleeding).
- The **proper fix** (the code/config change that removes the cause).
- The **verification step** (what signal should return to baseline, and how to
  confirm it).

Distinguish mitigation from fix explicitly. Rolling back buys time; it is not
the cure.

## Capturing what you learned

**This is the step that makes the skill compound. Do not skip it.**

After every incident — especially one that was slow, surprising, or where an
earlier guess was wrong — update the knowledge base so the next person (or the
agent) starts where you finished.

### When to capture

- A **new symptom** with no matching playbook → create a new
  `references/<symptom>.md`.
- An existing playbook **missed a step, a signal source, or a gotcha** → append
  to it.
- A **false alarm** that looked scary but was benign → record it so nobody
  re-investigates it from scratch.
- A **correction**: the agent (or you) reached a wrong conclusion and got
  corrected mid-incident → encode that correction. "You missed deploy history"
  becomes a permanent step.

Treat the diffs to these files as a changelog of your team's diagnostic
intelligence — each change traceable to a specific incident and a specific
mistake. Maintained not by discipline, but by the natural pressure of real
incidents.

### How to capture

1. Pick the target file (existing playbook, or a new one).
2. Use the template in `references/playbook-template.md`.
3. After adding a **new** playbook file, add a row to the
   [Triage scenario quick table](#triage-scenario-quick-table) above so it is
   discoverable next time.
4. Keep it synthetic and scrubbed if this skill is shared publicly — no real
   ids, hostnames, account data, or internal names.

A symptom playbook entry, at minimum:

```markdown
## Symptom: <short description>

**Looks like:** <observable signal — error message, status code, metric shape>
**Blast radius cues:** <one user vs many, region, platform, since-when>

### Diagnostic steps
1. <hypothesis> → <narrowest query against which signal source>
2. ...

### Root-cause patterns
| Signal seen | Likely cause | Confirm by |
|-------------|--------------|------------|
| ... | ... | ... |

### Resolution
- Mitigation: <fast stop-the-bleeding step>
- Fix: <proper code/config change>
- Verify: <signal that should return to baseline>

### Notes / false alarms
- <gotcha, timezone trap, or benign pattern that wastes time>
```

## How to adapt this to your stack

To build your **own** triage skill from this template:

1. **Copy this folder** and rename it (gerund form, e.g.
   `triaging-payments-incidents`). Update `name` to match the folder.
2. **Fill the signal table** with your real (private) tools — your log groups,
   metric namespaces, query workgroups, read-replica connection. Keep secrets
   in your private skill, never in a public one.
3. **Replace the synthetic playbooks** (`web-api`, `worker`, `auth-api`) with
   your real services and queries. Start with your top 3–5 recurring symptoms.
4. **Wire read-only access.** Give the agent read-only roles to logs, metrics,
   and a read replica. Never grant mutate permissions.
5. **Run the loop.** On each incident, follow the workflow and capture what you
   learned. Within a handful of incidents the playbooks embody your team's
   hard-won lessons and triage stops depending on one person typing fast.

## When to load references

| Task | Load this reference |
|------|---------------------|
| End-to-end reporter workflow, prompts, safety rules | `references/support-workflow.md` |
| Template for a new symptom playbook entry | `references/playbook-template.md` |
| Example: error-rate spike | `references/elevated-5xx.md` |
| Example: auth / login failures | `references/auth-login-failures.md` |
| Example: latency / timeouts | `references/latency-timeouts.md` |
| Example: CORS / FE-only outage | `references/cors-errors.md` |
