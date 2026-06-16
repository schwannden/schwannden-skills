#!/usr/bin/env bash
#
# geo-audit.sh — deterministic AI-friendliness (GEO/AEO) audit for one URL.
#
# Checks the things that are OBJECTIVELY verifiable today (the rest of GEO is
# judgment — see the skill body):
#   1. robots.txt directives for the AI crawlers that matter
#   2. Server-side rendering: does the content exist in raw HTML (no JS)?
#   3. AI-bot access: does the page return 200 to an AI user-agent?
#   4. Structured data: JSON-LD blocks present + valid + their @types
#   5. llms.txt presence (informational only — low/unproven value)
#
# Requires: curl. Strongly recommended: python3 (stdlib only) for robust HTML
# parsing; without it the script falls back to a cruder awk text extractor and
# best-effort JSON-LD detection.
#
# Exit code is always 0 (this is a report, not a gate); findings print as
# [PASS] / [WARN] / [FAIL] / [INFO] lines.
#
# Usage:  ./geo-audit.sh https://example.com/some/page
#
set -uo pipefail

URL="${1:-}"
if [ -z "$URL" ]; then
  echo "usage: $0 <url>" >&2
  echo "example: $0 https://example.com/blog/post" >&2
  exit 2
fi

# Normalise: derive scheme://host for robots.txt and llms.txt lookups.
ORIGIN="$(printf '%s' "$URL" | sed -E 's#^(https?://[^/]+).*#\1#')"

# A current AI search/retrieval crawler UA. These are the bots that decide
# whether you can be CITED in AI answers (training bots are a separate concern).
AI_UA="Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)"
BROWSER_UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

PYTHON="$(command -v python3 || true)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

pass() { printf '  [PASS] %s\n' "$1"; }
warn() { printf '  [WARN] %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; }
info() { printf '  [INFO] %s\n' "$1"; }
hdr()  { printf '\n=== %s ===\n' "$1"; }

# curl wrappers: follow redirects, fail soft, short timeout, given UA.
fetch()  { curl -sL --max-time 25 -A "$1" "$2" 2>/dev/null; }
status() { curl -sL --max-time 25 -o /dev/null -w '%{http_code}' -A "$1" "$2" 2>/dev/null; }

echo "GEO audit for: $URL"
echo "Origin:        $ORIGIN"
[ -z "$PYTHON" ] && warn "python3 not found — using degraded HTML parsing. Install python3 for accurate results."

# --- 1. robots.txt -----------------------------------------------------------
hdr "1. robots.txt — AI crawler access"
ROBOTS="$(fetch "$BROWSER_UA" "$ORIGIN/robots.txt")"
if [ -z "$ROBOTS" ]; then
  info "No robots.txt found (or empty). All crawlers allowed by default."
else
  RETRIEVAL_BOTS="OAI-SearchBot PerplexityBot Claude-SearchBot Googlebot Bingbot"
  TRAINING_BOTS="GPTBot ClaudeBot CCBot Google-Extended Applebot-Extended"

  check_bot() { # check_bot <name> <category>
    local bot="$1" cat="$2" block
    # Per-agent block detection: agent stanza followed by Disallow: /
    block="$(printf '%s' "$ROBOTS" | tr -d '\r' | awk -v b="$bot" '
      BEGIN{IGNORECASE=1; inblk=0}
      /^[[:space:]]*user-agent:/ {
        ua=$0; sub(/^[[:space:]]*[Uu]ser-agent:[[:space:]]*/,"",ua)
        inblk = (tolower(ua)==tolower(b)) ? 1 : 0
      }
      inblk && /^[[:space:]]*disallow:[[:space:]]*\/[[:space:]]*$/ {print "blocked"; exit}
    ')"
    if [ "$block" = "blocked" ]; then
      if [ "$cat" = "retrieval" ]; then
        fail "$bot is BLOCKED — this removes you from its AI answers/citations."
      else
        info "$bot (training) is blocked — opts out of model training; no citation impact."
      fi
    else
      pass "$bot allowed."
    fi
  }
  echo "  -- search/retrieval crawlers (block = invisible in AI answers) --"
  for b in $RETRIEVAL_BOTS; do check_bot "$b" "retrieval"; done
  echo "  -- training crawlers (block = training opt-out only) --"
  for b in $TRAINING_BOTS; do check_bot "$b" "training"; done
  printf '%s' "$ROBOTS" | grep -qi '^[[:space:]]*sitemap:' \
    && pass "Sitemap declared in robots.txt." \
    || warn "No Sitemap: line in robots.txt — add one to aid non-JS crawlers."
fi

# --- 2 & 3. rendering + AI-bot access ----------------------------------------
hdr "2. Server-side rendering & AI-bot access"
CODE_AI="$(status "$AI_UA" "$URL")"
[ "$CODE_AI" = "200" ] \
  && pass "Page returns 200 to an AI crawler UA (OAI-SearchBot)." \
  || fail "Page returns HTTP $CODE_AI to an AI crawler UA — check UA blocking/cloaking."

HTML="$(fetch "$AI_UA" "$URL")"
RAW_BYTES=${#HTML}

# Parse the page roughly the way a non-JS crawler "sees" it. Prefer python3
# (stdlib HTMLParser — handles minified one-line HTML correctly); fall back to
# awk. Emits: WORDS / SPAEMPTY / LDCOUNT / LDTYPES / LDBAD.
if [ -n "$PYTHON" ] && [ -f "$SCRIPT_DIR/_parse_html.py" ]; then
  PARSED="$(printf '%s' "$HTML" | "$PYTHON" "$SCRIPT_DIR/_parse_html.py")"
  WORDS=$(printf '%s' "$PARSED" | sed -n 's/^WORDS=//p')
  SPAEMPTY=$(printf '%s' "$PARSED" | sed -n 's/^SPAEMPTY=//p')
  LDCOUNT=$(printf '%s' "$PARSED" | sed -n 's/^LDCOUNT=//p')
  LDTYPES=$(printf '%s' "$PARSED" | sed -n 's/^LDTYPES=//p')
  LDBAD=$(printf '%s' "$PARSED" | sed -n 's/^LDBAD=//p')
else
  # awk fallback: split on '<' so each tag lands on its own line, drop
  # script/style blocks via a state machine, strip the leading tag, count words.
  WORDS="$(printf '%s' "$HTML" | tr '\n' ' ' | sed 's/</\n</g' | awk '
      BEGIN{skip=0; n=0}
      /^<script/   {skip=1; next}
      /^<\/script/ {skip=0; next}
      /^<style/    {skip=1; next}
      /^<\/style/  {skip=0; next}
      skip{next}
      { line=$0; sub(/^<[^>]*>/,"",line); n+=split(line,a,/[[:space:]]+/) }
      END{print n+0}')"
  SPAEMPTY=0
  printf '%s' "$HTML" | tr '\n' ' ' | grep -Eqi '<div[^>]+id="(root|app|__next|__nuxt)"[^>]*>[[:space:]]*</div>' && SPAEMPTY=1
  LDCOUNT="$(printf '%s' "$HTML" | grep -ciE 'application/ld\+json')"
  LDTYPES="$(printf '%s' "$HTML" | tr '\n' ' ' | grep -oiE '"@type"[[:space:]]*:[[:space:]]*"[^"]+"' | sed -E 's/.*:[[:space:]]*"//; s/"//' | sort -u | tr '\n' ' ')"
  LDBAD=0
fi

info "Raw HTML size: ${RAW_BYTES} bytes; visible content units (latin words + CJK chars, no JS): ${WORDS:-0}"
if [ "${WORDS:-0}" -ge 250 ]; then
  pass "Substantial text content is present in raw HTML (server-rendered)."
elif [ "${WORDS:-0}" -ge 50 ]; then
  warn "Thin raw-HTML content (${WORDS} words). Confirm key facts aren't JS-injected."
else
  fail "Almost no text in raw HTML (${WORDS:-0} words) — likely client-rendered (SPA). Most AI crawlers will see an empty page. Use SSR/SSG or pre-rendering."
fi
[ "${SPAEMPTY:-0}" = "1" ] && warn "Found an empty SPA mount node (#root/#app/#__next). Content is hydrated by JS — invisible to non-rendering AI crawlers."

# --- 4. structured data (JSON-LD) --------------------------------------------
hdr "4. Structured data (JSON-LD)"
if [ "${LDCOUNT:-0}" -lt 1 ]; then
  warn "No JSON-LD structured data found. Add Organization/Article/Product/BreadcrumbList as applicable (must match visible content)."
else
  pass "JSON-LD present (${LDCOUNT} block(s))."
  [ -n "${LDTYPES// /}" ] && info "Declared @type(s): ${LDTYPES// /, }"
  if [ -n "$PYTHON" ]; then
    [ "${LDBAD:-0}" = "0" ] \
      && pass "All JSON-LD blocks parse as valid JSON." \
      || fail "${LDBAD} JSON-LD block(s) do not parse as valid JSON."
  else
    info "Install python3 to validate JSON-LD syntax."
  fi
  info "Validate semantics in Google Rich Results Test + validator.schema.org (no official CLI)."
fi

# --- 5. llms.txt -------------------------------------------------------------
hdr "5. llms.txt (informational)"
LLMS_CODE="$(status "$BROWSER_UA" "$ORIGIN/llms.txt")"
if [ "$LLMS_CODE" = "200" ]; then
  info "/llms.txt present. Note: no major AI engine has confirmed using it; treat as low/unproven value, not a citation lever."
else
  info "/llms.txt absent (HTTP $LLMS_CODE). Optional and unproven — skip unless you run a docs site. Never use it as a substitute for real server-rendered HTML."
fi

hdr "Done"
echo "This script covers the DETERMINISTIC checks. Content quality (answer-first"
echo "structure, statistics/citations/quotations, E-E-A-T, freshness) and off-site"
echo "authority are judgment calls — see the skill body and references/."
