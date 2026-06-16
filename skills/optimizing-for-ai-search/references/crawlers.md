# AI crawlers & robots.txt strategy

Reference for Step 3 of the skill. The single most common GEO mistake is
blocking the wrong crawler — this page exists to prevent that.

## Contents

- [The three tiers of AI bot](#the-three-tiers-of-ai-bot)
- [User-agent reference table](#user-agent-reference-table)
- [Decision: what to allow vs block](#decision-what-to-allow-vs-block)
- [Ready-to-paste robots.txt (stay citable, opt out of training)](#ready-to-paste-robotstxt-stay-citable-opt-out-of-training)
- [Hard caveats](#hard-caveats)

## The three tiers of AI bot

Conflating these is the root of most errors.

1. **Training crawlers** — collect data to train future models. Blocking them
   only affects what *future* models know. **No effect on whether you're cited
   today.** (`GPTBot`, `ClaudeBot`, `CCBot`, `Google-Extended`,
   `Applebot-Extended`.)
2. **Search / retrieval crawlers** — build the live index the assistant cites
   from. **Blocking these removes you from AI answers, often within hours.**
   (`OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot`, and the classic
   `Googlebot` / `Bingbot` that also feed AI Overviews and Copilot.)
3. **User-triggered fetchers** — fetch a specific URL in real time when a user
   pastes/asks about it. Behavior on robots.txt varies by vendor; don't rely on
   blocking them. (`ChatGPT-User`, `Claude-User`, `Perplexity-User`.)

## User-agent reference table

| Vendor | Training | Search / retrieval (→ citations) | User-triggered fetch |
|---|---|---|---|
| OpenAI | `GPTBot` | `OAI-SearchBot` | `ChatGPT-User` |
| Anthropic | `ClaudeBot` | `Claude-SearchBot` | `Claude-User` (older docs: `Claude-Web`) |
| Perplexity | — | `PerplexityBot` | `Perplexity-User` |
| Google | `Google-Extended` (Gemini-training opt-out token) | `Googlebot` (also powers AI Overviews / AI Mode) | — |
| Microsoft / Bing | — | `Bingbot` (powers Copilot retrieval) | — |
| Apple | `Applebot-Extended` (training opt-out token) | `Applebot` | — |
| Common Crawl | `CCBot` (feeds many models' training) | — | — |
| Meta / Amazon / ByteDance | `Meta-ExternalAgent` / `Amazonbot` / `Bytespider` | — | `meta-externalfetcher` |

Most listed bots honor robots.txt; `Bytespider` is frequently reported ignoring
it. Always verify the **current** token at the vendor's own docs and confirm bot
IPs against the vendor's published JSON list before trusting a UA string (UAs are
trivially spoofed).

## Decision: what to allow vs block

| Goal | Action |
|---|---|
| **Maximum AI visibility** (most sites) | Allow everything. At minimum allow all retrieval + user-triggered crawlers. |
| **Stay citable but opt out of model training** | Block only the *training* crawlers; explicitly allow the retrieval crawlers. (Template below.) |
| **Keep content out of AI entirely** | Block retrieval crawlers too — and accept you will not appear in AI answers. Note robots.txt is advisory; real exclusion needs UA/IP enforcement at the CDN/origin. |

There is evidence (contested) that publishers blocking AI crawlers saw notable
traffic declines — direction is plausible, exact figures are not settled.

## Ready-to-paste robots.txt (stay citable, opt out of training)

```text
# --- Opt OUT of model training ---
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: Applebot-Extended
Disallow: /

# --- Stay CITABLE in AI answers ---
User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Claude-SearchBot
Allow: /

# Default for everything else stays Allow.
Sitemap: https://example.com/sitemap.xml
```

Repeat the file per subdomain. Replace the `Sitemap:` host. If you only want max
visibility, drop the "opt out" block entirely.

## Hard caveats

- **robots.txt is a request, not enforcement.** Some crawlers ignore it; in 2025
  a major provider was caught using undeclared rotating crawlers to evade it.
  True blocking requires UA/IP rules at the CDN/origin.
- **Tokens change.** `Claude-SearchBot` and the training/search split are
  relatively new; re-check vendor docs before shipping a config.
- **A block in robots.txt ≠ removal from existing answers.** Already-indexed
  content can persist; opting out is forward-looking.
