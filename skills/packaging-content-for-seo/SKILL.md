---
name: packaging-content-for-seo
description: Use when packaging a finished blog draft, static page, or press-clip recap into title/meta-description/section-heading/internal-link SEO metadata before publishing — the structural and distribution layer only, independent of any specific CMS. Not for rewriting the draft's prose or brand voice; that belongs to auditing-brand-voice.
---

# Packaging Content for SEO

## Required Background

Look for this project's brand-kit reference material — commonly produced via the `building-brand-kits` skill — for the facts this skill needs:

- **Fact sheet** — for the org's current product/service lines (used to derive keyword focus), canonical URLs, and owned channels (used to find internal-link targets).
- **Voice card** — for which named/bylined contributor or institutional voice applies to the piece, which drives the author-bio block and the register the title/meta should match.
- **Media-coverage inventory** — if the input is press-sourced, for the clip's logged outlet/date/angle.

If none of this exists, ask the user for the relevant facts or flag the gap explicitly — never invent stats, URLs, contributor names, or a keyword list. This skill applies that material; it does not redefine it.

## Overview

A surprisingly common gap in otherwise decent writing is structural, not stylistic: titles that lead with the brand name instead of a keyword, meta descriptions that are just a comma-separated keyword dump, zero real H1/H2/H3 structure in the CMS's section-heading fields, no internal linking, and press hits that never get repurposed into a backlink. This skill packages a finished draft or clip into those pieces — title, meta description, section-heading map, internal links, an optional press-repurposing note, and an author-bio block — without touching the body prose or voice.

## When to Use

- A blog post or static page is finished or near-finished and needs a title, meta description, section headings, and internal links before publishing.
- A press-clip URL or text needs a short SEO repurposing note (pull-quote + commentary + backlink) — **not** a full repurposing package; hand that off to `repurposing-press-coverage`.
- **Not for:** rewriting or "improving" the draft's actual voice or content — that's `auditing-brand-voice`'s job. This skill only ever touches title/meta/headings/links.

## Quick Reference

| Output | Spec |
|---|---|
| Page title | ≤60 chars, keyword-led (not brand-name-only) |
| Meta description | 120–158 chars, one or two natural sentences, never a comma-separated keyword list |
| Section-title map | Exact text for the CMS's H1/H2/H3 section-heading fields |
| Internal links | 2–5 suggestions, each with descriptive anchor text (never "click here") + target URL |
| Press repurposing note (if press-sourced) | Pull-quote + 1–2 sentence commentary + backlink to outlet — short, not a full package |
| Author-bio/credential block | Ties to the named contributor or institutional voice per the project's voice-card, for Google **E-E-A-T** (Experience, Expertise, Authoritativeness, Trustworthiness) signal |
| Machine-readable layer (optional) | Canonical URL + slug, Open Graph / Twitter Card tags, and JSON-LD structured data — see `references/seo-packaging.md` |

**On the CMS:** the exact field names for title, meta, and section headings vary by platform (Strikingly, Webflow, WordPress, Squarespace, a custom CMS...) — find where this project's CMS exposes those fields, but the content rules in this skill don't change based on which one it is.

**On keyword focus:** don't assume a fixed keyword list. Derive the current focus from the project's fact sheet's product/service lines, or ask the user which keyword(s) this specific piece is actually about.

## Workflow

1. **Read the input.** Get the full draft (or press-clip text/URL) and identify which page(s) or section(s) it should support.
2. **Identify voice.** Check the project's voice-card for whether this piece carries a named contributor's voice or an institutional voice — this determines the author-bio block and the register the title/meta should match (e.g. consumer-facing vs. B2B/partner-facing vs. no-byline institutional).
3. **Draft the title.** Lead with a keyword the draft is actually about — drawn from the fact sheet's product/service lines, or confirmed with the user — not just the org name alone. ≤60 chars.
4. **Draft the meta description.** Write it as a real sentence a person would read, summarizing what the page delivers, 120–158 chars. Never string keywords together with commas.
5. **Map section titles.** Go through the draft's actual paragraph breaks and assign one H1 (page title, usually the same as the title) + H2s for each major section + H3s for sub-points, if any. This is exact text to paste into the CMS's section-heading fields — not a suggestion to restructure the draft.
6. **Find 2–5 internal links.** Match draft content to existing pages and related blog posts. Write natural, descriptive anchor text — never "click here" or a bare URL. For example, if the draft mentions a program the org runs, link it to that program's page with anchor text like "our legacy-storytelling workshops" pointing at `example.org/programs/legacy-storytelling`, rather than a generic "learn more" pointing at the homepage. Link with the **pillar-page / topic-cluster** model in mind: point supporting posts at the broad "pillar" page for their topic and back, so related content reinforces one hub rather than scattering authority across disconnected pages.
7. **If press-sourced:** add a short repurposing note — one pull-quote from the clip, 1–2 sentences of original commentary framing why it matters, and a backlink to the outlet. Check the media-coverage inventory for the clip's logged details (outlet, date, angle) rather than inventing them; if it isn't logged, ask for the source instead of fabricating it.
8. **Add the author-bio/credential block** for E-E-A-T, matching the voice identified in step 2.
9. **Add the machine-readable layer if the piece warrants it.** For a blog post or page that will be shared or indexed, hand over the slug + canonical URL, Open Graph / Twitter Card tags, and a JSON-LD Article block — see `references/seo-packaging.md` for the exact snippets and rules (real dates/author only; institutional pieces use an `Organization` author).
10. **Run every new text you wrote (title, meta, headings, anchors, bio) through `auditing-brand-voice`'s de-AI-flavor pass.** Do not run the original draft body through it — this skill doesn't touch that.
11. **Return the bundle** as: title / meta description / section-title map / internal links / (press note if applicable) / author-bio block / (machine-readable layer if produced). Nothing else changes in the draft.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Calling "no H1/H2 in the rendered HTML" an unfixable platform limitation | Most CMS section-title fields *do* render real headings — hand over exact text for those fields, don't punt on it |
| Writing a comma-separated keyword string as the meta description | Always write a natural sentence; keyword-dumps read as spam and undersell copy that's usually better than that |
| Delivering 0 or 1 internal link | Every packaging output needs 2–5 link suggestions with anchor text — go find them, don't skip this step |
| Rewriting the draft's voice while "optimizing" a title or heading | Only title/meta/headings/links are in scope; if a heading requires rewording body content to fit, stop and flag it instead of touching prose |
| Producing a full press-repurposing package here | That's `repurposing-press-coverage`'s job — this skill only writes the short note (quote + commentary + backlink) |
| Inventing a press clip's outlet/date/quote when it isn't in the media-coverage inventory | Ask for the source URL/text instead of fabricating it |
| Running the de-AI-flavor pass over the original draft body | Only run it over the *new* text this skill generates (title/meta/headings/anchors/bio) |
| Skipping the voice check before drafting the title/meta/bio | Check the voice-card first — a B2B/partner-facing title reads wrong on a consumer-facing post and vice versa |
| Assuming a fixed keyword list instead of checking the current fact sheet | Product/service lines and priorities change; re-derive keyword focus each time rather than reusing a stale list |
| Leading the title with the brand name alone | Lead with the keyword the page is actually about; the brand name can appear, but not as the whole title |

## Related Skills

If this project doesn't yet have brand-kit reference material (fact sheet, voice-card, media-coverage inventory), run `building-brand-kits` first to produce it. For a voice/register/tone check on the *original* draft prose (out of scope for this skill), use `auditing-brand-voice`. For a full press-repurposing package beyond the short note in step 7, use `repurposing-press-coverage`. For making a page crawlable, renderable, and **citable by AI answer engines** (llms.txt, AI-crawler robots rules, citation-friendly structure), use `web-quality:optimizing-for-ai-search`; for auditing a *live* site's SEO/Core Web Vitals, accessibility, and crawlability end to end, use `web-quality:auditing-website-quality`.
