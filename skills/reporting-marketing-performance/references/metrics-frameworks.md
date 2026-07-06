# Marketing metrics & attribution frameworks

Reference for choosing KPIs and reading attribution. Use it to organize a
report's KPI rows against a recognized funnel model and to be precise about
what a channel number can and can't claim.

**Sections:** [AARRR funnel](#aarrr-pirate-metrics-the-kpi-backbone) · [Key ratios](#key-ratios) · [Attribution models](#attribution-models) · [Hypothesis vs. attributed](#hypothesis-vs-attributed)

## AARRR ("Pirate Metrics") — the KPI backbone

Dave McClure's five-stage funnel is a clean spine for grouping KPI rows.
Report by stage rather than as a flat list — it shows *where* the funnel is
leaking, not just that a number moved.

| Stage | Question | Example metrics |
|---|---|---|
| **Acquisition** | How do people find us? | Visits, reach, new followers, leads by source |
| **Activation** | Do they have a good first experience? | Signups, activation rate, time-to-value |
| **Retention** | Do they come back? | W1/M1 retention, repeat visits, cohort curves |
| **Referral** | Do they tell others? | Referrals, shares, viral coefficient, NPS |
| **Revenue** | Do they pay? | Conversions, MRR/revenue, AOV, expansion |

For a small org with only top-of-funnel counts, you may only be able to
populate Acquisition and Activation — that's fine; note which stages are "not
tracked" rather than faking the rest.

## Key ratios

Once raw counts exist, a few ratios carry most of the signal:

- **CAC** (customer acquisition cost) = spend ÷ new customers; **blended CAC**
  across all channels when per-channel spend isn't split out.
- **LTV** (lifetime value) and **LTV:CAC** — the efficiency ratio; ~3:1 is a
  common healthy rule of thumb. Below 1:1 you're losing money per customer.
- **Activation rate**, **W1/M1 retention**, and **cohort curves** — retention
  by signup cohort, the truest read on whether growth compounds or churns.

Only compute a ratio when its inputs are actually tracked; a made-up LTV is
worse than an honest "not tracked."

## Attribution models

How credit for a conversion is assigned across the touches that preceded it.
Naming the model makes a claim honest:

| Model | Credit goes to | Good for |
|---|---|---|
| First-touch | The first interaction | Understanding what creates awareness |
| Last-touch | The final interaction | Simple, but ignores everything earlier |
| Linear | Split evenly across touches | A fair-ish default when touches matter equally |
| Time-decay | Weighted toward touches nearer the conversion | Longer sales cycles |
| Position-based (U-shaped) | Extra weight to first + last, rest split | Valuing both discovery and closing |
| Data-driven / multi-touch | Modeled from actual paths (needs a platform) | Mature setups with enough volume |

## Hypothesis vs. attributed

The core discipline of the reporting skill maps onto this cleanly:

- **No attribution system** → you have channel *activity* and outcome *counts*
  but no linkage. Every content-to-metric claim is a **hypothesis** ("signups
  rose the week after the post — worth testing"), and the report must name the
  missing lead-source capture as the reason it can't be confirmed.
- **A real attribution system exists** (CRM, "how did you hear about us?"
  field, UTM tracking, analytics platform) → cite its *attributed* numbers and
  name the model it uses (e.g. "last-touch, per the CRM"). Don't hedge with
  "this suggests" when the data actually answers the question.

Sources: AARRR — McClure, "Startup Metrics for Pirates." Attribution-model
definitions are standard across GA4 / major analytics platforms.
