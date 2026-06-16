# Structured data (JSON-LD) for AI search

Reference for Step 5. **Honest framing:** structured data's value has bifurcated.
For *Google rich results*, several types are now dead. For *AI comprehension /
citation*, the evidence is **suggestive but weak and correlational** — vendors
(including Google) say plain, textual content matters more. Ship schema for
entity clarity and classic rich results; don't sell it as a citation lever.

## Contents

- [The iron rule](#the-iron-rule)
- [Types still worth implementing](#types-still-worth-implementing)
- [Dead / deprecated rich results](#dead--deprecated-rich-results)
- [Implementation rules](#implementation-rules)
- [What Google actually says](#what-google-actually-says)

## The iron rule

**Markup MUST match visible content.** Marking up content that users can't see
(or that isn't there) risks a Google manual action and erodes trust. Never
generate "AI-only" structured data that contradicts the page.

## Types still worth implementing

Low risk, real value for entity understanding, knowledge-graph disambiguation,
and live rich results:

| Type | Why |
|---|---|
| `Organization` + `Person` + `sameAs` | Builds the entity graph; helps engines disambiguate who you are. Highest-value, lowest-risk. |
| `Article` / `NewsArticle` / `BlogPosting` | `author`, `datePublished`, `publisher` — supports E-E-A-T / source-trust signals. |
| `Product` + `Offer` + `Review` / `AggregateRating` | Drives commerce rich results; feeds product answers. |
| `BreadcrumbList` | Still a live rich result; clarifies hierarchy. |
| `Dataset` | High value for data/research sites (Dataset Search, AI retrieval). |
| `QAPage` | Replacement for retired FAQPage on genuine user-Q&A pages. |
| `WebSite` + `SearchAction`, `VideoObject`, `Recipe` | As applicable; still live. |

## Dead / deprecated rich results

These no longer produce Google rich results. The underlying **content** (clear
Q&A, step lists) still helps machines parse meaning — but the *markup* itself
gives no confirmed benefit, so it's low-cost / low-confirmed-value:

- **FAQPage** — rich results retired **May 2026**; Rich Results Test support
  discontinued mid-2026. Google now points to `QAPage` for genuine Q&A.
- **HowTo** — desktop deprecated Sept 2023, fully removed 2024–25; markup ignored
  for search appearance.

Both removals were driven by markup abuse. Google states **rankings are
unaffected** — these are search-*appearance* changes only.

Be skeptical of vendor claims like "schema → +X% AI summaries" or "structured
data raised model accuracy from 16% to 54%." These are marketing; primary,
replicated evidence is lacking.

## Implementation rules

- Emit JSON-LD in `<script type="application/ld+json">` in the **server-rendered**
  HTML (client-injected JSON-LD is invisible to non-rendering AI crawlers — same
  failure mode as client-rendered content).
- Validate **syntax** with the audit script (`jq`/`python3`) and **semantics**
  with the **Google Rich Results Test** and **validator.schema.org** (both
  web-UI; there is no official CLI — extract with `curl` and paste, or use
  Screaming Frog at scale).
- Keep types accurate and populated (real `author`/`publisher`/`sameAs`), not
  skeleton stubs.

## What Google actually says

Google's AI-features guidance is explicit: there are **no additional
requirements** to appear in AI Overviews or AI Mode, and you should **not** create
machine-readable AI-only files or AI-specific markup. Keep content textual, keep
schema accurate and matching visible content, ensure Googlebot access, and meet
Core Web Vitals. This directly contradicts the "special schema/llms.txt for AI"
sales pitch — weight it accordingly.
