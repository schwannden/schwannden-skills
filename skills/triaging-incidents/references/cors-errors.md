# Example Playbook: CORS Errors / Frontend-Only Outage

> **Synthetic example.** Service `web-api`, the policy/header names, and the
> commands are placeholders illustrating the playbook format. Replace them with
> your real CDN/edge configuration when adapting this skill.

## Table of contents

- [Symptom](#symptom-web-clients-blocked-by-cors-mobile-fine)
- [The layered mental model](#the-layered-mental-model)
- [Diagnostic steps](#diagnostic-steps)
- [Root-cause patterns](#root-cause-patterns)
- [Resolution](#resolution)
- [Notes and false alarms](#notes--false-alarms)

## Symptom: web clients blocked by CORS; mobile fine

**Looks like:** browser console shows
`Access to fetch ... blocked by CORS policy`; web app fails to call `web-api`;
native mobile clients are unaffected.
**Blast radius cues:** web only, all regions, started at a specific time —
almost always correlated with a **frontend deploy**.

## The layered mental model

```
Browser
  └─ CDN / edge   ← CORS preflight (OPTIONS) terminated and answered HERE
        └─ Load balancer  ← only sees requests that pass the edge
              └─ web-api    ← only sees requests that pass the LB
```

**A CORS preflight (OPTIONS) is answered at the CDN/edge and may never reach the
application.** Therefore, for a CORS incident:

- App logs for `web-api` show **zero** signal.
- Application error counts and LB error metrics show **zero**.
- The real configuration lives in the **CDN response-headers / CORS policy**.

This is the classic "everything looks healthy but users can't connect" trap.
If your app dashboards are green during a web-only outage, suspect the edge.

## Diagnostic steps

**1. Confirm it is CORS, not a backend failure.**

Symptoms that confirm: web-only, mobile fine; console shows a CORS-policy
block; began at a frontend deploy; backend dashboards are green.

**2. Identify what header the browser is now sending.**

Hypothesis: the frontend deploy added a request header the edge does not allow.
Common culprits: tracing libraries adding `traceparent`/`tracestate` or similar
custom headers; new auth/observability libs adding `x-*` headers. Read the
browser's `Access-Control-Request-Headers` in the failing preflight.

**3. Compare against the allowed-headers list at the edge.**

Hypothesis: the new header is absent from the CDN CORS allow-list. Fetch the
current allowed headers from your CDN/edge config (synthetic command):

```bash
# Replace with your CDN's get-policy / config-read command (read-only)
your-cdn get-cors-policy --name web-api-headers \
  --query 'cors.accessControlAllowHeaders'
```

Any header the browser sends that is **not** in this list causes the browser to
block the response. That missing header is your root cause.

**4. Rule out an edge WAF block (different from a CORS misconfig).**

Hypothesis: a WAF rule with no method filter is blocking OPTIONS preflights.
Check the edge WAF's blocked-request count for the incident window; if non-zero,
inspect sampled requests for `Method = OPTIONS` to find the offending rule.
Listing rule names alone is insufficient — it omits each rule's match
conditions.

## Root-cause patterns

| Signal seen | Likely cause | Confirm by |
|-------------|--------------|------------|
| New request header absent from edge allow-list | FE deploy added a header | diff allowed headers vs `Access-Control-Request-Headers` |
| Edge WAF blocking OPTIONS | WAF rule with no method filter | blocked-request count + sampled OPTIONS requests |
| App + LB metrics all zero during web outage | Issue is at the edge, not the app | green backend dashboards + CORS console error |

## Resolution

- **Mitigation:** roll back the frontend deploy that started sending the new
  header (fastest), or temporarily relax the offending WAF rule.
- **Fix:** add the missing header to the CDN CORS allow-list (an
  infrastructure/IaC change). If the edge overrides origin headers, the
  application **cannot** fix CORS from code — it must be fixed at the edge.
- **Verify:** the preflight OPTIONS returns the header in
  `Access-Control-Allow-Headers` and the web app's requests succeed.

## Notes / false alarms

- A WAF showing "0 blocked requests" during a web-only outage is the tell-tale
  sign of a CORS config issue, not a WAF block — the browser is blocking
  client-side after a valid-but-incomplete preflight response.
- If the edge is configured to override origin response headers, any
  application-side CORS change is silently discarded. Always fix at the edge.
