---
name: repurposing-press-coverage
description: Use when reactivating a dormant press-coverage archive by turning one existing, already-published press clip (a URL or pasted article) into a multi-format content package — an SEO blog recap, 3-5 platform-native social captions, and an ESG/CSR-deck snippet — and logging it into the project's media-coverage inventory, especially when the goal is compounding a flat, unlinked list of past coverage into an ongoing content asset rather than pitching new coverage.
---

# Repurposing Press Coverage

## Overview

Most organizations with any press history end up with earned coverage sitting
as a flat, unlinked list — real credibility that generates zero ongoing SEO
or social value once the initial publication date passes. This skill turns
**one existing clip** into a repurposing package (blog recap, social
captions, ESG snippet) and logs it, so the archive compounds into a real
asset over repeated runs instead of staying a dead list.

## Required Background

Look for this project's brand-kit reference material, commonly produced by
the `building-brand-kits` skill:

- **Fact sheet** (stats, owned channels, case studies) — cite stats/case
  studies from here, never from memory.
- **Voice card** (register matrix, and any bylined-contributor voice
  fingerprints) — read before finalizing any new text this skill generates.
- **De-AI-flavor filter** — required for step 5 below.
- **Media-coverage inventory** — this is the log this skill maintains. Read
  the file itself (not just its description) before every run: its "How to
  add a row" section is the spec for step 6, and its itemized log is what
  step 1 checks against.

If any of these don't exist yet, run `building-brand-kits` first, or ask the
user for the underlying facts — never invent a stat, channel, or voice rule
to fill a gap.

## When to Use

- Input is one existing press clip about the organization — a URL or pasted
  article text — that needs to become new blog/social/ESG content.
- The clip is already published (it ran in an outlet); this is about
  *reusing* it, not securing new coverage.
- **Not for:**
  - Drafting a new pitch or press release to *get* coverage — no such skill
    exists yet in this ecosystem (see "Related / not yet built" below).
  - Assembling a full ESG/CSR proposal deck — that's
    `writing-esg-sponsorship-proposals`; this skill only hands it a snippet.
  - Packaging a finished blog draft's title/meta/headings, or writing a
    short pull-quote-plus-backlink note without the social/ESG assets —
    that's `packaging-content-for-seo`'s lighter-weight job.
  - Checking a draft's voice/register/AI-flavor after the fact without
    producing new deliverables — that's `auditing-brand-voice`'s job; this
    skill runs its own de-AI-flavor pass (step 5) as part of drafting, but a
    full voice-QA gate is a separate, optional follow-up.
  - Fabricating a quote, stat, date, or outlet not present in the actual
    clip — if the source text/URL isn't provided, ask for it.

## Quick Reference — the four deliverables

| Deliverable | Format | Voice/register | Mandatory elements |
|---|---|---|---|
| Blog recap post | Full post: exact H1/H2/H3 section-title text (literal text for whatever CMS's heading fields render), body, meta description | Institutional by default per the voice card; use a specific bylined contributor's voice only if the clip is specifically about their column/reflection and the voice card documents that fingerprint | Backlink to the original outlet, one real pull-quote from the clip, a written (not keyword-dumped) meta description |
| Social captions (3-5) | One per platform, each rewritten for that platform's register | Whichever register the voice card's matrix maps to this content (often consumer/general-audience unless the clip is B2B-angled) | One caption per confirmed-active platform (see step 3) — never the same text reused across platforms |
| ESG-deck snippet | One paragraph + one stat + one quote block | Corporate/ESG-B2B register per the voice card's register matrix (SDG framing, credibility-led, where relevant) | Reusable as-is inside a deck; hand off to `writing-esg-sponsorship-proposals` for full-proposal assembly — this skill stops at the snippet |
| Inventory log row | One row in the media-coverage inventory | — | Date, outlet, title/angle, stat/quote cited, `Repurposed?` = Y, repurposed-assets list |

## Workflow

### 1. Get the source and check the inventory first

Read the actual clip. If you have a web-fetch capability, fetch the URL; if
fetch is unavailable, or the page can't be retrieved (paywall, login wall,
JS-only render), ask the user to paste the article text — never work from the
headline, the URL slug, or a guess at what the article says. Do not proceed
from a headline or summary alone — pull-quotes and stats in later steps must
trace to real sentences in the clip. Knowing standard **press-release anatomy**
(headline / dateline / lede / inverted-pyramid body / quotes / boilerplate /
contact — see `references/pr-repurposing.md`) helps you locate the real quote,
stat, and angle.

Before drafting, skim the media-coverage inventory's itemized log and its
"Known outlets" list:
- Check how many press clips are already logged in the inventory, so you
  know whether this is an early run or a mature archive.
- If this clip already has a row, don't duplicate it — update the existing
  row's `Repurposed?`/assets columns instead.
- Note what angles/outlets already have full rows — over time this is how
  the inventory surfaces "coverage gaps" (angles or outlets not yet
  repurposed or pitched).

### 2. Draft the SEO blog recap

- Identify voice per the voice card (institutional by default for a press
  recap).
- Write exact section-title text for H1 (usually the recap's title), H2s per
  major section, H3s for sub-points — this is literal text for the target
  CMS's section-title fields, not a suggestion.
- Include one **real** pull-quote lifted from the clip (with attribution to
  the outlet/author).
- Include a **backlink** to the original article — this is the entire SEO
  point of the recap; a recap with no backlink is incomplete.
- Write a natural-sentence meta description (roughly 120-158 characters, per
  `packaging-content-for-seo`'s spec if the project has that skill
  installed), not a keyword string.
- Close with the org's canonical **boilerplate** — the standing "about [org]"
  paragraph, reused verbatim across coverage for a consistent brand
  description (see `references/pr-repurposing.md`); source it from the fact
  sheet rather than rewriting it per recap.

### 3. Draft 3-5 platform-native social captions

Each platform gets its own register — never copy-paste the blog recap or one
caption across platforms:
- Confirm the organization's actually-active platforms from its fact sheet
  before drafting captions — never assume a platform is unavailable (or
  available) without checking. Draft one caption per confirmed platform,
  not a generic template.
- Check the fact sheet's owned-channels list for platform-specific quirks —
  e.g. some messaging-app channels (LINE OA, WhatsApp Business, etc.) strip
  rich link previews or are used for direct 1:1 contact rather than
  broadcast; don't assume every channel behaves like a social feed. Phrase
  copy for those channels as a short, personal-toned message suitable for a
  1:1 reply or light share, not a feed-style announcement.
- For feed-style platforms without inline links (e.g. Instagram), phrase the
  CTA as "link in bio" rather than pasting a raw URL.
- For platforms that support longer, community-toned copy with a direct
  link (e.g. Facebook), let the caption run longer and include the link
  directly.
- If a 4th/5th caption is warranted (e.g., a Stories-format variant), keep
  each one distinct in length/register, not a trimmed duplicate.

### 4. Draft the ESG/CSR-pitch snippet

One paragraph + one stat (from the fact sheet's canonical stat block or the
clip itself) + one quote block, written in corporate/ESG-B2B register
(credibility-led, SDG framing where relevant, per the voice card's register
matrix). This is a standalone, drop-in snippet — not a full proposal. If the
user wants it assembled into a complete, per-account-tailored deck, hand off
to `writing-esg-sponsorship-proposals` (it needs a target company
name/industry to tailor against) — this skill stops at producing the
reusable snippet.

### 5. Run the de-AI-flavor filter

Pass every newly written piece of text (recap body/headings/meta, all
captions, the ESG snippet) through the de-AI-flavor filter's checklist:
banned vocabulary, banned sentence structures, banned transitions,
sentence-length variance, at least one concrete detail. Flag issues rather
than silently rewriting, per that filter's own instruction. If the project
also runs `auditing-brand-voice` as a separate gate before publishing, this
step is not a substitute for that full QA pass — it's the minimum bar for
work leaving this skill.

### 6. Log the row — mandatory, not optional

Append one row to the media-coverage inventory's itemized log following its
own "How to add a row" instructions: exact publish date, outlet, actual
headline/angle, the stat or quote cited, `Repurposed?` = Y, and the list of
repurposed assets produced (e.g., "blog recap / 2 social captions / ESG
snippet"). Never backfill a date/headline you can't verify — leave it blank
rather than guess. This step is what compounds the archive into a real asset
over repeated runs — treat a run that skips it as incomplete.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Producing social captions that are the blog recap copy-pasted across platforms | Each platform needs its own register/format — see step 3; a caption that reads identically on two platforms has failed the task |
| Writing a messaging-app channel's copy in the same broadcast register as a social feed | Check the fact sheet's owned-channels list first — some channels are for direct 1:1 contact, not broadcast; phrase copy as a short personal-toned message, not a mass announcement |
| Assuming a platform is (or isn't) active without checking the fact sheet | Confirm actually-active platforms from the fact sheet before drafting captions — never draft for a platform the org doesn't use, or skip one it does |
| Skipping the media-coverage inventory append (step 6) | This is what compounds the asset over time — treat it as a required last step of every run, not optional record-keeping |
| Fabricating a quote or stat not actually in the source clip | Pull-quotes and cited stats must come from the real article text/URL provided as input — if unclear, re-read the clip or ask, never invent |
| Forgetting the backlink to the original outlet in the blog recap | This is the whole SEO point of the repurposing — no backlink means the recap isn't doing its job |
| Adding a duplicate inventory row for a clip already logged | Check the itemized log first (step 1); update the existing row's `Repurposed?`/assets instead of adding a second row |
| Using B2B/ESG vocabulary in the consumer-facing blog recap or social captions, or vice versa in the ESG snippet | Check the voice card's register matrix before drafting each deliverable — registers are intentionally different |
| Defaulting to institutional voice when a bylined contributor's fingerprint actually applies (or vice versa) | If the voice card documents specific bylined contributors, match the recap/caption voice to whichever one is relevant to the clip's topic; otherwise use the institutional voice |
| Treating this skill as a pitch/press-release generator | It only repurposes *already-published* clips; drafting outbound pitches is a deferred, unbuilt capability (see below) |

## Related / not yet built

- **Pitch & press-release drafter** — would draft outbound pitches/releases
  to *get* new coverage. Needs external timing/relationship judgment this
  skill deliberately avoids. Not built; noted here so it isn't forgotten.
- **Pre-publish risk screener** — would screen drafts for legal/reputational
  risk before external distribution. Also deferred, phase-2.
- **`building-brand-kits`** — produces the fact sheet, voice card, and
  media-coverage inventory this skill reads and writes to. Run it first if
  the project doesn't have that reference material yet.
- **`packaging-content-for-seo`** — the lighter-weight sibling for packaging
  a finished draft's title/meta/headings or a pull-quote-plus-backlink note,
  without the social/ESG assets this skill also produces.
- **`writing-esg-sponsorship-proposals`** — the skill that assembles this
  skill's ESG snippet into a full, per-account-tailored proposal deck
  (buyer-role map, SDG angle, case-study match, a mostly-drafted outline,
  objection responses). Use it when the user names a target company; this
  skill's snippet is one input to that process, not a replacement for it.
- **`auditing-brand-voice`** — a fuller voice/register/AI-flavor QA gate for
  copy before it ships. This skill's own step 5 covers the AI-flavor
  minimum; run `auditing-brand-voice` separately for a complete pre-publish
  check.
