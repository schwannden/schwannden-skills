# Example Playbook: Auth / Login Failures

> **Synthetic example.** Service `auth-api`, the endpoints, and the queries are
> placeholders illustrating the playbook format. Replace them with your real
> auth service, fields, and tooling when adapting this skill.

## Table of contents

- [Symptom](#symptom-users-cannot-log-in)
- [Diagnostic steps](#diagnostic-steps)
- [Root-cause patterns](#root-cause-patterns)
- [Resolution](#resolution)
- [Notes and false alarms](#notes--false-alarms)

## Symptom: users cannot log in

**Looks like:** login or MFA requests to `auth-api` failing — 401/403/429, or a
generic "unexpected error". May be one user or many.
**Blast radius cues:** one user vs many; web vs mobile vs a specific app
version; one region; correlated with a deploy or a rate-limit/WAF change?

## Diagnostic steps

**1. Confirm the subject exists and its state.**

Hypothesis: the account is disabled/locked/unverified. Look up the subject in
your user store (read-only) and check state flags before reading any logs.

**2. Pull the subject's recent login history.**

Hypothesis: there is a consistent failure pattern for this subject. Filter logs
by subject id and the login/MFA endpoints.

```text
fields @timestamp, url, status, method, agent, fail_reason, user_id
| filter (url = '/v1/login' or url = '/v1/login/mfa') and user_id = '<USER_ID>'
| sort @timestamp desc
| limit 200
```

**3. Compare success vs failure side by side.**

Hypothesis: a request attribute differs between working and failing attempts
(IP, user agent, app version, header). Display them together and look for the
single difference.

**4. If failures are broad, check for an edge/rate-limit cause.**

Hypothesis: a WAF/rate-limit rule or a captcha provider is rejecting requests
before the app. If app logs show **zero** failures for a user who clearly can't
log in, the block is at the edge — check CDN/WAF logs, not the app.

## Root-cause patterns

| Status | `fail_reason` | Cause | Action |
|--------|---------------|-------|--------|
| 401 | `invalid_credentials` | Wrong password | User resets password |
| 401 | `account_locked` | Too many failed attempts | Wait out lockout / unlock |
| 403 | `captcha_failed` | Bot-check challenge failed | Often one platform/app version only |
| 403 | `blocked` | IP/edge block | Check WAF/CDN rules, not app logs |
| 429 | `rate_limited` | Rate limit exceeded | Confirm limit threshold; back off |
| 5xx | various | Server/dependency error | Route to `elevated-5xx.md` |
| (none in app logs) | — | Blocked at the edge | Check CDN/WAF logs |

## Resolution

- **Mitigation:** if a deploy or a rate-limit/WAF change caused broad failures,
  roll it back or relax the offending rule.
- **Fix:** correct the auth-flow regression, captcha config, or rate-limit
  threshold; for a single user, the appropriate account action (reset/unlock).
- **Verify:** the subject (or the affected cohort) completes login with a 200
  and the failure rate on the login endpoint returns to baseline.

## Notes / false alarms

- "reCAPTCHA is blocking everyone" is usually one platform or app version, not
  all users — confirm web vs mobile before declaring a broad outage.
- A 201/200 on a password-reset or login endpoint may be intentional even for
  non-existent or deleted accounts (anti-enumeration). It does **not** prove the
  side effect (email sent, session created) actually happened — verify the side
  effect separately.
- Always convert the reported time to UTC; an off-by-one-day timezone error is
  the most common reason a login-history query returns nothing.
