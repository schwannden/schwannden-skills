# De-AI-Flavor Filter

A checklist for stripping "AI-flavor" out of English marketing/content copy.
Run this pass on any drafted text before finalizing it — whether the draft
was written by a human, an LLM, or a mix of both.

## Core principle

AI defaults to statistical-average, "safe" phrasing — the opposite of what
makes content resonate. Treat first-pass AI output as roughly a 60-point
draft, not a finished product. Authenticity comes from personal judgment,
concrete detail, and lived/practitioner experience — don't flatten it out in
the name of "polish."

## Banned vocabulary

Words that read as generic AI filler rather than a specific claim:

delve, boasts, seamlessly, robust, landscape, tapestry, underscore(s),
elevate, unlock, harness, leverage (as a verb for "use"), navigate
(metaphorically), game-changer, cutting-edge, testament to, in today's
fast-paced world, in the ever-evolving world of, at the end of the day

## Banned sentence structures

- "Not only... but also..."
- "It's important to note that..."
- "Whether you're X or Y, [generic claim]..."
- Rhetorical-question openers used as a crutch ("Ever wondered how...?")

## Banned transition phrases (crutch words)

moreover, furthermore, additionally, in conclusion, that said, all in all

## Style rules

- Localize to the actual register and market you're writing for — don't let
  generic "international business English" phrasing replace the vocabulary
  your audience actually uses.
- Avoid excessive bold/emoji/markdown formatting in prose — flat, natural
  text reads more human than a wall of bolded phrases and bullet emoji.

## Positive requirements

- **Substantive, concrete content** — a specific number, a named example, a
  session/customer/product-level detail — not a generic claim that could
  apply to any organization in the category.
- **Human voice** — varied sentence rhythm and length, not uniform AI
  cadence (AI drafts tend toward same-length sentences strung together with
  the banned transitions above).

## Organization-specific additions (extend here)

The lists above are generic and organization-agnostic. To extend them, copy
this file into your own project and append your own rules below — the phrasings
*your* audience or industry over-uses that the generic list misses. Leave this
section empty in the shipped/installed copy; it exists so a downstream project
knows exactly where org-specific rules go.

- **Banned phrases:** [e.g. a competitor's slogan you keep echoing by accident,
  an industry cliché your niche overuses — add your own]
- **Banned structures:** [a sentence shape that recurs in your own drafts — add
  your own]
- **Locale/market phrasing:** [words the generic "international business
  English" list won't catch for your specific market — add your own]

## How to apply

1. Draft the content normally (voice/register per `voice-card-template.md`,
   facts per `fact-sheet-template.md`).
2. Scan for every banned word/structure/transition above — if present,
   rewrite that sentence rather than swap in a synonym. Synonym-swapping
   often keeps the underlying flat AI rhythm even when the trigger word is
   gone.
3. Check sentence-length variance — if every sentence is a similar length,
   vary it.
4. Confirm at least one concrete, specific detail (a number from the fact
   sheet, a named case, a product/session-level observation) rather than a
   general claim.

## Output when used as a QA pass

Report flagged instances with the exact phrase and a suggested rewrite —
don't silently rewrite. Flagging preserves the author's voice and judgment;
silent rewrites tend to reintroduce the same flat AI cadence this filter
exists to catch.
