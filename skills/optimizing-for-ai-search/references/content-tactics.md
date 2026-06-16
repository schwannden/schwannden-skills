# Content tactics for AI citation

Reference for Step 4. Grounded in the Princeton GEO study (Aggarwal et al.,
"GEO: Generative Engine Optimization", arXiv 2311.09735, KDD 2024) — ~10,000
queries across 9 domains, validated on Perplexity and a Bing-Chat-style engine —
plus corroborating industry data. The study is the strongest evidence in this
space; treat per-method percentages as ranges, not precise constants, and note
the gains have been pressure-tested by critics (causality is not fully settled).

## Contents

- [What the study measured](#what-the-study-measured)
- [Ranked tactics (with evidence)](#ranked-tactics-with-evidence)
- [The on-page principles](#the-on-page-principles)
- [Anti-patterns (measured 0% to negative)](#anti-patterns-measured-0-to-negative)
- [Per-engine nuance](#per-engine-nuance)

## What the study measured

Two metrics: **Position-Adjusted Word Count** (how much of the answer your source
contributes, weighted by position) and **Subjective Impression** (an LLM-judge
score over relevance, influence, uniqueness, click-likelihood). The right content
changes raised source visibility **up to ~40%**, and — reversing classic SEO —
**lower-ranked pages benefited most**. There is no universal best tactic;
efficacy is **domain-specific**.

## Ranked tactics (with evidence)

| Tactic | Effect (Position-Adjusted Word Count) | Strongest in |
|---|---|---|
| **Add quotations** (from named experts/sources) | ~+30–40% (top result) | People & Society, History, Explanation |
| **Add statistics** (concrete numbers vs. vague claims) | ~+30–40% | Law/Government, Opinion, fact-driven |
| **Cite sources** (credible inline references) | ~+30–40%; up to ~+115% for a page ranked ~5th | Law, factual |
| **Fluency optimization** (clearer prose) | ~+15–30% | Broad |
| **Authoritative language** (confident, definitive) | ~+10–20% (mixed) | History, Explanation |
| **Keyword stuffing** | ~0% to slightly **negative** | — (do not use) |
| Easy-to-understand / forced simplification | ~0 or negative | — |

The three reliable winners — **quotations, statistics, source citations** — are
all **verifiable factual density**. Lead with them.

## The on-page principles

1. **Answer-first / inverted pyramid.** Lead each section with a direct,
   self-contained answer in ~the first 40–60 words; elaborate after. Burying the
   answer loses the citation.
2. **Chunk and conquer.** RAG retrieves and scores *passages*, not whole pages.
   Every H2/H3 should make sense lifted out of context — avoid pronouns/back-
   references that break when isolated. One idea per chunk.
3. **Factual density.** Insert a concrete statistic roughly every 150–200 words;
   replace vague claims with numbers; quote named experts; cite primary sources
   inline. Publish **original data/research** — unique facts that exist nowhere
   else become the source the model *must* attribute.
4. **Question-style headings + a genuine FAQ.** Phrase headings as the real
   questions users ask; mirror conversational prompts.
5. **E-E-A-T** (Experience, Expertise, Authoritativeness, Trust). Real author
   bylines with bios and credentials; `Person`/author markup; consistent author
   identity across the web. LLMs use these to weight source trust.
6. **Freshness.** Show explicit dates ("as of 2026", `dateModified`) and refresh
   regularly — AI citations skew heavily toward recent content (a large share of
   cited pages are only weeks old; staleness is penalized hardest on Perplexity).
7. **Topical authority.** Pillar + cluster pages with deliberate internal
   linking; cover the topic comprehensively; reference entities consistently to
   align with the knowledge graph.
8. **Machine-parseable formatting.** Lists, comparison tables, explicit
   definitions, descriptive semantic headings — models parse these far more
   reliably than dense prose. Keep load-bearing facts in **plain HTML text**, not
   baked into images or hidden behind tabs/accordions/"read more".

## Anti-patterns (measured 0% to negative)

- **Keyword stuffing** — inert or harmful; classic SEO density does not transfer.
- **Padding / pure persuasion / fluff** — ~0% benefit; wastes the chunk.
- **Artificial simplification** — dumbing content down did not help.
- **Content behind interaction/JS/paywall/login** — not retrievable; if a fact
  matters, it must be in the initial server-rendered HTML as text.

## Per-engine nuance

- **ChatGPT (SearchGPT)** — favors encyclopedic, comprehensive coverage.
- **Perplexity** — rewards recency and community examples; penalizes keyword
  stuffing most; easiest to monitor (transparent inline citations).
- **Google AI Overviews / AI Mode** — lean on existing top-ranking pages, so
  classic SEO still feeds GEO here. Highest commercial value.

Two surfaces, two ceilings: principles 1–8 are **on-page** (you control them);
off-site authority (referring domains, third-party mentions, digital PR) drives a
large additional share of citation probability and is **not** editable on the
page — see the skill's Step 6.
