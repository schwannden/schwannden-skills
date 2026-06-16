# Mobile-Friendliness Checklist

Each item: **check → pass criteria (concrete) → how to verify**. `[static]` =
caught by `scripts/static-audit.sh`; everything else needs Lighthouse mobile or
DevTools device mode.

**Tooling note:** Google retired the standalone Mobile-Friendly Test, its API,
and the Search Console Mobile Usability report on 2023-12-01. Use **Lighthouse**
(DevTools → Lighthouse, **Mobile** form factor) and **PageSpeed Insights**
(pagespeed.web.dev, Mobile tab) instead.

## 1. Viewport & responsive layout

- **Viewport meta** `[static]` — `<meta name="viewport" content="width=device-width, initial-scale=1">`. **No** `user-scalable=no` or `maximum-scale=1` (blocks zoom = a11y fail). Verify: Lighthouse "Has a `<meta name=viewport>`".
- **No horizontal scroll** — content width ≤ viewport at 320px (iPhone SE). Verify: DevTools Device Mode at 320px → no horizontal scrollbar.
- **Responsive / fluid** — adapts via media/container queries; relative units (%, rem, fr, vw), not fixed-px containers. Verify: resize across breakpoints, confirm reflow (not just shrink).
- **No tap-to-zoom required** — readable/usable at 100% scale on a phone preset.

## 2. Touch ergonomics

- **Tap target size** — **24×24px** WCAG 2.5.8 AA minimum; **44–48px** recommended (Apple 44 / Material 48); Lighthouse uses 48px target + 8px gap. Inline text links exempt. Verify: Lighthouse "Tap targets are sized appropriately".
- **Spacing** — adjacent targets don't overlap a 24px circle of a neighbor; ~8px min gap.
- **No hover-only interactions** — every menu/tooltip reachable by tap (touch has no hover). WCAG 1.4.13. Verify: Device Mode touch emulation, reach every control by tap.
- **Gesture alternatives** — swipe/pinch/drag has a single-pointer alternative (buttons). WCAG 2.5.1.

## 3. Readable text

- **Legible font size** — body **≥16px** (browser default; below this PSI flags small text). Verify: Lighthouse "Document uses legible font sizes".
- **Line length** — ~50–75 chars/line (`max-width: ~65ch`).
- **Line height** — 1.4–1.6; paragraph spacing ≥2× font size (WCAG 1.4.12).
- **Contrast on small screens** — 4.5:1 normal, 3:1 large/UI (see accessibility ref).

## 4. Mobile performance

- **Core Web Vitals (mobile)** — LCP <2.5s, INP <200ms, CLS <0.1 at p75. Mobile is the hard case. Verify: PSI Mobile tab → CrUX "Core Web Vitals Assessment: Passed".
- **No layout shift** — CLS <0.1; reserve space; don't inject content above existing. Verify: Lighthouse "Avoid large layout shifts".
- **Image width/height set** — explicit `width`+`height` (or CSS `aspect-ratio`) reserves space → prevents CLS. Verify: Lighthouse "Image elements have explicit width and height".
- **Responsive images** — `srcset`+`sizes` and/or `<picture>`; next-gen formats (AVIF/WebP). Verify: Lighthouse "Properly size images" / "Serve images in next-gen formats".
- **Lazy-load below the fold** — `loading="lazy"` on below-fold images/iframes; **never** lazy-load the LCP/hero image (eager it, `fetchpriority="high"`). Verify: Lighthouse "Defer offscreen images".
- **Survives throttling** — usable on Lighthouse Mobile preset (4× CPU + Slow 4G).

## 5. Mobile-specific gotchas

- **No intrusive interstitials** — no popup/overlay covering content on arrival. Allowed: cookie/legal/age-gate, login dialogs for non-indexable content, small dismissible banners. Violations get a Google mobile ranking demotion. Verify: load fresh on mobile, observe first paint.
- **Fixed/sticky elements don't cover content** — sticky bars don't obscure form fields or the keyboard area. Verify: Device Mode, scroll + open a field.
- **Mobile keyboard input types** `[partial static]` — `type="email|tel|url|number|search"` or `inputmode="numeric"`; add `autocomplete` tokens (WCAG 1.3.5). Verify: inspect form markup.
- **Safe-area / notch** — for full-bleed/fixed UI: `viewport-fit=cover` + pad with `env(safe-area-inset-*)`. Verify: inspect viewport meta + CSS; test on a notched device.
- **Orientation** — works portrait + landscape; don't lock unless essential (WCAG 1.3.4). Verify: Device Mode rotate.

## One-pass recipe

1. **PSI Mobile tab** → CrUX CWV pass/fail at p75 + Lighthouse scores.
2. **Lighthouse Mobile** → viewport tag, content sized to viewport, legible fonts, tap targets, contrast, image dimensions, responsive/next-gen images, offscreen images, layout-shift diagnostics.
3. **DevTools Device Mode** at 320px + a notched preset → no horizontal scroll, no hover-only menus, fixed bars clear, rotate, tap fields for keyboards, watch first paint for interstitials.
