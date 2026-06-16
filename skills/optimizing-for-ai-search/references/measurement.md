# Measuring AI search visibility

Reference for Step 7. Three independent layers, the tool landscape, and — most
importantly — an honest read of what is measurable vs. speculative. **Don't
promise citation numbers:** engines are non-deterministic and personalized, so
track **trends over a fixed prompt set**, never single snapshots.

## Contents

- [Three measurement layers](#three-measurement-layers)
- [GA4 setup for AI-referral traffic](#ga4-setup-for-ai-referral-traffic)
- [Tool landscape](#tool-landscape)
- [Honest caveats](#honest-caveats)

## Three measurement layers

Conflating these is a common mistake — measure all three.

1. **Prompt-based visibility monitoring (the primary GEO metric).** Run a fixed
   *prompt library* (segmented by intent, branded vs. non-branded, geography)
   against each engine on a cadence. For each prompt × engine, score
   **present / cited / recommended / absent** plus prominence. Aggregate into:
   - **Brand mention rate** — % of responses mentioning the brand.
   - **Citation share / share of voice** — your share of citations vs.
     competitors vs. third parties (some split "share of answer" = cited as
     source, vs. "share of voice" = merely mentioned).
   - **Content-gap report** — queries where the brand *should* appear but doesn't.
   A manual baseline (~5 prompts × 4 engines, weekly) already catches major
   shifts. Perplexity is easiest (transparent citations).

2. **AI-referral traffic (GA4).** AI assistants send **referral**, not organic,
   traffic — see setup below. Treat the numbers as a **floor**: 35–70% of AI
   sessions arrive with no referrer and fall into **Direct** ("dark traffic").

3. **Server-log / crawler analysis.** Grep logs for AI bot UAs (`GPTBot`,
   `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, `PerplexityBot`, `Google-
   Extended`) to see what's actually fetched; verify IPs against vendor JSON
   lists to filter spoofs. Compute crawl-to-referral ratios (who takes content
   vs. who sends traffic). Cloudflare's AI Audit surfaces this.

## GA4 setup for AI-referral traffic

- Reports → Acquisition → Traffic acquisition; dimension = **Session
  source/medium**. Look for `perplexity.ai`, `chatgpt.com` / `chat.openai.com`,
  `gemini.google.com`, `copilot.microsoft.com` (and `claude.ai`).
- Create a custom channel group (Admin → Data settings → Channel groups) with a
  rule placed **above** the default Referral rule:

  ```text
  Source matches regex:
  (chatgpt\.com|chat\.openai\.com|perplexity\.ai|gemini\.google\.com|copilot\.microsoft\.com|claude\.ai)
  ```

- GA4 added a native "AI" channel (mid-2026) but it only fires when the referrer
  header survives — so it, too, undercounts.

## Tool landscape

Named, not endorsed — categories matter more than brands (the market churns fast):

- **Dedicated AI-visibility / prompt-monitoring platforms** — Profound, Peec AI,
  Otterly.AI, Scrunch AI, and many others. Query large prompt sets across engines
  and report mention rate, share of voice, citation sources, sentiment.
- **SEO-suite add-ons** — Ahrefs Brand Radar, SE Ranking AI tracker, Semrush AI
  features, InLinks. Bolt AI visibility onto existing SEO data.
- **DIY analytics** — GA4 custom channel groups; server-log analyzers; Cloudflare
  AI Audit.
- **Audit / validation** — the skill's `geo-audit.sh`; Google Rich Results Test;
  validator.schema.org; Screaming Frog; Lighthouse; axe DevTools.

## Honest caveats

State these plainly to anyone reading the numbers:

- **AI-referral traffic is systematically undercounted** (dark traffic → Direct).
  GA4 is a floor, not the true influence.
- **robots.txt is advisory.** "Allowed" is necessary but not sufficient; some
  crawlers ignore directives. Blocking there doesn't guarantee exclusion.
- **No standard benchmarks.** GEO/AEO/AI-SEO are used interchangeably; "good"
  share-of-voice varies wildly by category. No industry consensus as of 2026.
- **Engines are non-deterministic and personalized.** Same prompt → different
  answers across runs, accounts, regions, dates. Track trends on a fixed prompt
  set; never report a single snapshot as fact.
- **The "+40%" GEO research is contested.** The foundational study's gains may
  partly reflect simply adding unique content; causality isn't fully isolated.
- **llms.txt / "schema for AI"**: little-to-no evidence of impact today; report
  as optional/unproven, not as levers.

**Bottom line:** crawlability and rendering are objectively verifiable now (curl /
logs / validators) — make those the deterministic core. Citation / share-of-voice
monitoring is real but noisy and tool-dependent — report it as trends with
explicit confidence caveats.
