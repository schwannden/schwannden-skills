---
name: auditing-brand-voice
description: Produces a four-section, citation-backed flagged report — brand-voice fit, register fit, author-voice consistency, and a de-AI-flavor pass — that checks a piece of marketing or content copy against a documented brand-kit standard instead of judging it on vibe, flagging each issue with a one-line fix rather than silently rewriting. Use when reviewing copy before it ships — a blog post, proposal/one-pager, social caption, service-page copy, or any other text — especially when a target register and/or a declared author (a specific named/bylined contributor, or "institutional") need to be checked against the project's brand-kit reference material.
---

# Auditing Brand Voice

## Overview

**Core principle: this is an editorial GATE, not a content generator.** It absorbs the "check it against a standard" step of review. It always flags issues with a one-line suggested fix and never silently rewrites the draft, preserving the human's final judgment call.

## Required Background

Look for this project's brand-kit reference material — a fact sheet, voice card, and/or media-coverage inventory, commonly created via the `building-brand-kits` skill (e.g. under `docs/brand/`). If none exists, ask the user for the relevant facts or flag the gap explicitly — never invent brand-voice facts.

This skill applies that material as a checklist; it does not redefine it. At minimum you need:

- A **voice card** — brand personality, "what the brand is NOT," a register matrix (the different formality/vocabulary modes the brand writes in, e.g. consumer-facing vs. B2B/partner-facing vs. internal/volunteer-facing — whatever registers this project's voice-card defines), and, if the project has named/bylined contributors, a table of their voice fingerprints.
- A **de-AI-flavor filter** — banned vocabulary/structures/transitions, any locale-specific phrasing rules, and requirements for a concrete, human tone.

If the draft also needs fact-checking (stats, case names, taglines, figures), that's a separate concern handled by the project's fact sheet — this skill's job is voice/register/tone, not fact verification.

**Fallback when no brand kit exists.** If the project has no voice card or de-AI-flavor filter and the user can't supply one, don't stall — run a degraded pass against a minimal standard, and say up front that it's a generic check, not a brand-kit-backed one:

- **Register:** ask the user for the one target register (who the audience is), then score the draft on the four generic **NN/g tone dimensions** in `references/tone-dimensions.md` — a citable rubric to use in place of a project register matrix.
- **De-AI-flavor:** fall back to the generic checklist in `building-brand-kits`'s `references/de-ai-flavor-filter.md` (banned vocabulary/structures/transitions).
- **Brand-voice / author-voice:** with no voice card there is nothing documented to check against — state that those two sections are "not assessable without a voice card" rather than inventing a personality or fingerprint.

## When to Use

- Before a piece of copy ships, and it needs a check against documented brand voice/register standards.
- A target register is declared and cross-contamination between registers is a risk (e.g., B2B/technical jargon leaking into consumer copy, or informal/testimonial language leaking into B2B copy).
- An author is declared — either a specific named/bylined contributor or "institutional" — and the copy needs to be checked against that voice.
- A draft "reads fine" on a casual pass but hasn't been checked against the actual documented voice-card examples or the de-AI-flavor checklist.
- **Not for:** drafting new content from scratch (use the project's content-generation skill, or a sibling skill such as `writing-esg-sponsorship-proposals` or `writing-short-form-video-scripts`), fact-checking stats/case studies (see the project's fact sheet), or bulk-rewriting a draft without human sign-off (auto-revise is an opt-in mode, not the default — see below).

## Quick Reference — the four fixed sections

| # | Section | Checks against | Source in voice-card / de-ai-flavor filter |
|---|---|---|---|
| 1 | **Brand-voice fit** | Does the draft match the brand's core personality and framing? Any tonal clash with the brand's mission language (e.g., if the mission language is "we serve people, not case files," does the draft instead read clinical or process-first)? Any pattern the voice card explicitly bans (e.g., a framing device it says never to use)? | "Brand personality" + "What the brand is NOT" sections |
| 2 | **Register fit** | Vocabulary/formality correct for the declared register? Any cross-contamination between registers? | Register matrix + its "cross-contamination to catch" note |
| 3 | **Author-voice consistency** (only if an author is declared) | If the voice-card documents specific named/bylined contributors, does the draft match that contributor's documented fingerprint — or does it read like a different contributor's voice, or generically institutional when a personal byline was declared? If the copy is institutional (no byline), does it match the documented institutional-voice description instead? | Author/contributor voice-fingerprint table, or institutional-voice description |
| 4 | **De-AI-flavor pass** (always run) | Banned vocabulary/structures/transitions, locale-appropriate phrasing, sentence-length variance, concrete/specific detail present | Full de-ai-flavor filter checklist |

## How to run the QA pass

1. **Confirm inputs.** You need the draft text, a declared target register, and optionally a declared author. If register isn't declared, ask — don't guess, since register is the axis most checks depend on.
2. **Section 1 — Brand-voice fit.** Read the draft against the voice-card's "brand personality" and "what the brand is NOT" sections. Flag any framing the voice card bans outright (not register-dependent), off-tone framing, or corporate-cold copy where warmth is expected (or vice versa).
3. **Section 2 — Register fit.** Compare vocabulary and formality to the matching register-matrix row. This is the highest-yield check — read the register matrix's "cross-contamination to catch" note specifically and scan for its failure modes in both directions. To keep the judgment defensible rather than a vibe, locate the draft on the four **NN/g tone dimensions** (`references/tone-dimensions.md`) and flag any dimension where it drifts from where the target register should sit.
4. **Section 3 — Author-voice consistency.** Only run if an author is declared. If the voice-card documents specific named/bylined contributors, compare against that contributor's row in the fingerprints table, and note if the draft instead matches a different contributor's fingerprint or reads as generic/institutional when a personal byline was declared. If the copy is institutional (no byline), compare against the documented institutional-voice description instead.
5. **Section 4 — De-AI-flavor pass.** Always run, regardless of what sections 1–3 found. Work through the de-ai-flavor filter's banned vocabulary, banned structures, banned transitions, then confirm locale-appropriate phrasing and sentence-length variance, then confirm at least one concrete/specific detail is present.
6. **Assemble the report** in the fixed four-section order below. Do not merge sections or reorder them — the reviewer scans this by section, not as prose.
7. **Stop.** Do not rewrite the draft unless the user has explicitly asked for auto-revise mode (see below).

## Output format

Always exactly four sections, in this order, even if a section has no findings (state "No issues found" rather than omitting it):

```
## 1. Brand-voice fit
- [flag]: <quoted phrase or description> — <one-line fix> (cites: voice-card, <section/row>)

## 2. Register fit
- [flag]: <quoted phrase> — <one-line fix> (cites: voice-card register matrix, <row>)

## 3. Author-voice consistency  [omit only if no author declared]
- [flag]: <quoted phrase> — <one-line fix> (cites: voice-card fingerprints table or institutional-voice description, <contributor or "institutional">)

## 4. De-AI-flavor pass
- [flag]: <exact banned phrase> — <suggested rewrite> (cites: de-ai-flavor filter, <rule>)
```

Every flag cites the specific voice-card/de-ai-flavor-filter example, row, or rule it's based on — a flag without a citation is a vibe check, not a QA pass, and isn't teachable.

**Auto-revise mode is opt-in only.** If the user explicitly asks the skill to apply the fixes, produce the flagged report first, then a second "revised draft" block applying only the flagged fixes — never skip straight to a rewritten draft.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Rewriting the whole draft instead of producing a flagged-issues report | Defeats the purpose — the reviewer needs to scan flags, not re-read the whole piece. Flag, don't silently rewrite. |
| Skipping the register check because "it reads fine" | Cross-contamination between registers is usually the single most concrete risk and is easy to miss on a casual read. Always run section 2 explicitly against the register-matrix row. |
| Applying generic brand-voice judgment instead of checking against the voice-card's actual examples | Always cite which do/don't example, matrix row, or fingerprint the flag is based on — an uncited flag is a vibe, not a teachable fix. |
| Treating the de-AI-flavor pass as optional or secondary | It's one of the four fixed sections every time, regardless of what the other three sections find. |
| Running author-voice consistency when no author was declared | Only run section 3 when an author is explicitly declared; otherwise omit the section rather than guessing a voice. |
| Jumping to a rewritten draft when the user only asked for a check | Auto-revise is opt-in — always produce the flagged report first, and only apply fixes if explicitly asked. |
| Inventing brand-voice facts when no brand-kit reference material exists | Ask the user for the relevant facts, or flag the gap explicitly, rather than guessing at a voice/register/fingerprint that isn't documented. |

## Related skills

If this project doesn't yet have brand-kit reference material, run `building-brand-kits` first to produce it. For downstream content work that this skill can gate, see sibling skills such as `writing-esg-sponsorship-proposals`, `reporting-marketing-performance`, `repurposing-press-coverage`, `packaging-content-for-seo`, and `writing-short-form-video-scripts`.
