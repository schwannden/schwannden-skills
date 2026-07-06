---
name: building-brand-kits
description: Scaffolds a brand kit (fact sheet, voice card with register matrix, media-coverage inventory, and a de-AI-flavor filter) as blank copy-and-adapt templates for the user's own organization. Use when starting content/marketing/PR work for an organization and no documented brand voice or fact sheet exists yet, or when other drafting/QA skills need a shared, consistent source of facts and voice instead of each reconstructing them independently.
---

# Building Brand Kits

## Overview

A brand kit is a small set of reference documents — facts, voice, press
history, and an AI-tell checklist — that every piece of content for an
organization should draw from, instead of each drafting session
reconstructing (and drifting from) the same facts and tone independently.

This skill does not ship anyone's real data. It scaffolds **blank,
copy-and-adapt templates** for the user's own organization, plus one
ready-to-use reference file (the de-AI-flavor filter, which is generic by
design). Fill the templates in for your organization, save the filled copies
in your own project, and point your other content/drafting skills at them.

**Scope — the editorial half of a brand kit, not the visual half.** A full
brand identity has two layers: the *editorial* layer this skill covers (facts,
voice, register, press history) and a *visual* layer (logo usage, color
palette, type scale, spacing/grid) that a design system captures as **design
tokens** — platform-agnostic name/value pairs — organized in Brad Frost's
**Atomic Design** hierarchy (tokens → atoms → molecules → organisms →
templates → pages). This skill intentionally scopes to the editorial layer that
drafting/QA skills read; if you also need the visual layer, capture it
separately (e.g. a Figma library or a `design-tokens.json`) rather than
stretching these text templates to hold color and type decisions.

## When to Use

- Starting content, marketing, PR, or sales-collateral work for an
  organization that has no documented fact sheet or voice guide yet.
- A drafting or QA skill needs canonical facts/voice to check against instead
  of reconstructing them per-request (see the consumer table below).
- An existing brand kit has gone stale (new stats, new leadership, a new
  audience segment, new press coverage) and needs a refresh pass.

## How to build each artifact

Work through these in order — later artifacts reference earlier ones.

1. **Fact sheet** (`assets/fact-sheet-template.md`) — Copy the template into
   your project. Fill in identity, the canonical stat block, leadership,
   named case studies/partners, recognition, product/service lines,
   audience/funnel segments, owned channels, and contact info. Pull from
   your own website, "About"/"Team" pages, and internal reporting — not from
   memory or inference. Note the source and date next to any number that
   changes over time, so staleness is visible at a glance.

2. **Voice card** (`assets/voice-card-template.md`) — Fill in brand
   personality traits and anti-personas first (these are usually easy to
   agree on). Then build the register matrix: add one row per audience
   segment you identified in the fact sheet's "Audiences / funnels" section,
   using the *same segment names* in both files. If your org has named
   bylined contributors (a founder's column, guest authors), fingerprint
   each one's recurring themes and quirks the same way you'd document a
   distinct voice — don't flatten them into "the brand voice." Populate the
   do/don't table as real examples surface; it's meant to grow, not to be
   complete on day one.

3. **Media-coverage inventory** (`assets/media-coverage-inventory-template.md`)
   — Start with the outlet list if you know who's covered you, then add rows
   only for clips you've actually read. Never backfill a date, headline, or
   quote you can't verify.

4. **De-AI-flavor filter** (`references/de-ai-flavor-filter.md`) — This one
   is ready to use as-is; it's organization-agnostic. Point any drafting or
   QA skill at it directly, or copy it into your project if you want to
   extend it with organization-specific banned phrases (a competitor's
   slogan you keep echoing by accident, a cliché your industry overuses).

## Which sibling skills consume which artifact

If you've also installed skills that draft or QA content, this is the kind
of consumer relationship a filled-in brand kit typically supports:

| Skill | Consumes |
|---|---|
| `auditing-brand-voice` | Voice card (register matrix, do/don't examples) |
| `writing-esg-sponsorship-proposals` | Fact sheet (case studies, stats, corporate/B2B register), voice card (formal register) |
| `reporting-marketing-performance` | Fact sheet (canonical stat block, audience/funnel map) |
| `repurposing-press-coverage` | Media-coverage inventory |
| `packaging-content-for-seo` | Fact sheet (stats, product/service lines), media-coverage inventory (backlink/citation candidates) |
| `writing-short-form-video-scripts` | Voice card (register + tone), de-AI-flavor filter |

None of these are required dependencies — treat the table as "if installed,
this is what it reads," not as a hard coupling.

## Where to save it in your project

There's no fixed requirement here — search your project first for an
existing docs/brand location before assuming one. If nothing exists yet, a
reasonable convention is:

```
docs/brand/fact-sheet.md
docs/brand/voice-card.md
docs/brand/media-coverage-inventory.md
```

Copy the de-AI-flavor filter alongside them only if you plan to extend it;
otherwise skills can reference this skill's copy directly.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Hardcoding a stat inside a skill's own instructions instead of reading it from the fact sheet | Always read the current number from the fact sheet at run time — it changes over time |
| Inventing press-clip details not in the media-coverage inventory | If a clip isn't logged yet, ask for the source URL/text — never fabricate outlet, date, or quote |
| Applying one audience segment's vocabulary (e.g. formal B2B/ESG framing) to another segment's content (e.g. warm consumer copy), or vice versa | Check the voice card's register matrix before drafting — registers are intentionally different |
| Using testimonial/quote framing when the org's stat-block-only credibility pattern is deliberate (or vice versa) | Check what the voice card says the org's proof style actually is — don't assume testimonials are always wanted or always forbidden |
| Committing a filled-in fact sheet with real company data into a shared/published skill package | Save your filled-in copies in your own project's docs (e.g. `docs/brand/`), never inside this skill's own folder — this skill's templates must stay blank for anyone else who installs it |

## Source

Distilled from a working brand-kit pattern used on a client engagement, then
genericized into blank templates so any organization can populate its own
copy. The register-matrix and voice-fingerprinting techniques in
`assets/voice-card-template.md` are the reusable part — the structure
generalizes even though the underlying content in this repo is entirely
placeholder.
