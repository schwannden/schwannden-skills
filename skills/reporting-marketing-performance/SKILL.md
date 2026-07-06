---
name: reporting-marketing-performance
description: Use when producing a recurring (e.g. monthly) marketing performance report from raw channel counts — signups, leads, content/post volume — especially for small teams/orgs that have no formal attribution system. Builds a KPI-vs-last-period table from a running history file, diagnoses content-to-metric patterns as hypotheses rather than proven causation, and recommends 2-4 next actions that must include at least one instrumentation/tracking fix. Not for drafting the content itself, deep web analytics, or one-off campaign attribution — and not a substitute for a real CRM/analytics platform's attribution data if one is already in place.
---

# Reporting marketing performance

## Overview

**Core principle — the gap is usually habit, not tooling.** Most small teams and orgs already have *some* raw counts (signups, leads, posts sent) lying around in spreadsheets, forms, or someone's head — what's missing is the habit of turning them into a running, comparable record. This skill's entire value is compounding whatever counts exist into a period-over-period history file that didn't exist before. Every report must diagnose content-to-metric patterns as **hypotheses**, never proven causation, unless a real attribution system says otherwise — and it must push toward the one instrumentation fix (usually lead-source capture) that would make the hypothesis provable.

**Verify the attribution assumption before writing the report — don't guess it.** If the org has no CRM, ad-spend tracking, or analytics dashboard capturing "how did you hear about us," diagnose by hypothesis as described above. If a CRM or analytics platform **is** in place and already attributes leads/signups to a channel, use its real data instead of hypothesizing — and name the attribution model it uses (e.g. "last-touch, per the CRM"). Ask the user which situation applies if it isn't obvious from the inputs they give you. See `references/metrics-frameworks.md` for the AARRR funnel to group KPI rows against, the key ratios (CAC, LTV:CAC, retention cohorts), and the attribution-model menu.

**Check for a brand-kit fact sheet first.** If the project has a fact sheet built via the `building-brand-kits` skill (typically `references/fact-sheet.md` or similar), read its "Owned channels" section for canonical channel names before writing the report — this keeps labels consistent with every other skill touching this org's content. If no fact sheet exists, ask the user which channels to report on; don't assume a fixed channel list. Illustrative examples of channels you might see: website/blog, social media, email or a messaging broadcast list — but treat these as examples only, never as a required set.

## When to Use

- Someone gives you a period's raw counts: signups/leads by source, and what was posted/sent (post counts, blog posts, press mentions, campaigns sent)
- Someone asks for "this month's marketing report," "how did we do this period," or wants to start a recurring review habit
- **Not for:** drafting the content itself (that's a separate content/copywriting skill), deep web analytics (there's no dashboard to pull from if none exists), or one-off campaign attribution when no attribution data exists to analyze (see Common Mistakes)

## Quick Reference

| Report section | Built from | Notes |
|---|---|---|
| 1. Collect inputs | Whatever raw counts the requester has | Don't block on missing fields — note them as "not tracked this period," never as zero |
| 2. Read or create the history file | Prior entries in the running history file | First-ever run: show this period only, mark comparison column "N/A (first report)" |
| 3. KPI-vs-last-period table | This period's counts + prior entry | Compute Change as delta/percent; leave blank if there's no prior period rather than inventing a baseline |
| 4. Diagnosis | KPI table + free-text list of what was posted/sent | Always framed as hypothesis unless real attribution data says otherwise; explicitly note the assumption you verified |
| 5. Next-action recommendations (2-4) | Diagnosis + standing instrumentation gap | **Must** include ≥1 instrumentation/tracking fix whenever attribution data is still missing |
| 6. Append to history file | All of the above | Append-only — never overwrite. Create the file with a header on first run. |

**History file location:** no fixed path — this is a convention, not a requirement. Before creating a new file, check whether the project already has a reporting/marketing-ops file (search for names like `monthly-report-history`, `marketing-history`, or ask the user). If none exists, a reasonable default is `docs/marketing/monthly-report-history.md`, created alongside the project's own operating docs, not inside a skills directory — it's the org's growing trend archive, not skill reference material. See `assets/monthly-report-history-template.md` for the format.

## Workflow

### 1. Collect this period's inputs

Ask for (or extract from what's given) whatever raw counts the requester has — don't block on missing fields, just note them as "not tracked this period":

- Primary conversion metrics for this org: signups, leads, sales, registrations — whatever the org's actual funnel(s) produce (by source/cohort/campaign if given)
- Content/activity volume by channel — pull the channel list from the brand-kit fact sheet if one exists (see Overview); otherwise ask which channels matter
- Any free-text color: what specifically was posted, when in the period, anything unusual (a campaign didn't run, a press hit landed, a form was down, etc.)

**Discipline: "not tracked" is never the same as "zero."** If a count wasn't captured this period, say so explicitly. Recording `0` implies the metric was measured and nothing happened; recording "not tracked" tells the truth that no one looked. Conflating the two corrupts every future period-over-period comparison silently.

### 2. Read or create the history file

Search the project first (see "History file location" above) before creating a new file — most projects that ask for this report more than once already have one.

- **If it doesn't exist:** create it (and its parent directory) with a short header explaining what the file is and that entries are appended chronologically, oldest first. Then treat this as the first entry — there is no prior period to compare against.
- **If it exists:** find the most recent dated entry and use its KPI numbers as the "last period" column. If the file has entries but the immediately-prior period is missing (skipped), compare against whatever the latest entry is and say explicitly which period you're comparing to.

### 3. Build the KPI-vs-last-period table

Columns: Metric | This period | Last period (or "N/A (first report)") | Change. Rows: one per conversion metric (total, plus by source/cohort if given), and one per content/activity channel with its count. Where it helps, group rows by **AARRR stage** (Acquisition / Activation / Retention / Referral / Revenue — see `references/metrics-frameworks.md`) so the table shows where the funnel leaks, not just a flat list. Compute Change as a delta or percent; if there's no prior period, leave Change blank rather than inventing a baseline. If a metric is "not tracked" this period, write that in the cell — don't leave it blank and don't write `0`.

**Two report modes.** In *hypothesis mode* (no attribution system), the table is raw counts and the diagnosis stays hypothesis-only. In *attributed mode* (a CRM/analytics platform attributes leads to channels), add a "Source/model" note stating which model produced the attributed numbers (e.g. last-touch) and cite the attributed figures directly instead of hedging.

### 4. Write the diagnosis

Look for temporal/volume patterns between channel activity and the conversion metrics — e.g. "signups rose the week after the blog post went up, not during the heavier social-posting cadence." If no real attribution system exists, state each pattern as a hypothesis ("this suggests," "worth testing," "consistent with, but doesn't prove") and explicitly name the reason it can't be confirmed (no lead-source capture on the funnel). If a real attribution system exists, cite its actual attributed numbers instead of hedging. Don't skip this section just because a period is quiet — write "no clear pattern this period" if that's the honest read.

### 5. Give 2-4 next-action recommendations

At least one recommendation, for as long as attribution is missing, must be an instrumentation/tracking fix scoped to the org's actual size — e.g. adding a "how did you hear about us?" field to a signup or contact form, or turning on UTM parameters for outbound links. A recommendation like "post more" or "buy a CRM" does not satisfy this requirement on its own — the instrumentation fix must be something that would make next period's diagnosis provable rather than hypothetical. Other recommendations should be content/channel adjustments implied by the diagnosis (e.g. "double down on the channel that preceded the signup bump," "test posting to an underused channel"). Keep recommendations concrete and sized to the org's actual tooling — see Common Mistakes.

### 6. Append to the history file

Add a new dated section (e.g. `## YYYY-MM`) at the end of the file — never overwrite prior sections. **Concrete safeguard against clobbering the archive:** first read the full existing file, then write it back verbatim with only the new dated section added at the end (or use a true append that leaves every prior byte untouched) — never regenerate the file from scratch or reconstruct old entries from memory, which silently drops or rewrites history. Include: the KPI table, the diagnosis, the recommendations, and a short raw-notes line capturing what was posted/sent that period for future reference. Confirm the prior sections are still present byte-for-byte and the new one is appended, not rewritten, before finishing.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Recommending a CRM/analytics-platform upgrade as "the fix" | Usually overkill for a small org's scale. Right-sized fix is spreadsheet/form-level instrumentation (e.g. one new form field or a UTM convention), not new software — unless the org has actually outgrown that and says so. |
| Presenting a content/channel correlation as proven causation | Always frame as a hypothesis and name the missing-attribution reason it can't be confirmed, unless a real attribution system's data backs the claim. Pair the hypothesis with the instrumentation recommendation that would make it provable. |
| Overwriting the history file instead of appending | The period-over-period archive is the entire point of running this skill. Always append a new dated section; never edit or delete a prior one. |
| Skipping the report because "nothing much happened this period" | Log it anyway with whatever counts exist (even all zeros, if genuinely tracked and zero) — the habit of a recurring entry matters more than any single period's content volume. |
| Inventing or hardcoding a fixed channel list | Pull channel names from the project's brand-kit fact sheet (via `building-brand-kits`) if one exists; otherwise ask the user. Don't assume every org has the same channels. |
| Treating a missing metric as zero | If a count wasn't tracked this period, say "not tracked" rather than silently recording `0` — `0` implies it was measured and nothing happened. |
| Assuming no attribution system exists without checking | Ask, or check for a CRM/analytics platform, before defaulting to hypothesis-only diagnosis. If real attribution data exists, use it — hedging with "this suggests" when you actually know the answer is a worse failure than false precision. |
