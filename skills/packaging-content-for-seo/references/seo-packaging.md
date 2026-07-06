# SEO packaging: structured data, social cards, canonical URLs

Reference material for the machine-readable layer of on-page SEO — the part
that lives in `<head>` and structured-data blocks rather than in the title and
body prose. Read the relevant section when a piece needs more than title / meta
/ headings / internal links.

**Sections:** [Canonical URL & slug](#canonical-url--slug) · [Open Graph tags](#open-graph-tags) · [Twitter Card tags](#twitter-card-tags) · [JSON-LD structured data](#json-ld-structured-data) · [What to hand back](#what-to-hand-back) · [Cross-references](#cross-references)

## Canonical URL & slug

- **Slug:** short, hyphenated, keyword-led, lowercase; drop stop-words
  (`the`, `a`, `of`) where it still reads. Prefer `legacy-storytelling-workshops`
  over `the-workshops-we-run-for-legacy-storytelling-2026`.
- **Canonical tag:** every page declares its own canonical URL so duplicate or
  parameterized paths don't split ranking signals:
  `<link rel="canonical" href="https://example.org/blog/legacy-storytelling-workshops" />`
- A press-clip recap that quotes another site still canonicalizes to *your*
  URL — you're not duplicating the outlet's page, you're citing it (with the
  backlink from the main skill workflow).

## Open Graph tags

Control how the page renders when shared on social/messaging. Provide these
four at minimum; reuse the SEO title/meta unless a punchier social framing is
wanted:

```html
<meta property="og:title"       content="Legacy Storytelling Workshops: What We Learned" />
<meta property="og:description" content="A short, human sentence — the same 120–158 char meta works." />
<meta property="og:image"       content="https://example.org/img/legacy-workshops.jpg" />
<meta property="og:url"         content="https://example.org/blog/legacy-storytelling-workshops" />
<meta property="og:type"        content="article" />
```

Image target: ~1200×630 px. If no image is available, flag it — a shared link
with no card image gets far less engagement.

## Twitter Card tags

```html
<meta name="twitter:card"        content="summary_large_image" />
<meta name="twitter:title"       content="Legacy Storytelling Workshops: What We Learned" />
<meta name="twitter:description" content="Same human sentence as the meta description." />
<meta name="twitter:image"       content="https://example.org/img/legacy-workshops.jpg" />
```

## JSON-LD structured data

Emit as a `<script type="application/ld+json">` block. This is what makes a
page eligible for rich results and gives AI answer engines a structured
summary. Use real values from the fact sheet — never invent an author, date,
or organization name.

**Article** (blog post / recap):

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Legacy Storytelling Workshops: What We Learned",
  "datePublished": "2026-02-14",
  "dateModified": "2026-02-14",
  "author": { "@type": "Person", "name": "[contributor from voice card]" },
  "publisher": {
    "@type": "Organization",
    "name": "[org name from fact sheet]",
    "logo": { "@type": "ImageObject", "url": "https://example.org/img/logo.png" }
  },
  "mainEntityOfPage": "https://example.org/blog/legacy-storytelling-workshops"
}
```

- Use `author` as an `Organization` instead of a `Person` when the piece is
  institutional (no byline) — mirror the voice decision from step 2 of the
  skill.
- `datePublished` / `dateModified` must be real; don't fabricate a date.

**Organization** (site-wide, usually on the homepage — reference, not per-post):

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "[org name from fact sheet]",
  "url": "https://example.org",
  "logo": "https://example.org/img/logo.png",
  "sameAs": ["[owned social URLs from the fact sheet]"]
}
```

Validate any block with Google's Rich Results Test / the Schema.org validator
before shipping.

## What to hand back

When a piece needs this layer, add to the packaging bundle: the slug + canonical
URL, the OG + Twitter tags, and the JSON-LD Article block — as
copy-paste-ready snippets for the CMS's custom-head / SEO fields. Keep values
sourced from the fact sheet and voice card, same as the rest of the skill.

## Cross-references

- For getting crawled, rendered, and **cited by AI answer engines**
  (ChatGPT/Perplexity/AI Overviews) — beyond classic SEO — see the
  `web-quality:optimizing-for-ai-search` skill (llms.txt, AI-crawler robots
  rules, citation-friendly structure).
- For auditing a *live* site's SEO/Core Web Vitals, accessibility, and
  crawlability end to end, see `web-quality:auditing-website-quality`.
