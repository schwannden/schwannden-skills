---
name: optimizing-for-ai-search
description: 'Audits a website for AI/LLM search visibility (GEO — Generative Engine Optimization, also AEO / answer-engine optimization) and prescribes prioritized fixes so pages can be crawled, rendered, understood, and CITED by AI assistants and answer engines (ChatGPT/SearchGPT, Perplexity, Google AI Overviews & AI Mode, Gemini, Copilot). Use when someone wants their site to "show up in"/"be cited by"/"rank in" AI search or chatbots; when traffic from AI assistants is the goal; when reviewing robots.txt for AI crawlers (GPTBot, OAI-SearchBot, PerplexityBot, ClaudeBot, Google-Extended); when a JavaScript/SPA site is invisible to AI; when adding structured data, llms.txt, or content for AI citation; or when auditing/measuring AI search presence. Triggers: "make my site AI-friendly", "GEO", "AEO", "AI SEO", "get cited by ChatGPT/Perplexity", "AI Overviews", "llms.txt".'
---

# Optimizing for AI Search (GEO / AEO)

Make a website something AI search engines and assistants can **reach, read, and
cite**. The goal of classic SEO was *rank #1, earn the click*; the goal here is
*be one of the few sources the model quotes* in a synthesized answer (often
zero-click).

## The one honest principle

**~90% of GEO is rigorous technical SEO + making content readable without
JavaScript + factual density. There is very little that is genuinely
"AI-specific."** Google's own guidance says there are *no special requirements or
optimizations* for AI Overviews/AI Mode beyond solid, crawlable, textual content.
Resist vendor hype — especially "magic schema percentages" and llms.txt miracles.
Lead with the deterministic, evidence-backed wins below.

## How AI engines pick what to cite (why this works)

Every citing engine runs a **RAG pipeline**: rewrite the query → retrieve
**passages/chunks** (from a crawler index and/or vector store) → re-rank →
synthesize an answer → attach citations to the passages actually used. Two
consequences drive everything:

1. **If your content isn't in plain server-rendered HTML, it isn't retrieved.**
   Most AI crawlers do **not** execute JavaScript.
2. **You compete at the passage level, not the page level.** Each section must be
   self-contained, quotable, and fact-dense.

## The workflow

Run the audit, then fix in priority order (rendering first — it dwarfs the rest).

### Step 1 — Audit (deterministic checks)

Run the script on a representative URL. It needs `curl` (optional `jq`/`python3`):

```bash
./scripts/geo-audit.sh https://example.com/a-real-content-page
```

It reports robots.txt directives for the crawlers that matter, whether content
exists in raw HTML (server-rendered), whether an AI UA gets a 200, JSON-LD
presence/validity, and llms.txt presence. **Read what it CAN'T check:** content
quality and off-site authority are judgment calls (Steps 4–6).

### Step 2 — Fix rendering (the #1 lever)

Most AI crawlers fetch HTML but never run JS. A client-rendered SPA shows them an
empty `<div id="root">`.

- **Server-render or statically generate** every content page (Next.js, Nuxt,
  Astro, SvelteKit, Remix, etc.) so content + `<title>`/meta + canonical +
  JSON-LD are all in the initial HTML response.
- Stuck on a SPA? **Pre-render** to static HTML (e.g. `prerender.io`, static
  export, islands).
- **Verify, don't trust:** `curl -A "GPTBot" <url>` (or the audit script) — if a
  fact isn't in that output, AI crawlers don't see it. Browser DevTools shows the
  *hydrated* DOM and will lie to you here; use View Source / curl.

### Step 3 — Fix crawler access (and avoid the classic traps)

Vendors run three tiers of bot. **Blocking the wrong one silently kills AI
visibility.** Full table + a ready-to-paste robots.txt: `references/crawlers.md`.

- **Never block search/retrieval crawlers** (`OAI-SearchBot`, `PerplexityBot`,
  `Claude-SearchBot`, `Googlebot`, `Bingbot`) — these are how you get cited.
- **`Google-Extended` does NOT control AI Overviews.** Those are served from the
  normal Googlebot index. `Google-Extended` only opts out of Gemini *training*.
- Only block **training** crawlers (`GPTBot`, `ClaudeBot`, `CCBot`,
  `Google-Extended`, `Applebot-Extended`) if protecting content from training is
  a deliberate goal — it carries a real visibility cost.

### Step 4 — Fix content for citation (evidence-backed)

The Princeton GEO study (Aggarwal et al., KDD 2024; ~10k queries) measured what
raises a source's visibility in generative answers by up to ~40%. The reliably
winning levers — all forms of **verifiable factual density** — and the things
that **don't** work: `references/content-tactics.md`. The essentials:

- **Answer-first.** Lead each section with a direct, self-contained answer in the
  first 1–2 sentences, then elaborate. Make every H2/H3 a "mini-article" that
  survives being lifted out of context.
- **Add statistics** (concrete numbers, not vague claims) and **cite credible
  sources** inline and **add expert quotations** — the three highest-impact
  tactics (~+30–40%; the source-citing gain is largest for lower-ranked pages).
- **Question-style headings + a real FAQ** matching how people prompt assistants.
- **E-E-A-T**: real author bylines/bios/credentials, primary-source citations,
  explicit **dates** (AI citations skew heavily toward fresh content).
- **Machine-parseable formatting**: lists, comparison tables, clear definitions.
- **Do NOT** keyword-stuff, pad, or artificially simplify — measured at ~0% or
  *negative*. Classic keyword tactics do not transfer.

### Step 5 — Structured data (useful, but don't over-claim)

Add JSON-LD (server-side) for entity clarity and classic rich results;
AI-citation benefit is plausible but weakly evidenced. Which types still matter,
which Google rich results are **dead** (FAQPage retired 2026; HowTo removed
2023–25), and the iron rule that **markup must match visible content**:
`references/structured-data.md`.

### Step 6 — Off-site authority (not editable on the page)

LLMs synthesize across many sources, so a large share of citation probability
lives **off your site**: mentions on high-authority third-party sites, Wikipedia,
Reddit, review platforms; breadth of referring domains; consistent brand
narrative (digital PR). Name this explicitly to the user — on-page fixes alone
have a ceiling.

### Step 7 — Measure (honestly)

Three independent layers — prompt-based visibility monitoring, AI-referral
traffic in GA4 (heavily *undercounted* as "direct"), and server-log crawler
analysis — plus the tool landscape and what is genuinely measurable vs.
speculative: `references/measurement.md`.

## Quick reference

| Priority | Lever | Why it ranks here |
|---|---|---|
| 1 | Server-side rendering of content + metadata + JSON-LD | Most AI crawlers don't run JS; unrendered content is invisible. Dwarfs everything. |
| 2 | robots.txt: allow retrieval crawlers | Blocking them = removed from AI answers. |
| 3 | Answer-first, self-contained passages, semantic HTML | RAG retrieves chunks, not pages. |
| 4 | Statistics + source citations + expert quotes | Only tactics with controlled-study backing (~+30–40%). |
| 5 | Structured data (honest, matching) | Entity clarity + rich results; AI benefit plausible, not proven. |
| 6 | Off-site mentions / referring domains | A large share of citation probability is off-page. |
| 7 | Measurement (prompt sets, GA4, logs) | Trends over a fixed prompt set; data is noisy. |

## Red flags — stop and reconsider

- "We'll just add `llms.txt` and we're done." → No engine has confirmed using it;
  it's not a substitute for server-rendered HTML. Low priority, unproven.
- "Schema markup will get us cited." → Over-claim. Markup helps parsing/rich
  results; it is not a proven citation lever, and mismatched markup risks a
  manual action.
- "Block GPTBot to protect our content." → That's a *training* bot; it doesn't
  affect citations. Blocking `OAI-SearchBot`/`PerplexityBot` is what removes you
  from answers.
- "Block Google-Extended to opt out of AI Overviews." → It can't; AI Overviews
  use the main Googlebot index.
- "The content is right there" (in a SPA). → Check raw HTML via curl, not
  DevTools. Hydrated DOM ≠ what crawlers see.
- "Let's add more keywords." → Keyword stuffing is inert-to-negative for GEO.

## Common mistakes

- Auditing the homepage only — audit a real **content** page (article/product).
- Trusting DevTools' rendered DOM instead of `curl`/View Source for the SSR check.
- Treating GEO as a replacement for SEO — it's **additive**; crawlability and
  E-E-A-T are shared prerequisites.
- Promising citation numbers. Engines are non-deterministic and personalized;
  report **trends**, never single snapshots, and state confidence honestly.
- Misreading the content-volume signal on CJK (Chinese/Japanese/Korean) or other
  non-space-delimited sites — naive word counts undercount badly. The audit
  script counts CJK characters as content units; if you eyeball raw HTML, judge
  by characters, not spaces.
