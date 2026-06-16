#!/usr/bin/env bash
# static-audit.sh — fetch a URL once and report the website-quality signals that
# are extractable from raw HTML + HTTP headers (no browser, no JS execution).
#
# Covers the STATIC subset of the four audit dimensions:
#   SEO/indexing, social-share metadata, structured data, PWA manifest/meta,
#   plus a few transport/perf headers and a11y structure smells.
#
# It does NOT (and cannot) measure: Core Web Vitals field data, tap-target size,
# colour contrast, keyboard/screen-reader behaviour, or offline support. Those
# need Lighthouse/PageSpeed Insights, axe, and manual testing — see the skill's
# reference files. This script tells you which of those to run next.
#
# Usage:   ./static-audit.sh https://example.com/
# Requires: curl, grep, sed (all standard).

set -uo pipefail

URL="${1:-}"
if [ -z "$URL" ]; then
  echo "usage: $0 <url>" >&2
  exit 2
fi
case "$URL" in http://*|https://*) ;; *) URL="https://$URL" ;; esac

# Derive the origin (scheme://host) for robots.txt / sitemap / manifest probes.
ORIGIN="$(printf '%s' "$URL" | sed -E 's#^(https?://[^/]+).*#\1#')"

HTML="$(mktemp)"; HDRS="$(mktemp)"
trap 'rm -f "$HTML" "$HDRS"' EXIT

# Single fetch of the page (follow redirects, capture headers + body).
META="$(curl -sL --compressed --max-time 30 -A "website-quality-audit/1.0" \
        -D "$HDRS" -o "$HTML" \
        -w 'HTTP %{http_code} | %{size_download}B | %{time_total}s | %{content_type}' "$URL" 2>/dev/null)"
if [ ! -s "$HTML" ]; then
  echo "FATAL: could not fetch $URL" >&2
  exit 1
fi

pass()  { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
warn()  { printf '  \033[33mWARN\033[0m  %s\n' "$1"; }
fail()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; }
info()  { printf '  ----  %s\n' "$1"; }
head_h(){ printf '\n\033[1m%s\033[0m\n' "$1"; }

# grep -oiE helper that returns first match (HTML is single-line-ish from SSR).
g() { grep -oiE "$1" "$HTML" 2>/dev/null | head -1; }
# Count OCCURRENCES, not matching lines: SSR HTML is often a single line, so
# `grep -c` would always return 1. Pipe through wc -l on `-o` output instead.
gc(){ grep -oiE "$1" "$HTML" 2>/dev/null | wc -l | tr -d ' '; }
hdr(){ grep -iE "^$1:" "$HDRS" 2>/dev/null | tail -1 | sed -E 's/\r//'; }

echo "==================================================================="
echo " Website quality — static audit"
echo " URL:    $URL"
echo " Fetch:  $META"
echo "==================================================================="

# ---------------------------------------------------------------- transport
head_h "Transport / performance (headers)"
REDIR="$(curl -sI --max-time 15 "$(printf '%s' "$ORIGIN" | sed 's#https://#http://#')" -o /dev/null -w '%{http_code}' 2>/dev/null)"
case "$REDIR" in 30*) pass "HTTP -> HTTPS redirect ($REDIR)";; *) warn "no HTTP->HTTPS redirect (got $REDIR)";; esac
[ -n "$(hdr strict-transport-security)" ] && pass "HSTS: $(hdr strict-transport-security)" || warn "no Strict-Transport-Security header"
ENC="$(hdr content-encoding)"; [ -n "$ENC" ] && pass "compression:$ENC" || warn "no content-encoding (check gzip/brotli is served)"
CC="$(hdr cache-control)"; [ -n "$CC" ] && info "cache-control:$CC" || warn "no cache-control header on document"
info "server:$(hdr server)"

# ---------------------------------------------------------------- mobile
head_h "Mobile-friendliness (static signals)"
VP="$(g '<meta[^>]*name="viewport"[^>]*>')"
if [ -n "$VP" ]; then
  echo "$VP" | grep -qiE 'width=device-width' && pass "viewport: $VP" || warn "viewport present but no width=device-width: $VP"
  echo "$VP" | grep -qiE 'user-scalable=no|maximum-scale=1([^0-9]|$)' && fail "viewport disables zoom (a11y fail): remove user-scalable=no / maximum-scale=1"
else
  fail "no <meta name=viewport> — page will not be mobile-friendly"
fi
info "tap targets, font sizes, no-horizontal-scroll, hover-only UI -> need Lighthouse mobile + DevTools device mode"

# ---------------------------------------------------------------- a11y structure
head_h "Accessibility (structure smells only)"
LANG="$(g '<html[^>]*lang="[^"]*"')"; [ -n "$LANG" ] && pass "html $LANG" || fail "no lang attribute on <html>"
H1="$(gc '<h1[ >]')"; case "$H1" in 1) pass "exactly one <h1>";; 0) warn "no <h1> found";; *) warn "$H1 <h1> elements (expect 1)";; esac
IMG="$(gc '<img[ >]')"; IMGALT="$(gc '<img[^>]*alt=')"
if [ "$IMG" -gt 0 ]; then
  [ "$IMG" = "$IMGALT" ] && pass "all $IMG <img> have alt attributes" || warn "$IMGALT/$IMG <img> have alt (check the rest; decorative => alt=\"\")"
else
  info "0 <img> tags (CSS/SVG/next-image?) — verify meaningful images have alt manually"
fi
info "contrast, keyboard nav, focus, ARIA, screen-reader -> need axe DevTools + manual (automation catches ~30-40%)"

# ---------------------------------------------------------------- SEO
head_h "SEO / indexing"
T="$(g '<title>[^<]*</title>')"; TL=$(printf '%s' "$T" | sed -E 's/<[^>]*>//g' | tr -d '\n' | wc -c | tr -d ' ')
if [ -n "$T" ]; then
  pass "title (${TL} chars): $(printf '%s' "$T" | sed -E 's/<[^>]*>//g')"
  [ "$TL" -gt 62 ] && warn "title >60 chars may truncate in SERP"
else
  fail "no <title>"
fi
D="$(g '<meta[^>]*name="description"[^>]*>')"; [ -n "$D" ] && pass "meta description present" || warn "no meta description"
CAN="$(g '<link[^>]*rel="canonical"[^>]*>')"; [ -n "$CAN" ] && pass "canonical: $CAN" || warn "no rel=canonical link"
RB="$(g '<meta[^>]*name="robots"[^>]*>')"; if [ -n "$RB" ]; then echo "$RB" | grep -qi noindex && fail "robots meta has noindex: $RB" || info "robots meta: $RB"; fi
RTXT="$(curl -sL --max-time 15 "$ORIGIN/robots.txt" -o /dev/null -w '%{http_code}' 2>/dev/null)"
[ "$RTXT" = "200" ] && pass "robots.txt (200)" || warn "robots.txt -> HTTP $RTXT"
SM="$(curl -sL --max-time 15 "$ORIGIN/sitemap.xml" -o /dev/null -w '%{http_code}' 2>/dev/null)"
[ "$SM" = "200" ] && pass "sitemap.xml (200)" || warn "sitemap.xml -> HTTP $SM (or referenced under another path in robots.txt)"
info "Core Web Vitals (LCP/INP/CLS), render-blocking, image formats -> PageSpeed Insights (field data) + Lighthouse"

# ---------------------------------------------------------------- social
head_h "Social share metadata"
for p in og:title og:description og:url og:type; do
  [ -n "$(g "<meta[^>]*property=\"$p\"[^>]*>")" ] && pass "$p" || warn "missing $p"
done
[ -n "$(g '<meta[^>]*property="og:image"[^>]*>')" ] && pass "og:image" || fail "no og:image — link previews will have no image"
[ -n "$(g '<meta[^>]*name="twitter:card"[^>]*>')" ] && pass "twitter:card" || warn "no twitter:card"
[ -n "$(g '<meta[^>]*name="twitter:image"[^>]*>')" ] && pass "twitter:image" || warn "no twitter:image (falls back to og:image if present)"

# ---------------------------------------------------------------- structured data
head_h "Structured data"
LD="$(gc '<script[^>]*type="application/ld\+json"')"
if [ "$LD" -gt 0 ]; then
  pass "$LD JSON-LD block(s) present"
  TYPES="$(grep -oE '"@type" *: *"[^"]*"' "$HTML" | sed -E 's/.*"([^"]*)"$/\1/' | sort -u | paste -sd, -)"
  [ -n "$TYPES" ] && info "@type: $TYPES"
  info "validate at validator.schema.org + search.google.com/test/rich-results"
else
  warn "no JSON-LD structured data"
fi

# ---------------------------------------------------------------- PWA
head_h "PWA readiness"
MAN="$(g '<link[^>]*rel="manifest"[^>]*>')"
if [ -n "$MAN" ]; then
  pass "manifest linked: $MAN"
else
  fail "no <link rel=manifest> in HTML — not installable"
  for mp in manifest.json manifest.webmanifest site.webmanifest; do
    code="$(curl -sL --max-time 10 "$ORIGIN/$mp" -o /dev/null -w '%{http_code}' 2>/dev/null)"
    [ "$code" = "200" ] && info "(but $ORIGIN/$mp exists -> link it from <head>)"
  done
fi
[ -n "$(g '<meta[^>]*name="theme-color"[^>]*>')" ] && pass "theme-color" || warn "no theme-color meta"
[ -n "$(g '<link[^>]*rel="apple-touch-icon"[^>]*>')" ] && pass "apple-touch-icon (iOS)" || warn "no apple-touch-icon (iOS home-screen icon)"
[ -n "$(g 'apple-mobile-web-app')" ] && pass "apple-mobile-web-app meta present" || info "no apple-mobile-web-app-* meta (iOS standalone/splash)"
[ -n "$(g 'serviceWorker|registerSW|workbox')" ] && pass "service-worker registration referenced" || warn "no service-worker reference (no offline; no auto install prompt)"
info "installability + offline + maskable icons -> DevTools > Application; PWABuilder.com. (Lighthouse dropped its PWA category in v12.)"

echo
echo "==================================================================="
echo " Static pass done. Next: run the lab/manual checks flagged above"
echo " (Lighthouse mobile, PageSpeed Insights field data, axe, keyboard,"
echo "  screen reader, DevTools Application) per the skill reference files."
echo "==================================================================="
