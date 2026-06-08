# Question 1: Distributed URL Shortener

> Interviewer's guide for the 1-hour Google L5/L6 system-design round.
> Anchor problem for the **stateless-scale** archetype. The question is
> canonical (Alex Xu Vol 1 Ch. 8, Hello Interview, ByteByteGo), so the
> calibration value is *not* what the candidate knows — it's whether they
> can produce judgment under constraint in a problem they've almost
> certainly rehearsed.

---

## 1. Why this question (interviewer's framing)

URL shortener is the **easiest hard question** on the loop. Every candidate
has seen it. That's the point — the L5/L6 deltas aren't about whether they
can name "base62" or "Bigtable," they're about:

- whether they **commit to numbers** by minute 10 that actually constrain
  later decisions, vs. reciting Alex Xu's "100M/day,"
- whether they let the **read-heavy, hot-key, write-cheap workload shape**
  drive their cache/storage choices,
- whether they treat **ID generation as a distributed-systems problem**
  (allocator coordination, sequential-ID leakage, collision math) rather
  than "base62 of auto-increment, next topic,"
- whether they go beyond steady-state into **abuse, multi-region, cost, and
  10x evolution** unprompted.

### What "Hire" looks like at each level

**L5 Hire.** RPS + storage math committed by minute 10. Picks an ID scheme
and defends it in one sentence. One CDN/cache layer, one storage choice,
both justified. Goes deep on either read path or allocator unprompted.
Handles "what if shard 7 dies" calmly.

**L6 Hire.** All of the above, plus: drives the room (narrates the budget,
picks deep-dives), volunteers $/month, surfaces abuse/safety unprompted,
states an explicit CAP commitment for multi-region, articulates the 10x
evolution path with named seams, and talks about who would *own* each
piece in a real org.

### Three classic downlevel traps

1. **Base62-of-auto-increment without addressing predictability.** A
   sequential ID leaks neighbors. Missing this is the modal L4 answer.
2. **"We'll add a cache" with no number.** No hit rate, no stampede story,
   no TTL reasoning. "Named a product, didn't defend it" in raw form.
3. **Ignoring abuse / malicious URLs.** Shorteners are phishing
   infrastructure if you let them be. Silence here at L6 is close to
   disqualifying — the candidate is designing the feature, not the service.

---

## 2. The 60-minute plan

### 0–5 min — Intro

**Say:** *"I'm <name>, L7 on <unrelated infra team>. Tell me about yourself
in 60 seconds. Today: design a distributed URL shortener. Think bit.ly /
the old goo.gl. Drive it however you want; I'll interject as we go."*

**Listen for:** do they sit with the ambiguity or immediately start drawing.
**Push back when:** they whiteboard before scoping. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** almost nothing. If asked "what scale?" → *"Google scale, but you
tell me what that means."* If asked "analytics?" → *"What would you
support, and what would change if we cut it?"*

**Listen for:**
- Tight functional commit (shorten / redirect / custom alias / expiry /
  basic analytics). Bonus if they explicitly *cut* something.
- Non-functionals **with numbers**: QPS read+write, p99, availability,
  read:write ratio, retention.

**Push back when:**
- "Highly scalable" without a number → *"Quantify that."*
- No read:write ratio → *"Read-heavy or write-heavy? By how much?"*
- 12 functional requirements → *"Smallest useful v1?"*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip math, *"Before we draw, what does the
math tell us we need?"*

**Listen for:**
- Worked TPS: writes/sec, peak reads (5–10x avg), storage/yr, cache
  working set, egress.
- **Numbers that constrain a choice.** "10k writes/sec — one sequencer's
  worth, no sharded allocator needed" is L6-quality.
- Box diagram: LB → stateless app → ID allocator → KV → cache → CDN.
  Analytics fire-and-forget on the side.

**Push back when:**
- 11 boxes → *"Which are on the critical path? p99 budget per hop?"*
- Reflexive Spanner → *"What does Spanner cost you here?"*

### 25–45 min — Deep dives

The diagnostic phase. I steer to **two** of three:

- **ID allocator design** (always — most-rehearsed-least L5/L6 separator)
- **Read path: cache + CDN + stampede / hot-key**
- **Multi-region or abuse/safety** (whichever they didn't volunteer)

**Say:** *"Two app servers want a new ID at the same instant. What
happens?"* Later: *"Taylor Swift's marketing tweets one of your links.
Walk me through the next 10 seconds."*

**Listen for:** structured decomposition (name subproblem, two options,
commit, name cost), voluntary failure modes, and for L6 — cost framing,
blast radius, deployment safety.

**Push back when:** hand-waving → *"Say more. Data structure? Protocol?
SLO?"* Textbook answer undefended → *"Why not Snowflake?"*

### 45–55 min — Evolution / curveball

Pick **one**:
- *"10x traffic overnight. What breaks first?"*
- *"EU users need <50ms p99 from Frankfurt. What changes?"*
- *"Spammer makes 1M phishing URLs/hr. Walk me through it."*

**Listen for:** do they identify the seam to change, or redesign? L5 picks
one well; L6 picks one fluently and gestures at the others.

**Push back when:** they redesign → *"You have a working system. Minimum
change?"*

### 55–60 min — Wrap

**Say:** *"That's time. Anything you'd do differently with 15 more
minutes? Then — questions for me?"*

**Still scoring:** self-aware retro ("I didn't get to migration / DR"),
and what they ask (technical-reality questions read very differently
from comp/promo).

---

## 3. Probing prompts (the kit)

Pre-loaded, with the signal each one hunts for.

| Prompt | Signal hunted |
|---|---|
| *"Read:write ratio, and how confident?"* | Workload-shape grounding. ~100:1 should drive cache. |
| *"Commit to numbers: peak read/write QPS, p99, storage growth/yr."* | Unprompted-numbers. Balking here is no-hire by itself. |
| *"Pick an encoding scheme. Why?"* | ID gen as distributed-systems problem vs. string trick. |
| *"Base62 of auto-increment — what does my competitor learn over a week?"* | Trap for the rote answer. Sequential-ID prediction. |
| *"Two app servers want the next ID at the same instant. Walk me through it."* | Do they understand their allocator? |
| *"Collision probability with that scheme? Show the math."* | Birthday-paradox literacy for hash-based schemes. |
| *"Bigtable vs Spanner vs sharded MySQL — pick one, what did you give up?"* | Named-and-defended storage choice; bonus for cost. |
| *"Cache hit rate target? Protect against 1M QPS on one key."* | Request coalescing / negative caching / CDN by name or mechanism. |
| *"Custom aliases — what's the consistency requirement?"* | Strong-consistency-on-write subproblem; where Spanner earns its keep. |
| *"Analytics pipeline — do clicks block redirects?"* | SLO separation. Joining clicks to redirect path is down-level. |
| *"Spammer makes 1M phishing URLs/hr. Detection and response?"* | Abuse/safety. Expected unprompted at L6; backstop here. |
| *"EU users at <50ms p99 from Frankfurt. What changes?"* | CAP commit; AP for redirects, CP for alias claims. |
| *"Monthly cost at your QPS, back of envelope."* | L6 marker; L5s often skip. |
| *"SLO? What burns error budget first?"* | Ops; distinguishing redirect-SLO from create-SLO is a level-up. |
| *"Schema change on the shortlink table without an outage. How?"* | Paper-architect filter. |
| *"10x overnight. What breaks first?"* | Evolution. L6 names it in one sentence. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

I steer toward **two** of these three depending on what the candidate has
already self-selected.

### Deep dive A: ID allocator under contention

**Phrasing:** *"Two app servers in two regions, both at 5k QPS of writes,
both want the next ID. What's the on-the-wire protocol? What happens
when the sequencer dies?"*

**Strong L5 answer.** Range-leasing: a Chubby/ZK-backed sequencer hands
each app server a range of ~10⁴ IDs. App servers consume locally,
request a new range at 80% used. On failure, cached range serves
in-flight writes; standby takes over via leader election. Names the
trade-off: ranges burned on app crash → bounded waste.

**Strong L6 answer.** All of the above, plus:
- Explicitly rejects Snowflake IDs for this workload: base62-encoded
  Snowflake is ~11 chars vs. ~7 for a counter → worse UX.
- Names the **sequential-ID leakage problem unprompted** ("competitor
  observing 7gK and 7gL can scrape every new URL"). Fixes it with a
  **Feistel permutation** over the counter — cheap, reversible,
  bijective (zero collisions), uniformly distributed output.
- Blast radius: sequencer failure → <30s of write unavailability;
  redirects unaffected. "Acceptable, writes are the cold path."
- Ops: alerting on lease-exhaustion rate, not absolute counter value.

**Anti-signal.** "UUIDs base64'd." → Packet: *"Did not consider the
22-char shortlink UX impact or recognize ID generation as a distributed
systems problem."*

### Deep dive B: Hot-key read path

**Phrasing:** *"Celebrity tweets a shortlink. 5M redirects for one key
in 10 seconds. Walk me through what's hot, what's cold, what falls over."*

**Strong L5 answer.** Layered cache: CDN at the edge with Cache-Control,
Memcache behind it for the working set, Bigtable on miss. Names a 95%+
hit-rate target. Identifies the stampede (10k concurrent misses for the
same key all hit DB) and proposes request coalescing / single-flight.
TTL trade-off picked with a number.

**Strong L6 answer.** All of the above, plus:
- Quantifies: 1M QPS × 99% hit rate = 10k QPS on **one Bigtable row** →
  hot tablet that can't be rebalanced fast enough; tail latency
  degrades co-located rows.
- Solves with **client/CDN-side caching of the response itself** —
  long Cache-Control on the 302, so the celebrity URL is a *zero-RPC
  redirect* after the first hit per POP/browser.
- Negative caching for 404s (typo'd viral URLs).
- **301 vs 302 trade-off, named:** 301 is browser-cached forever →
  great hot-key behavior, but destroys per-click analytics and
  prevents us from revoking abuse-classified URLs. Commits to 302
  with a 600s Cache-Control on non-analytics URLs; `private, no-store`
  on analytics-tracked URLs.
- Ops: alert on cache miss rate per top-K key, not absolute QPS.

**Anti-signal.** "Add more cache nodes." → Packet: *"Did not identify
that the problem is single-key access pattern, not aggregate throughput;
did not bring up CDN, request coalescing, or 301/302 trade-off."*

### Deep dive C: Multi-region + abuse

**Multi-region:** *"EU redirects from Frankfurt at <50ms p99. What
changes?"*

**Strong L6 answer.** Explicit CAP commit: **AP for redirects, CP for
alias claims, AP for analytics rollup.** Redirects served from regional
Bigtable replicas (eventual consistency, ~5s replication lag → a
brand-new URL might 404 in EU briefly, acceptable). Alias-claim writes
go through a globally-serialized path (single global primary at this
QPS; migrate to Spanner-for-aliases-only if alias QPS grows past one
primary). Cross-region write latency on alias creation: 80–200ms p50,
fine on a cold path. Analytics aggregated regionally → BigQuery in
batch, 5-min freshness.

**Abuse:** *"Spammer makes 1M phishing URLs/hr. Walk me through it."*

**Strong L6 answer.** Three layers:
1. **At create:** synchronous Safe Browsing lookup (~10–20ms). Reject
   malicious targets with 400. Fail-closed on Safe Browsing outage.
2. **Rate limits:** authenticated quotas (100/day free, 10k/day paid);
   anonymous heavily IP-throttled + CAPTCHA above threshold. Stated
   plainly: "shorteners are phishing infrastructure; we are
   responsible for what flows through them."
3. **Post-hoc rescan:** daily Dataflow job re-scans recent URLs against
   Safe Browsing. Newly-malicious → flag set, redirect returns 451 to
   interstitial. Row preserved for audit / law enforcement.

**Anti-signal at L6.** Abuse not surfaced unprompted, or only
generically when prompted. → Packet: *"Did not engage with the
operational reality that shorteners are a phishing vector."*

---

## 5. Watch-outs / common traps

### Candidate-side

- **Sequential-ID prediction ignored.** Base62-of-counter without seeing
  the scraping risk. One prompt; if they still miss it, down-level signal.
- **Hash without collision math.** "MD5(url)[:7]" — birthday-paradox
  says ~50% collision at √(62⁷) ≈ 1M URLs. No math = don't understand
  what they proposed.
- **Cache stampede unhandled.** "Add a cache" without coalescing /
  single-flight.
- **Clicks on the hot path.** Analytics must be fire-and-forget.
  Write-then-redirect mis-ranks SLOs.
- **No abuse story** (covered above — 2026-era expectation).
- **Over-engineering day-1.** Active-active + custom Paxos allocator for
  an MVP. L6 move is to *name* the evolution path, not build it.
- **No cost math.** "We'd use Spanner" with no $/QPS comparison.
- **Short-URL length not defended.** 62⁷ ≈ 3.5T (95 years at 100M/day)
  vs 62⁶ ≈ 56B (~1.5 years). Pick 7 and justify; don't pick 8 by reflex.

### Interviewer-side

- **Letting them dwell on encoding for 20 min.** Base62 vs Snowflake is
  a 5-minute conversation. At 10, redirect: *"Call the scheme good;
  move on."*
- **Not prompting on abuse by min 40.** If they don't volunteer, I must
  ask — otherwise no signal either way in the packet.
- **Letting "we'd use Spanner" pass.** Always ask the cost.
- **Over-prompting.** If the packet reads like I led the design, the
  committee discounts. Stay quiet when they're moving.
- **Multi-region too early.** Saving it for min 45 tests evolution; at
  min 20 it becomes just another steady-state requirement.
- **Eating the candidate's 3-min question window.** Still scoring on
  Googleyness during their questions.

---

## 6. The golden answer (what a strong L6 candidate would produce)

What follows is the L6-quality walk-through, structured the way I'd
expect to hear it in the room. Numbers are explicit. Trade-offs are
committed.

### 6.1 Functional requirements (committed scope)

v1: shorten (authed POST → short URL); redirect (GET → 302); custom
alias (globally unique slug); optional TTL (expired → 410); basic
analytics (total clicks, last-N-days series, top referrers — **not**
real-time, ~5 min freshness is fine).

**Out of scope v1, said out loud:** A/B test on destinations, per-click
geo/device dashboards, link previews, team/org sharing semantics.

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| Peak read QPS | **500k QPS** (global) | Assumption: bit.ly-scale, 100B redirects/yr ≈ 3k avg, 5–10× peak → 30k avg, 500k peak. Worst-case viral events: 1M+ for a single key. |
| Peak write QPS | **5k QPS** (global) | ~100M new URLs/day = 1.2k/s avg, 5× peak → 5–10k. Read:write ≈ 100:1. |
| p99 redirect latency | **<100ms end-to-end**, <30ms server-side | This is the user-facing SLO. Anything worse, the redirect feels broken. |
| p99 create latency | **<500ms** | Acceptable — it's a cold path; Safe Browsing lookup is on it. |
| Availability — redirect | **99.99%** | 52 min/yr. This is the customer-facing number. |
| Availability — create | **99.9%** | 9 hr/yr. Lower bar because creates are async-tolerable. |
| Durability | **11 nines** (Colossus / GCS replication) | We are not allowed to lose a shortlink — it's a permanent URL. |
| Retention | URLs live forever by default; TTL'd URLs purged 30 days after expiry | Audit / law-enforcement requirements outlive product use. |
| Storage growth | ~100B URLs over 10 years ≈ 50 TB primary (500 B/row) | See 6.3. |

### 6.3 Capacity estimation (worked)

- **Row size:** short_id (8B) + long_url (~100B avg) + metadata
  (~40B) + overhead → call it **500 B** for math.
- **Storage:** 100M/day × 365 × 10yr = 365B rows × 500 B = **~180 TB**
  (≈ 1 PB at 5× replication). Trivial for Bigtable/Colossus. Cost
  driver is not storage.
- **Hot working set.** Pareto-ish: truly-hot URLs (>1 QPS sustained)
  ≈ 10M rows × 200 B = **~2 GB per region**, fits Memcache cleanly.
  CDN handles the moderately-popular long tail.
- **Egress:** 500k × 300 B ≈ **150 MB/s = 1.2 Gbps**. Google edge
  handles trivially.
- **Click events:** 500k/s × 200 B = 100 MB/s → regional Pub/Sub →
  Dataflow → BigQuery.

**Numbers that changed a design choice:**
- 5k writes/sec ≈ one sequencer's worth → no sharded allocator.
- 2 GB hot set fits per-region cache → no global cache tier needed.
- 100 MB/s click stream → clicks **cannot** block redirect.

### 6.4 API design

```
POST /v1/urls          { long_url, custom_alias?, expires_at? }
                       Auth + Idempotency-Key required
                       → 201 / 400 (Safe Browsing) / 409 / 429
GET  /:short_id        → 302 / 410 (expired) / 404 / 451 (abuse takedown)
GET  /v1/urls/:id/stats (owner-only)
DELETE /v1/urls/:id    (soft-delete; row preserved for audit)
```

Idempotency-Key deduped on (user_id, key) for 24h: retries must not
produce two short URLs.

### 6.5 Data model

Primary store: **Bigtable.** Three tables:

- `shortlinks` — row key `short_id` (uniformly random base62 → no hot
  tablets). Columns: `long_url`, `owner_id`, `created_at`,
  `expires_at`, `flags` (deleted / abuse_takedown / custom_alias),
  `safe_browsing_verdict`, `last_scanned_at`.
- `aliases` — row key `alias_string`, value `short_id` (custom aliases
  resolved via two-hop lookup).
- `user_quota` — row key `user_id`, atomic counter for rate limiting.

**Why Bigtable:** uniformly random keys = no hot tablets at steady
state; single-row atomicity is enough on the hot path; ~5–10× cheaper
than Spanner at this QPS because we don't pay cross-region Paxos on
every write. **Gave up:** strong cross-region consistency on aliases —
handled explicitly in 6.10. **Why not Spanner:** at 500/s alias QPS we
can serialize via a single-region primary; full Spanner only earns its
keep if alias QPS outgrows that. **Why not sharded MySQL:** resharding
pain at 365B rows.

### 6.6 High-level architecture

```
                          ┌───────────────────┐
                          │  Google Edge CDN  │  <── 80%+ of redirects
                          │  (301/long-TTL)   │      served here
                          └─────────┬─────────┘
                                    │ miss
                          ┌─────────▼─────────┐
                          │  Regional GFE +   │
                          │  L7 Load Balancer │
                          └─────────┬─────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
        ┌─────▼─────┐         ┌─────▼─────┐         ┌─────▼─────┐
        │  Redirect │         │  Redirect │         │  Redirect │
        │  Service  │   ...   │  Service  │   ...   │  Service  │
        │ (stateless│         │ (stateless│         │ (stateless│
        │   Borg)   │         │   Borg)   │         │   Borg)   │
        └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
              │                     │                     │
              └──────────┬──────────┴─────────┬───────────┘
                         │                    │
              ┌──────────▼──────────┐  ┌──────▼──────────┐
              │ Regional Memcache   │  │ Analytics Pub/  │
              │ (hot key tier, 2GB) │  │ Sub (fire-and-  │
              └──────────┬──────────┘  │ forget click    │
                         │ miss        │ events)         │
              ┌──────────▼──────────┐  └──────┬──────────┘
              │     Bigtable        │         │
              │  (shortlinks table) │         ▼
              │  multi-region repl. │   Dataflow → BigQuery
              └─────────────────────┘   (5-min freshness)

  Create path (separate, lower-QPS):
  Client → GFE → Create Service → [Safe Browsing] → ID Allocator (Chubby
                                                    lease)
                                → Bigtable shortlinks (write)
                                → If custom_alias: Bigtable aliases
                                  (conditional-put for uniqueness)
                                → Idempotency cache (Memcache, 24hr)
```

### 6.7 Encoding scheme — defended with numbers

**Decision: 7-char base62, output of a Feistel permutation over a
distributed 64-bit counter.**

- **Length.** 62⁷ ≈ 3.5×10¹² → ~95 years at 100M URLs/day. 62⁶ ≈
  5.6×10¹⁰ → ~1.5 years, too tight. 62⁸ overkill / worse UX. Pick 7.
- **Counter.** Single logical 64-bit counter; Chubby-backed sequencer
  hands app servers ranges of 10⁴ IDs. At 5k writes/s, one lease
  request every ~2s. App-server crash → bounded waste of ≤10⁴ IDs.
- **Why not Snowflake.** Timestamp+machine portion forces ~11 chars
  after base62. Worse UX for a service whose product is URL length.
- **Feistel permutation (the L6 move).** Raw `counter → base62` leaks
  sequence (`aB3kZ8q` and `aB3kZ8r` issued back-to-back → competitor
  scrapes every new URL). Pipe the counter through a keyed Feistel
  network before base62-encoding. Bijection → **zero collisions by
  construction**, uniformly distributed output, fully reversible (we
  use that for debugging).
- **Allocator failure.** Cached range serves in-flight creates;
  standby sequencer takes over in <30s via Chubby election. Redirects
  unaffected. Well within 99.9% create SLO.

### 6.8 Read path & caching strategy

Target: 99%+ hit rate, <30ms p99 server-side.

1. **Google Edge CDN.** Serves 302 with `Cache-Control: public,
   max-age=600` for non-analytics URLs; `private, no-store` for
   analytics-tracked ones. This is *the* viral-spike mitigation.
2. **Regional Memcache.** ~2 GB per region, LRU, 1hr TTL,
   refresh-on-miss.
3. **Bigtable.** Authoritative; only reached on miss.

**Stampede prevention.** Single-flight at the app tier:
`map[short_id] → Future<Result>`. First miss fires the Bigtable read;
concurrent misses for the same key await the in-flight future. Caps
Bigtable read amplification at (num_app_servers) regardless of QPS.

**Negative caching.** 404s cached 60s. Prevents typo'd-viral-URL DOS.

**301 vs 302.** 302 by default — preserves our ability to revoke
abuse URLs and to track clicks. Long Cache-Control gives most of the
hot-key benefit of 301 without forfeiting revocability.

### 6.9 Write path

POST flow: idem-key lookup → quota check → Safe Browsing sync
(10–20ms; fail-closed on outage) → if custom_alias, conditional-put
into `aliases` (409 on collision) → otherwise, next ID from local
lease, Feistel-permute, base62-encode → write `shortlinks` → cache
`(user, idem_key) → short_id` for 24h → 201. Idempotency window: 24h.

### 6.10 Multi-region

CAP commits, said out loud: **AP for redirects, CP for alias claims,
AP for analytics rollup.**

- **Redirects:** active-active, regional Bigtable replicas + regional
  Memcache. Eventual consistency (≤5s typical replication lag) — a
  brand-new URL might 404 in EU for a few seconds. Product accepts.
- **Creates:** routed to user's home region; allocator runs in one
  global primary with hot-standby (<30s failover on create path).
- **Custom alias uniqueness (the hard bit).** Alias-claim writes
  serialize through a single global primary. At 500/s this is fine;
  cross-region p50 ~100ms on a cold path. Migrate to Spanner-for-
  aliases-only if alias QPS grows past what one primary can serve.
- **Analytics:** regional Pub/Sub → Dataflow → cross-region BigQuery
  rollup. 5-min freshness, explicitly *not* real-time.

### 6.11 Abuse / malicious URLs

Three layers (full detail in deep-dive C):
1. Synchronous Safe Browsing at create; fail-closed.
2. Authenticated quotas; anonymous IP throttling + CAPTCHA.
3. Daily Dataflow rescan; newly-malicious → flag set; redirect serves
   451 to interstitial. Row preserved for audit.

Abuse pipeline has its own on-call and SLO (24h median time-to-
takedown). It is infrastructure, not a feature.

### 6.12 Cost (back-of-envelope, monthly)

Public GCP pricing as a proxy for internal cost at the 6.2 QPS:

| Component | Notes | $/mo |
|---|---|---|
| Bigtable | ~100 nodes for 500k QPS read + 5k write + hot-key headroom | ~$70k |
| Regional Memcache | ~10 regions × 2 GB | <$5k |
| CDN egress | ~400 TB/mo at $0.02–0.08/GB | ~$20k |
| Analytics (Pub/Sub + Dataflow + BigQuery) | 100 MB/s ingest | ~$30k |
| App tier (Borg) | ~500 cores | ~$10k |
| Chubby allocator | rounding error | — |
| **Total** | | **~$135k/mo** |

vs. a Spanner-backed equivalent at ~$700k–$1M/mo. The 5–10× cost
delta is the whole reason we chose Bigtable.

### 6.13 Failure modes & blast radius

- **Bigtable region failure** → reads fail over <10s, writes pause
  ~30s during election. Redirects unaffected (other regions serve).
- **Allocator failure** → cached leases continue, new leases blocked
  ~30s. Create-only blip.
- **Memcache region failure** → falls through to Bigtable; p99 rises
  ~30→80ms until cache reheats (~5 min).
- **CDN failure (worst case)** → 500k QPS hits backend directly.
  Mitigation: regional Memcache absorbs hot set; Bigtable provisioned
  for 2× expected traffic.
- **Safe Browsing outage** → fail-closed on creates (deliberate
  safety choice; documented in runbook).

**SLO/error budget.** 99.99% redirect → 4.32 min/mo budget. Page at
10× burn. Create SLO (99.9%) separate so create incidents don't burn
the redirect budget.

### 6.14 Evolution at 10x

5M QPS reads / 50k QPS writes:
- **Allocator:** still one logical sequencer; larger leases.
- **Bigtable:** scale nodes ~linearly; Feistel keys keep distribution
  uniform → no hot-tablet surprises.
- **Cache:** 2 → 20 GB per region, still one tier.
- **CDN:** Google edge handles transparently.
- **Alias allocator:** 500/s → 5k/s — the named seam. Migrate to
  Spanner-for-aliases. Migration path was set up at v1.
- **Analytics:** scale Dataflow linearly; partition BigQuery by month.
- **Cost:** ~linearly to ~$1.3M/mo — still <2× a hypothetical
  Spanner-from-day-1 design at 1× scale.

**What does not change:** encoding scheme (95-year runway), API,
write protocol. The seams I named at v1 are the seams at 10x.

---

## 7. Signals scorecard

Left column is packet-quotable evidence from the transcript. Right is
the level call.

| Evidence | Call |
|---|---|
| No commit to QPS or read:write after two prompts; "highly scalable" without numbers. | **Strong No Hire** |
| Proposed MD5(long_url)[:7]; under pressure on collisions, fell back to "retry loop" without birthday-paradox math. | **No Hire** |
| Base62-of-auto-increment; when prompted on sequential-ID leakage, didn't see the problem or proposed "we'd encrypt them" without specifying how. | **Lean No Hire** |
| Numbers (100k QPS, p99 200ms, 100:1) by min 8. Clean LB→app→cache→Bigtable. Named request coalescing on hot-keys. Did not surface CDN or 301-vs-302 even when prompted. | **Hire L5** |
| All of the above, **unprompted**. Range-leased counter with named blast radius and lease-waste trade-off. Bigtable over Spanner with a 5× cost-delta estimate. Volunteered cache stampede with coalescing + negative caching. CAP commit on multi-region: AP redirects, CP aliases, named latency cost on creates. | **Hire L5 / Lean L6** |
| All of L5-Hire-plus, **plus**: identified sequential-ID leakage unprompted, proposed Feistel permutation (bijection → zero collisions). Brought up abuse / Safe Browsing / rate-limiting before I asked. Volunteered 301-vs-302 with analytics implication named. Surfaced $/mo by min 50. Under 10× curveball, named exactly two components to change and the migration path in <2 min. Narrated the budget twice. | **Hire L6** |
| Everything in L6, **plus**: named what they'd delegate vs. own ("I'd own the redirect SLO and the allocator; analytics goes to the team that runs Dataflow"); defended their multi-region design against my pushback with a quantitative argument; closed with a self-aware retro on the one thing they didn't get to. | **Strong Hire L6** |

---

*End of guide. Next in this series:* `02-news-feed.md` *(stateful
consistency anchor) and* `03-top-k-trending.md` *(real-time /
streaming anchor); see* `05-rate-limiter.md` *for the operational
multi-tenant anchor.*
