# PWA-Readiness Checklist

**Contents:** [1. Core installability](#1-core-installability) ·
[2. Service worker & offline](#2-service-worker--offline) ·
[3. Cross-platform install](#3-cross-platform-install) ·
[4. Modern capabilities](#4-modern--really-nice-capabilities-20232026) ·
[5. Verify](#5-verify--requirement--tool--pass-signal)

Each item: **check → pass (concrete values) → how to verify → platform notes.**
`[static]` = caught by `scripts/static-audit.sh`.

**Biggest correction vs 2018-era guidance:** Chrome/Edge no longer require a
service worker with a fetch handler to be **installable** (relaxed in Chrome 108
Android / 112 desktop). A SW is still required for **offline** and to fire the
**automatic `beforeinstallprompt`**. Two distinct bars — keep them separate:

- **Installable via menu** = HTTPS + valid manifest (icons 192+512, `display`≠`browser`).
- **Auto-prompted + offline** = the above **plus** a registered service worker with a fetch handler.

**Tooling:** Lighthouse **removed its PWA category in v12** (2024-04). There is no
"Lighthouse PWA score" anymore. Audit with **DevTools → Application** (canonical)
and **PWABuilder.com**.

## 1. Core installability

- **HTTPS** `[static]` — page + manifest over HTTPS (or localhost in dev), no mixed content. Hard requirement everywhere.
- **Manifest linked** `[static]` — `<link rel="manifest" href="…">`; served as `application/manifest+json`; parses clean. Verify: DevTools → Application → Manifest, no parse errors.
- **Required manifest fields (Chromium install):**
  - `name` **or** `short_name`
  - `icons` incl. a **192×192** and **512×512** PNG
  - `start_url` (within `scope`, same-origin)
  - `display` ∈ {`standalone`,`fullscreen`,`minimal-ui`,`window-controls-overlay`} — **not** `browser`
  - `prefer_related_applications` absent or `false`
  - Verify: DevTools Manifest pane shows **no Installability warnings** + install (⊕) icon appears.
- **Service worker** `[partial static]` — registered, `activated and is running`, has a fetch handler. Required for offline + auto-prompt, **not** for menu install. Verify: DevTools → Application → Service Workers.

### Manifest field reference (pass values)

| Field | Pass | Notes |
|-------|------|-------|
| `name` / `short_name` | full + ≤12-char short | short = home-screen label |
| `start_url` | within scope, same-origin | e.g. `/?source=pwa` |
| `display` | `standalone` | `browser` disqualifies install |
| `icons` | 192 + 512 PNG, one `purpose:"maskable"` 512 | maskable safe zone = central 80% |
| `theme_color` | e.g. `#0b5fff` | window/address-bar tint |
| `background_color` | e.g. `#ffffff` | splash bg (Android; iOS ignores) |
| `id` | stable, e.g. `/?source=pwa` | set it so `start_url` can change without a duplicate install |
| `scope` | `/` | URLs outside open in browser chrome |
| `screenshots` | `wide` (desktop) + `narrow` (Android) PNG/JPEG | triggers the **richer** install dialog |

## 2. Service worker & offline

- **Registration & scope** — `activated`; scope capped by SW script's directory (serve from root for whole-origin). Don't version the SW URL (`sw-v2.js`) or long-cache the SW file.
- **Lifecycle / waiting worker** — `install` precaches in `event.waitUntil`; `activate` cleans old caches; on a new waiting worker, **prompt the user to reload** (or deliberately `skipWaiting()`) — not silently waiting.
- **Caching strategies** — cache-first for hashed/immutable assets; network-first for HTML + fresh API data; stale-while-revalidate for freshness-tolerant; never cache-first unversioned files.
- **Offline fallback** — precached `offline.html` returned on failed navigation. Verify: Application → Service Workers → tick **Offline**, navigate to an uncached route.
- **Tooling** — Workbox 7.x or a framework plugin (`vite-plugin-pwa` ✅). Original `next-pwa` archived 2023 → use **Serwist** (`@serwist/next`) for Next.js.

## 3. Cross-platform install

**Android / Chrome**
- `beforeinstallprompt` — `e.preventDefault()`, stash event, custom button calls `prompt()`, read `userChoice.outcome`. Chromium-only, non-standard.
- WebAPK — only on devices with Google Mobile Services; verify `chrome://webapks`.

**iOS / Safari (most error-prone)**
- **No install prompt** — instruct Share → Add to Home Screen. `'onbeforeinstallprompt' in window` is `false` (true through iOS 18).
- **Honored manifest fields:** `name`, `short_name`, `start_url`, `scope`, `display` (only `standalone`/`browser`), `theme_color` (≥15), icons (≥**15.4**). **Ignored:** `background_color`, `shortcuts`, `minimal-ui`/`fullscreen`, dark/tinted icons.
- **Apple meta** `[static]` — `apple-touch-icon` (180×180, square, opaque) **overrides** manifest icons when present; `apple-mobile-web-app-capable="yes"` still needed to enable `apple-touch-startup-image` splash screens; `apple-mobile-web-app-status-bar-style` `black-translucent` for true fullscreen.
- **Splash screens** — still manual: one `apple-touch-startup-image` per resolution/orientation with exact `media` queries.
- **Web Push on iOS** — requires iOS ≥16.4 **+ installed to Home Screen** + permission from a user gesture + Push API/SW. No push in Safari tabs.
- **Limitations:** no Background Sync/Fetch; storage evictable after ~7 days idle.

**Desktop (Chrome/Edge)**
- Install → standalone window + launcher/Dock entry.
- `window-controls-overlay` — `display_override:["window-controls-overlay"]`; position with `env(titlebar-area-*)`; drag via `-webkit-app-region`. Stable since Chromium 104, **desktop-only**. Verify `navigator.windowControlsOverlay.visible`.
- `shortcuts` — taskbar/Dock menu (desktop + Android + Safari macOS 17.4+; **not iOS**).

## 4. Modern / "really nice" capabilities (2023–2026)

Verdict: ✅ usable · ⚠️ partial · ❌ unsupported. **Feature-detect everything**
(`'X' in navigator` / `@supports`) — none except Push is load-bearing-safe.

| Capability | Desktop Chrome/Edge | Chrome Android | Safari/iOS | Verdict |
|------------|:---:|:---:|:---:|---|
| **Web Push / Push API** | ✅ | ✅ | ✅ 16.4+ (installed only) | **The one Baseline cross-browser capability** |
| **Badging API** | ✅ | ❌ | ✅ 16.4+ / macOS 17+ | Widest OS reach incl. iOS |
| `display_override` | ✅ | ✅ | ⚠️ parsed | Safe wrapper |
| `window-controls-overlay` | ✅ | ❌ | ❌ | Chromium desktop enhancement |
| `shortcuts` | ✅ | ✅ | macOS ✅ / iOS ❌ | Enhancement |
| `share_target` (receive) | ✅ | ✅ | ❌ | Chromium/Android-first |
| `file_handlers` + launchQueue | ✅ | ❌ | ❌ | Chromium desktop only |
| `protocol_handlers` | ✅ | ❌ | ❌ | Chromium desktop only |
| `launch_handler` (focus-existing) | ✅ | ⚠️ | ❌ | Chromium enhancement |
| Periodic Background Sync | ✅ | ✅ | ❌ | Niche; needs install+engagement |
| Background Fetch | ✅ | ✅ | ❌ | Chromium enhancement |
| `screenshots` (rich install UI) | ✅ (wide) | ✅ (narrow) | ❌ | Safe enhancement |
| View Transitions (same-doc/SPA) | ✅ 111+ | ✅ | ✅ 18.0+ | **Baseline Oct 2025** — app-like nav everywhere |
| View Transitions (cross-doc/MPA) | ✅ 126+ | ✅ | ✅ 18.2+ | Progressive enhancement (no Firefox) |
| File System Access (pickers) | ✅ 86+ | ❌ | ❌ | Chromium **desktop only** |
| OPFS (sandboxed storage) | ✅ | ✅ | ✅ 15.2+ | Usable (not user-chosen disk files) |
| Web Share API | ✅ | ✅ | ✅ | Progressive enhancement; best on mobile |

**Two anti-patterns to flag:** (1) File System Access *pickers* (Chromium-only) ≠
OPFS (broad); (2) same-document ≠ cross-document View Transitions (very different
support). For richer install dialogs, ship `description` + `screenshots` with
`form_factor` `wide` (≤8, desktop) and `narrow` (≤5, Android).

## 5. Verify — requirement → tool → pass signal

| Requirement | Tool | Pass signal |
|-------------|------|-------------|
| Installability | DevTools → Application → Manifest | no Installability error + ⊕ in address bar |
| Manifest validity | DevTools Manifest pane / PWABuilder | all required fields, no red errors |
| SW active | DevTools → Service Workers | "activated and is running" |
| Offline works | Service Workers → Offline + Cache Storage | core flow works offline |
| Icons / maskable | DevTools Manifest → Icons | 192+512 load; logo inside safe circle |
| HTTPS / security | DevTools / PWABuilder Security card | HTTPS + valid SSL + no mixed content |
| Store readiness | PWABuilder Report Card | all red items cleared → "Package for Stores" |

**Uncertain / version-sensitive:** SW-for-install relaxation is version-dependent;
`id`/`maskable` not fully Baseline (limited Safari); iOS dark/tinted icons don't
work for PWAs through iOS 18; re-verify iOS field support each minor release.
