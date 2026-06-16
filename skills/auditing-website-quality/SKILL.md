---
name: auditing-website-quality
description: Use when checking whether a website or web app is mobile-friendly, accessible, PWA-installable, or SEO/performance-optimized — auditing a site before launch or review, diagnosing why it isn't installable/indexable/responsive, or producing a prioritized fix list. Runs a curl-based static pass (manifest, meta, Open Graph, JSON-LD, robots/sitemap, headings, transport headers) then routes to per-dimension checklists with concrete pass thresholds (WCAG contrast, Core Web Vitals LCP/INP/CLS, tap-target sizes) and the lab/manual tools (Lighthouse, PageSpeed Insights field data, axe, DevTools Application, PWABuilder) the static pass cannot replace.
---

# Auditing Website Quality

## Overview

Audit a live website across four built-in dimensions — **mobile-friendliness**,
**accessibility**, **PWA-readiness**, **SEO/performance** — plus an optional fifth,
**GEO/AEO** (AI-search citability), when a skill for it is installed. Each
dimension is an independent, read-only parallel agent, so adding one is just
adding an agent.

**Core principle — two layers, and don't confuse them:**

1. **Static layer (cheap, scriptable).** Anything in the raw HTML + HTTP headers:
   manifest link, meta tags, Open Graph, JSON-LD, robots/sitemap, heading
   structure, transport headers. `scripts/static-audit.sh` extracts all of it in
   one fetch. **No browser required.**
2. **Lab/manual layer (the verdict).** Core Web Vitals field data, tap-target
   size, colour contrast, keyboard/screen-reader operability, offline support.
   These need Lighthouse, PageSpeed Insights, axe, DevTools, and real testing.

**A green static pass is necessary but never sufficient.** Automated a11y tools
catch only ~30–40% of issues; the authoritative Core Web Vitals verdict is field
data, not a lab score. Report a clean static run as "static checks pass," never
as "the site is accessible / fast / installable."

## When to Use

- Pre-launch or pre-review audit of a site or web app
- "Why isn't my site installable / indexed / responsive / shareable?"
- Producing a prioritized fix list for a frontend
- Verifying a fix actually landed

**When NOT to use:** pure GEO/AEO (getting cited by AI assistants) — that's the
`optimizing-for-ai-search` skill, which complements this one. Use both for a full
web-presence audit.

## The audit dimensions

Each dimension is an independent audit unit with its own reference file. The first
four are built in; GEO/AEO is an optional fifth (see [Pluggable dimensions](#pluggable-dimensions-geoaeo-and-beyond)).

| Dimension | Reference | What it covers |
|-----------|-----------|----------------|
| Mobile-friendly | `references/mobile-friendly.md` | Viewport, tap targets, readable text, responsive images, interstitials, safe-area/notch |
| Accessibility | `references/accessibility.md` | WCAG 2.2 AA: semantics, contrast, keyboard/focus, forms, ARIA, motion |
| PWA-readiness | `references/pwa-readiness.md` | Manifest, service worker/offline, cross-platform install, modern capabilities |
| SEO/performance | `references/seo-performance.md` | On-page SEO, indexing, structured data, social meta, Core Web Vitals |
| GEO/AEO *(optional)* | external skill | AI-search citability — only when a GEO/AEO skill is installed |

## Workflow — parallel dimension audit

Dimensions are independent (no shared state), so audit them concurrently — one
read-only subagent per dimension, the same pattern as `reviewing-code`'s lenses.

1. **One shared fetch.** Run `./scripts/static-audit.sh <url>` once. It is a single
   HTTP fetch covering every dimension; capture its output and hand the same copy
   to each agent — don't make five agents re-fetch the page.
2. **Dispatch one read-only subagent per in-scope dimension, in parallel** (add the
   GEO agent only if that skill is installed). Give each the contract below.
3. **Aggregate by severity** into one report — Critical / Important / Suggestions.
   De-dupe overlaps (structured data, SSR, robots show up in both SEO and GEO —
   keep one finding, note both lenses).
4. **Hand back the consolidated lab/manual checklist.** Agents can't run a browser
   (see below); present the merged Lighthouse / PSI / axe / keyboard / screen-reader
   / DevTools steps for the human (or main agent) to run, then fold results in.

### Per-dimension agent contract

Each dimension agent is **read-only** and receives exactly:

- The target URL(s) and the shared `static-audit.sh` output.
- One instruction: *"Load `references/<dimension>.md`. Audit `<url>` for THIS
  dimension only. Do any deeper dimension-specific static analysis (extra pages,
  closer DOM/markup inspection). Return findings as: severity · the concrete
  threshold · location (file/selector/tag) · the fix. Separately list the
  lab/manual checks you could NOT perform."*
- Constraints: don't edit anything; don't stray into other dimensions; return
  structured data, not prose.

**Honest limit — what an agent cannot do.** A subagent has no browser, so it does
the *static + analysis + triage + fix-list* layer only. It **cannot** run
Lighthouse, PageSpeed Insights, axe, a screen reader, or DevTools Application —
the tools that produce the authoritative verdicts (Core Web Vitals field data,
contrast, keyboard/SR operability, installability/offline). Those run outside the
agent and get folded in. An all-green agent pass = "static checks pass," never
"the site is fast / accessible / installable."

## Pluggable dimensions (GEO/AEO and beyond)

A new dimension is a new parallel agent — nothing else changes. GEO/AEO (being
reached, read, and *cited* by AI answer engines) is the natural fifth:

- **If a GEO/AEO skill is installed** (e.g. `optimizing-for-ai-search`), dispatch
  it as another parallel agent with the same contract, pointed at its own audit
  (it ships its own `geo-audit.sh` + references), and fold its findings into the
  same severity buckets.
- **If not installed**, note GEO as out of scope rather than half-doing it.

GEO and this skill's SEO dimension overlap on structured data, SSR/rendering, and
robots/sitemap but optimize different goals (SERP rank + Core Web Vitals vs
passage-level citability). When both run, de-dupe shared findings and keep both
lenses' framing.

## Quick Reference — pass thresholds

| Signal | Pass |
|--------|------|
| Viewport | `width=device-width, initial-scale=1`; **no** `user-scalable=no`/`maximum-scale=1` |
| Tap target | ≥24×24px (WCAG 2.5.8 AA min); 44–48px recommended; ~8px gap |
| Body font | ≥16px; legible without zoom |
| Contrast | **4.5:1** normal text · **3:1** large (≥24px, or ≥18.66px bold) + UI/icons · 3:1 focus ring |
| LCP | **≤ 2.5s** (good) at p75 field data |
| INP | **≤ 200ms** (good) at p75 — replaced FID on 2024-03-12 |
| CLS | **≤ 0.1** (good) at p75 |
| TTFB | ≤ 800ms (LCP diagnostic) |
| Title / description | one `<title>` ~50–60 chars · meta description ~120–160 chars |
| Manifest (Chromium install) | `name`/`short_name`, `start_url`, `display`≠`browser`, icons incl. **192** + **512** PNG, one `maskable` |

## Tools (and what static can't see)

| Tool | Layer | Use for |
|------|-------|---------|
| `scripts/static-audit.sh` | static | manifest/meta/OG/JSON-LD/robots/sitemap/headers/headings in one fetch |
| Lighthouse (DevTools / `npx lighthouse`) | lab | Mobile audit: perf, a11y, SEO, best-practices. **No PWA category since v12.** |
| PageSpeed Insights (pagespeed.web.dev) | field+lab | **Authoritative CWV verdict** (CrUX p75) + Lighthouse lab |
| axe DevTools / WAVE | lab | ~30–40% of a11y issues (contrast, labels, ARIA, structure) |
| keyboard + VoiceOver/NVDA | manual | the other ~60% — operability, focus order, announcements |
| DevTools → Application | manual | Manifest validity, service worker state, offline, maskable icons |
| PWABuilder.com | lab | PWA report card + store packaging |
| validator.schema.org / Rich Results Test | lab | structured-data validity + rich-result eligibility |

Google **retired** the standalone Mobile-Friendly Test, its API, and the Mobile
Usability report (2023-12-01) → use Lighthouse mobile + PSI instead.

## The two PWA "bars" (common confusion)

Since Chrome 108 (Android) / 112 (desktop), a service worker is **no longer
required to be installable** via the menu — only a valid manifest + HTTPS.
A service worker (with a fetch handler) is still required for **offline** and to
fire the **automatic `beforeinstallprompt`**. So distinguish:

- **Installable via menu** = HTTPS + valid manifest (icons 192+512, `display`≠browser).
- **Auto-prompted + works offline** = the above **plus** a registered service worker.

iOS honors only some manifest fields (`name`, `short_name`, `start_url`, `scope`,
`display: standalone`, `theme_color`, icons ≥15.4), ignores `background_color`/
`shortcuts`, has no install prompt (Share → Add to Home Screen), and supports Web
Push only for **installed** PWAs on iOS ≥16.4. Details in the PWA reference.

## Common Mistakes

| Mistake | Reality |
|---------|---------|
| "Lighthouse is green, so it's accessible" | Automation catches ~30–40%. Keyboard + screen reader required. |
| "Lighthouse PWA score" | Lighthouse dropped the PWA category in v12. Use DevTools Application + PWABuilder. |
| Reading lab CWV as the verdict | The verdict is **field** data (CrUX/PSI/Search Console) at p75. Lab is diagnostic. |
| `og:image` missing but `twitter:card=summary_large_image` set | Link previews still show no image. The card needs an image. |
| Lazy-loading the LCP/hero image | Hurts LCP. Lazy-load below-the-fold only; eager + `fetchpriority="high"` the hero. |
| `user-scalable=no` "for a cleaner mobile look" | Blocks pinch-zoom = accessibility fail. Remove it. |
| Treating "installable" and "works offline" as one thing | Two separate bars — see above. |

## Worked Example — `resume.schwannden.com` (benchmark)

A Next.js static site on GitHub Pages. The shared `static-audit.sh` pass (step 1)
fed the dimension agents; their aggregated findings:

- **SEO: strong.** Title (53 chars), meta description, `lang="en"`, single `<h1>`,
  robots.txt + sitemap.xml (200), HTTP→HTTPS 301, gzip, rich JSON-LD (Person,
  ProfilePage, Occupation, Organization, Article, WebSite, SoftwareApplication).
- **FAIL — no `og:image`/`twitter:image`** despite `twitter:card=summary_large_image`
  → social link previews render with no image. High-value, one-tag fix.
- **WARN — no `rel=canonical`** and **no HSTS** header (GitHub Pages limitation).
- **FAIL — zero PWA readiness:** no manifest, no `theme-color`, no
  `apple-touch-icon`, no service worker → not installable on any platform.
- **Static can't judge:** mobile tap targets/CWV, contrast, keyboard/screen-reader
  → flagged for Lighthouse mobile + PSI field data + axe.

Prioritized fix list this produced: (1) add `og:image` + `twitter:image`;
(2) decide if PWA-install is a goal — if yes, add manifest + icons + theme-color +
apple-touch-icon (+ service worker for offline); (3) add canonical; (4) run
Lighthouse mobile + PSI to confirm CWV and tap targets.
