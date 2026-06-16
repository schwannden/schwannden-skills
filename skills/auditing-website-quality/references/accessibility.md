# Accessibility Checklist (WCAG 2.1 / 2.2)

Each item: **check → pass criteria → how to verify** (auto vs manual). `[static]`
= caught by `scripts/static-audit.sh`.

**Reality check:** automated tools (axe, Lighthouse, WAVE) catch only **~30–40%**
of WCAG issues — mostly contrast, missing alt/labels, ARIA misuse, structure. The
other ~60% (alt-text *quality*, focus order, keyboard operability, ARIA that
conveys real meaning) needs **manual + assistive-tech** testing. A clean axe scan
is necessary, never sufficient. Never report "accessible" on automation alone.

**Target:** WCAG **2.2 Level AA** (meets 2.1 AA too). A = bare minimum, AAA =
aspirational. New in 2.2 AA: 2.4.11 Focus Not Obscured, 2.5.7 Dragging Movements,
2.5.8 Target Size (min), 3.3.8 Accessible Authentication; new A: 3.2.6 Consistent
Help, 3.3.7 Redundant Entry. (4.1.1 Parsing was removed.)

## 1. Semantic HTML & structure

- **Document language** `[static]` — `<html lang="…">` correct; language changes marked (3.1.1 A, 3.1.2 AA). Auto-detected.
- **Page title** `[static]` — unique, descriptive `<title>` (2.4.2 A). Auto flags empty; manual judges quality.
- **Heading hierarchy** `[partial static]` — one logical outline, no skipped levels (h2→h4 fails), one `<h1>` by convention (1.3.1, 2.4.6). Verify: WAVE heading map / HeadingsMap extension.
- **Landmarks** — `<header>/<nav>/<main>/<footer>`; one `<main>`; all content inside a landmark; duplicate landmarks get unique labels. Verify: axe + screen-reader rotor.
- **Lists / tables** — real `<ul>/<ol>/<dl>`; data tables use `<th scope>` + `<caption>`, no layout tables (1.3.1).
- **Buttons vs links** — `<a href>` navigates, `<button>` acts; never `<div onclick>`. Verify: tab to each, confirm operable + correct role announced.

## 2. Images & media

- **Meaningful alt** `[partial static]` — informative images convey purpose; functional images describe the action (1.1.1 A). Auto flags *missing* alt; **manual** judges quality.
- **Decorative** — `alt=""` (empty) or CSS background; no `alt="image"`/filename.
- **Complex images** — chart/diagram has short alt + long description (adjacent text / `aria-describedby`).
- **Text in images** — avoid except logos; use real text (1.4.5 AA). Verify: zoom 200–400%, no pixelation.
- **Video captions / transcript** — captions for prerecorded (1.2.2 A) and live (1.2.4 AA); transcript for audio-only (1.2.1); audio description (1.2.5 AA). Verify accuracy manually.

## 3. Colour & contrast

- **Text contrast (normal)** — ≥ **4.5:1** for text <24px (and <18.66px bold) (1.4.3 AA; AAA 7:1). Verify: axe/Lighthouse + WebAIM Contrast Checker (esp. text over images/gradients — automation misses these).
- **Text contrast (large)** — ≥ **3:1** for ≥24px or ≥18.66px bold.
- **Non-text contrast** — ≥ **3:1** for UI borders/states, icons, meaningful graphics (1.4.11 AA).
- **Not colour alone** — errors/links/required/status not conveyed by colour only (1.4.1 A). Verify: view in grayscale, confirm meaning survives.
- **Focus indicator contrast** — ≥ 3:1 vs adjacent.
- **Resize / reflow** — text to 200% with no loss (1.4.4 AA); reflow at 320px / 400% zoom, no two-axis scroll (1.4.10 AA).

## 4. Keyboard & focus (mostly manual — automation can't verify)

- **Full keyboard operability** — everything works via keyboard alone, incl. menus, modals, custom widgets; drag has a non-drag alternative (2.1.1 A, 2.5.7 AA). Verify: unplug mouse, Tab/Enter/Space/Arrows/Esc through every flow.
- **No keyboard trap** — focus can always leave any component (2.1.2 A). Test embedded widgets/iframes.
- **Visible focus** — clear indicator on every focusable element (2.4.7 AA). Never `outline:none` without a replacement.
- **Logical tab order** — follows reading/visual order (2.4.3 A); avoid positive `tabindex`.
- **Skip link** — first focusable element, visible on focus, jumps to `<main>` (2.4.1 A). Verify: load, press Tab once.
- **Focus not obscured** — focused element not hidden by sticky bars (2.4.11 AA).
- **Modal focus management** — opening moves focus in + traps within; closing returns to trigger. Follow ARIA APG patterns.

## 5. Forms

- **Labels** — every input has an associated `<label for>` (or wrapping label / `aria-label`). Placeholder ≠ label (1.3.1, 3.3.2, 4.1.2). Auto flags unlabeled reliably.
- **Required & instructions** — in text, not colour/asterisk alone; `required`/`aria-required` set.
- **Error identification** — errors in **text**, describe the problem, tied to field (`aria-describedby`, `aria-invalid`) (3.3.1 A). Verify: submit invalid, confirm screen reader announces which field + why.
- **Error suggestion** — suggest a fix when known (3.3.3 AA).
- **Group labeling** — radio/checkbox groups in `<fieldset>` + `<legend>`.
- **Accessible auth** — no transcription/cognitive test without alternative; allow paste/password managers (3.3.8 AA).

## 6. ARIA

- **First rule of ARIA** — don't use ARIA if native HTML provides the semantics. `<button>` over `<div role="button">`. ARIA changes semantics but adds **no behavior** — you wire the keyboard yourself.
- **No redundant/conflicting ARIA** — no `role` duplicating native, no invalid role/attr combos. axe is strong here.
- **Accessible name** — every control has a non-empty name (content / `aria-label` / `aria-labelledby`); icon-only buttons need `aria-label` (4.1.2 A).
- **States/properties** — `aria-expanded/selected/checked/current/pressed/controls` present and updated. Verify: operate widget + screen reader.
- **Hidden content** — `aria-hidden="true"` never on focusable elements.
- **APG patterns** — custom tabs/combobox/menu/dialog/accordion match WAI-ARIA Authoring Practices.

## 7. Dynamic content & motion

- **Live regions** — async updates (toasts, validation, cart) use `aria-live="polite"`/`role="status"` (urgent: `assertive`/`role="alert"`); region in DOM before injection. Verify: trigger + screen reader.
- **Reduced motion** — honor `@media (prefers-reduced-motion: reduce)`. Verify: enable OS Reduce Motion.
- **Pause/stop/hide** — auto-moving content >5s can be paused (2.2.2 A); no autoplay audio >3s (1.4.2 A).
- **No flashing** — nothing flashes >3×/second (2.3.1 A).
- **Timeouts** — adjustable/extendable; warn before session timeout (2.2.1 A).

## Verdict workflow

1. **Automated** (axe DevTools / Lighthouse a11y / WAVE / Pa11y) — gate: 0 critical/serious axe violations, Lighthouse a11y ≥95. ~⅓ of issues.
2. **Keyboard-only** — full walkthrough, no traps, visible focus, working skip link.
3. **One screen reader** (VoiceOver/NVDA) — names, roles, states, errors, live updates on key flows.
4. **Manual** — alt quality, colour-alone (grayscale), contrast over images, captions, reduced-motion.
5. **Zoom/reflow** — 200% and 320px width.

A page passing only automation must **not** be reported as accessible.
