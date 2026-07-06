<!--
Monthly (or other recurring-period) marketing report history — append-only log.

WHERE THIS FILE LIVES: this is a convention, not a requirement. Before
creating a new file from this template, search the project for an existing
reporting/marketing-ops file (names like `monthly-report-history`,
`marketing-history`, or similar) and use that instead. If nothing exists, a
reasonable default location is `docs/marketing/monthly-report-history.md`
alongside the project's own operating docs — this file is the org's growing
trend archive, not skill reference material, so it should not live inside a
skills directory.

FORMAT: one `## YYYY-MM` (or `## YYYY-MM-DD` for non-monthly periods) section
per report, appended in chronological order, oldest first. NEVER edit or
delete a prior section — the period-over-period record is the entire point.
Each section contains, in order:
  1. A KPI table (This period | Last period | Change)
  2. A diagnosis (hypothesis-framed, unless a real attribution system exists)
  3. 2-4 next-action recommendations (at least one must be an
     instrumentation/tracking fix, for as long as attribution is missing)
  4. A short raw-notes line: what was actually posted/sent that period

Remember: "not tracked" is not the same as "zero." If a metric wasn't
captured this period, write "not tracked" in its cell — never `0`, which
implies it was measured and genuinely came out to nothing.

The example entry below uses entirely fictional numbers for a fictional
small organization, to illustrate the format. Delete it once you start
logging real periods, or leave it as a formatting reference above your
real entries — either is fine, just don't treat its numbers as real data.
-->

# Marketing Report History

## 2025-01 (example — fictional data, for format reference only)

### KPI vs. last period

| Metric | This period | Last period | Change |
|---|---|---|---|
| Signups (total) | 42 | N/A (first report) | — |
| Signups — referral cohort | 11 | N/A (first report) | — |
| Contact-form leads | 8 | N/A (first report) | — |
| Website/blog posts | 3 | N/A (first report) | — |
| Social media posts | 14 | N/A (first report) | — |
| Email/newsletter sends | 2 | N/A (first report) | — |
| Messaging broadcast (e.g. SMS/chat list) | not tracked | N/A (first report) | — |

### Diagnosis

This is the first logged period, so there is no prior-period comparison. Signups cluster in the two weeks after the two blog posts went up, which is *consistent with* blog content driving signups — but this org has no lead-source field on the signup form, so this is a hypothesis, not a confirmed attribution. Contact-form leads show no clear relationship to social post volume this period; worth watching for a second data point before drawing a conclusion either way.

### Next-action recommendations

1. **Instrumentation (required while attribution is missing):** add a "how did you hear about us?" field to the signup form, so next period's diagnosis can cite real source data instead of a timing hypothesis.
2. Maintain blog cadence at least through the next signup window, since it precedes this period's only visible bump.
3. Test moving one recurring social post to the underused email/newsletter channel and compare lead volume next period.

### Raw notes

Posted 3 blog articles (weeks 1 and 3), 14 social posts across the period, sent 2 newsletters. No messaging/SMS broadcast count was available this period (channel exists but nobody logged sends — flagged as "not tracked," not zero).
