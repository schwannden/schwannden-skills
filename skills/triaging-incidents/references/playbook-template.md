# Symptom Playbook Template

Copy this template to create a new `references/<symptom>.md` after an incident
surfaces a symptom with no existing playbook — or to standardize an entry you
are appending to an existing file. This is the artifact that lets the skill
**learn from every incident**: each captured playbook is hard-won diagnostic
knowledge made reproducible.

## Table of contents

- [When to create one](#when-to-create-one)
- [Naming](#naming)
- [The template](#the-template)
- [Filled mini-example](#filled-mini-example)
- [After you create one](#after-you-create-one)
- [Quality bar](#quality-bar)

## When to create one

- A **new symptom** with no matching playbook in the scenario quick table.
- An existing playbook **missed a signal source, a step, or a gotcha** — append
  rather than create a new file.
- A **false alarm** worth recording so nobody re-investigates it cold.
- A **correction**: a wrong conclusion was reached and corrected mid-incident.
  Encode the correction as a permanent step (e.g. "always check deploy history
  before blaming a dependency").

## Naming

- File: `references/<symptom>.md`, kebab-case, describing the *symptom* the
  reporter observes, not the eventual cause (e.g. `elevated-5xx.md`,
  `auth-login-failures.md`). The reporter knows the symptom; they do not yet
  know the cause.

## The template

```markdown
## Symptom: <short description as the reporter would phrase it>

**Looks like:** <observable signal — error message, status code, metric shape,
console error>
**Blast radius cues:** <one user vs many; region; platform (web/mobile);
since-when; correlated with a deploy?>

### Diagnostic steps
1. <single hypothesis> → <narrowest query against which signal source>
2. <next hypothesis, only if step 1 did not confirm>
   - Compare success vs failure for the same subject side by side.
3. <stop once a concrete signal appears; inspect code/config from there>

### Root-cause patterns
| Signal seen | Likely cause | Confirm by |
|-------------|--------------|------------|
| <e.g. 5xx only on one host> | <e.g. one bad task/replica> | <e.g. per-host error count> |
| <...> | <...> | <...> |

### Resolution
- **Mitigation:** <fast stop-the-bleeding step — often a rollback or flag flip>
- **Fix:** <proper code/config change that removes the cause>
- **Verify:** <which signal should return to baseline, and how to confirm>

### Notes / false alarms
- <gotcha, timezone trap, or benign pattern that wastes investigation time>
- <correction encoded from a past incident, if any>
```

## Filled mini-example

```markdown
## Symptom: users on web see "session expired" immediately after login

**Looks like:** redirect back to login right after a 200 on the token exchange;
mobile unaffected.
**Blast radius cues:** web only, all regions, started right after a frontend
deploy.

### Diagnostic steps
1. Hypothesis: cookie attributes changed → compare Set-Cookie on a success vs a
   failing request for the same subject.
2. Hypothesis: clock skew on a replica → check token issue/expiry timestamps in
   auth logs for one subject.

### Root-cause patterns
| Signal seen | Likely cause | Confirm by |
|-------------|--------------|------------|
| Cookie missing SameSite/Secure after deploy | FE changed cookie flags | diff deploy config |
| expiry < issue time | replica clock skew | NTP/metric on the replica |

### Resolution
- Mitigation: roll back the frontend deploy.
- Fix: restore correct cookie attributes in FE config.
- Verify: post-login 200 is no longer followed by a redirect to login.

### Notes / false alarms
- A single user reporting this is usually a stale browser tab, not an incident.
```

## After you create one

1. Add a row to the **scenario quick table** in `SKILL.md` so the new playbook
   is routed to next time.
2. If this skill is public, confirm everything is synthetic and scrubbed — no
   real ids, hostnames, account data, connection strings, or internal names.
3. Tie the change, in your commit/PR, to the incident and the mistake it
   exposed — that traceability is the team's diagnostic changelog.

## Quality bar

- Every diagnostic step tests **one** hypothesis with the **narrowest** query.
- The root-cause table says how to **confirm** each cause, not just name it.
- Resolution separates **mitigation** from **fix** from **verify**.
- Notes capture the trap that would otherwise waste the next responder's time.
