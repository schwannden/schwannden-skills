# SEO & Performance Checklist

Each item: **check → pass (concrete) → how to verify.** `[static]` = caught by
`scripts/static-audit.sh`. Authoritative Core Web Vitals verdict = **field** data
(CrUX/Search Console/PSI) at the **75th percentile**, not a lab score.

## 1. On-page SEO

- **Title** `[static]` — one `<title>`, ~50–60 chars (~600px), unique, keyword near front. Verify: Lighthouse SEO; Screaming Frog duplicate/length.
- **Meta description** `[static]` — one, ~120–160 chars, unique. Not a ranking factor but drives CTR.
- **Single H1 + hierarchy** `[partial static]` — one `<h1>`, no skipped levels.
- **Semantic URLs** — lowercase, hyphenated, shallow, no query-string IDs for canonical content.
- **Internal linking** — important pages within ~3 clicks of home; contextual links. Verify: Screaming Frog inlinks; Search Console → Links.
- **Descriptive anchor text** — no "click here". Verify: Lighthouse "Links have descriptive text".
- **Canonical** `[static]` — `<link rel="canonical">` to the preferred absolute URL; self-referential on canonical pages; no conflicting signals. Verify: Search Console URL Inspection (user-declared = Google-selected).
- **Language / hreflang** `[partial static]` — `<html lang>`; multilingual uses reciprocal `hreflang` + `x-default`, valid ISO codes.

## 2. Crawlability & indexing

- **robots.txt** `[static]` — at `/robots.txt`, 200, doesn't block CSS/JS or key pages, references the sitemap. Verify: Search Console robots report.
- **XML sitemap** `[static]` — valid, lists only canonical indexable 200 URLs, <50k URLs/<50MB per file, submitted. Verify: Search Console → Sitemaps "Success".
- **Meta robots / noindex** `[static]` — indexable pages have **no** `noindex`; only thin/private pages use it. Verify: Search Console URL Inspection "Indexing allowed? Yes".
- **Canonicalization** — one host variant (https + www-or-not); variants 301 to it. Verify: Search Console "Duplicate, Google chose different canonical" ≈ 0.
- **No orphan pages** — every indexable page has ≥1 internal link. Verify: Screaming Frog crawl vs sitemap → Orphan URLs.
- **JS-rendered content** — critical content + links in server-rendered/pre-rendered HTML (SSR/SSG/dynamic rendering), not solely client-side. Verify: Search Console URL Inspection → "View crawled page"; compare raw `curl` HTML vs DOM.
- **HTTP status codes** — live=200, permanent moves=301 (not 302), dead=404/410, no soft-404s, no redirect chains/loops.

## 3. Structured data

- **Format** `[static detects presence]` — JSON-LD in `<script type="application/ld+json">` (Google's recommended format). Verify: validator.schema.org — 0 errors.
- **Type coverage** — `Organization`+`WebSite` on home; `Article`/`BlogPosting` on posts; `BreadcrumbList` on deep pages; `Person`/`Product`/`Event` where content matches.
- **Required properties** — all Google-required + recommended fields; data matches visible content (no markup-only). Verify: Rich Results Test "Valid items", 0 errors.
- **Rich result eligibility** — Verify: Rich Results Test "eligible for rich results"; Search Console Enhancements 0 errors.
- **Note:** Google deprecated FAQ/HowTo rich results for most sites (2023) — markup is still valid schema.org and useful to other consumers (LLMs/AI overviews); keep it, don't expect SERP rich results.

## 4. Social / sharing metadata

- **Open Graph** `[static]` — `og:title`, `og:description`, `og:type`, `og:url`, **`og:image`** (≥1200×630, 1.91:1, <5MB, absolute URL). Verify: Facebook Sharing Debugger; opengraph.xyz.
- **Twitter/X cards** `[static]` — `twitter:card` (`summary_large_image` for articles), `twitter:title/description/image`; falls back to OG. **Common bug:** `summary_large_image` set but no image → preview has no image.
- **Favicon** — `<link rel="icon">` (200) + `apple-touch-icon` (180×180).
- **Link preview** — paste URL into Slack/X/LinkedIn → title + description + image. Verify: live paste + opengraph.xyz.

## 5. Core Web Vitals & performance

**Thresholds (verified, measured at p75 field data):**

| Metric | Good | Needs improvement | Poor |
|--------|------|-------------------|------|
| **LCP** (Largest Contentful Paint) | **≤ 2.5s** | 2.5–4.0s | > 4.0s |
| **INP** (Interaction to Next Paint) | **≤ 200ms** | 200–500ms | > 500ms |
| **CLS** (Cumulative Layout Shift) | **≤ 0.1** | 0.1–0.25 | > 0.25 |

**INP replaced FID** as a Core Web Vital on **2024-03-12** (FID's old ≤100ms
threshold is obsolete). INP measures responsiveness across **all** interactions
at p75; FID only measured the first interaction's input delay.

Supporting / diagnostic:

- **TTFB** — ≤ **800ms** good (LCP diagnostic, not a CWV).
- **FCP** — ≤ **1.8s** good.
- **Render-blocking** — defer/async non-critical JS, inline critical CSS. Verify: Lighthouse "Eliminate render-blocking resources".
- **Image optimization** — AVIF (preferred)/WebP; correctly sized; explicit `width`/`height` (prevents CLS); `loading="lazy"` below the fold, **never** the LCP image.
- **Font loading** — `font-display: swap`/`optional`; preload key fonts; self-host or `preconnect`; subset. Verify: Lighthouse "Ensure text remains visible during webfont load".
- **Minification** — production CSS/JS minified; code-split; remove unused.
- **Caching** `[partial static]` — long `Cache-Control max-age` + fingerprinted filenames. Verify: `curl -I` cache headers.
- **Compression** `[static]` — Brotli or gzip on text assets. Verify: `curl -H "Accept-Encoding: br,gzip" -I`.
- **CDN / protocol** — static assets via CDN; HTTP/2 or HTTP/3.

## 6. Page experience signals

- **HTTPS** `[static]` — all pages HTTPS, valid cert, HTTP 301→HTTPS, no mixed content. Verify: Lighthouse mixed-content; SSL Labs.
- **Mobile-friendly** — see `mobile-friendly.md`.
- **No intrusive interstitials** — no full-screen popup blocking content on load (cookie/legal exempt if reasonable).
- **Safe Browsing** — not flagged for malware/deceptive content. Verify: Search Console → Security & Manual Actions "No issues".

## 7. Tool → signal map

| Tool | Data | Pass signal |
|------|------|-------------|
| Lighthouse (DevTools/CLI) | lab | scores ≥90; named audits passed. Lab CWV are estimates. |
| **PageSpeed Insights** | field+lab | **"Core Web Vitals Assessment: Passed"** (all 3 good at p75) |
| Chrome UX Report (CrUX) | field | the authoritative record; 28-day rolling p75 |
| Search Console | field+index | CWV report "Good"; Page indexing errors ≈0; Enhancements valid |
| Rich Results Test | live render | "eligible for rich results", 0 errors |
| validator.schema.org | static | 0 errors (broader than Google) |
| WebPageTest | lab (real devices) | TTFB ≤800ms; no long render-blocking chains; assets compressed+cached |

**Authoritative CWV pass = field data, p75, all three "Good."** Lab scores are
diagnostic and can diverge (especially INP, which needs real interactions).
