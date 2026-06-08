# Question 2: News Feed (Fan-Out Tradeoffs)

*Interviewer guide + golden answer for the 1-hour Google L5/L6 system-design
round. The prompt: "Design a social-media news feed — Twitter home timeline,
Instagram main feed, or YouTube subscriptions." This is the
**stateful-consistency / fan-out** anchor question in the loop.*

Voice: senior peer. Numbers are stated as assumptions where they are
assumptions. No Google-internal product names are invented — public Google
infra (Spanner, Bigtable, Memcache, Colossus, BigQuery, Pub/Sub) is named
where it is genuinely the natural fit.

---

## 1. Why this question (interviewer's framing)

News feed is the canonical **stateful-consistency / fan-out tradeoff**
question. There is no single right answer — the interviewer is listening
for a candidate who can **name the tradeoff, commit to a position, and
defend it with numbers**. The question simultaneously tests:
read/write asymmetry (~100:1), power-law fanout (median follower count
≪ celebrity follower count, so "average case" doesn't exist), freshness
vs cost under an explicit SLO, and evolution under scale (push works at
1M DAU, breaks differently at 100M and 1B). Staff-level judgment is
which seam you build *now* so you don't re-platform later.

### L5 vs L6 bar

| | L5 "Hire" | L6 "Hire" |
|---|---|---|
| **Fan-out** | Picks one strategy cleanly; names the celebrity problem when prompted | Volunteers hybrid fan-out with a **defended celebrity threshold (a specific number with math)** before being asked |
| **Ranking** | "We can sort by recency, or score by engagement features" | Designs a two-stage candidate-gen + ranker pipeline with explicit feature freshness budget, says where the model runs and what it costs per QPS |
| **Freshness** | "It should be reasonably fresh" | Names an SLO: "p99 visible within 5s for normal posters; 60s acceptable for celebrities" — and **uses that number to size the fan-out workers** |
| **Storage** | Names Redis / Memcache / a SQL store with reasonable shape | Sizes the per-user feed cache, defends Bigtable-vs-Spanner for the follow-graph, computes monthly storage cost |
| **Evolution** | Mentions sharding when prompted | Volunteers the 10x and 100x evolution: when does pure-write break, what's the seam to hybrid, what's the migration plan |
| **Voice** | Reactive — answers the questions asked | Drives — narrates the plan, names what they'll skip, surfaces cost/blast-radius unprompted |

The hybrid fan-out decision *with a defended threshold* is **the** L6
separator on this question. An L5 who delivers a clean pure-write design
gets a Hire at L5; an L6 who delivers that same answer gets downleveled.

### Classic downlevel traps

- **Pure fan-out-on-write at celebrity scale** — never returns to fix
  the 100M-follower case. Packet quote: *"redesigned ad hoc when asked;
  did not size fan-out lag or propose a threshold."*
- **Pure fan-out-on-read at hot-user scale** — never confronts that an
  active user reading 800 follows at 200ms p99 is not free.
- **Names celebrity problem without quantifying the threshold.** "We'd
  do something different" is hand-waving.
- **No ranking discussion.** Ships strict reverse-chronological in
  2026; modern feeds *are* ranking systems with a fan-out attached.
- **"Redis" as a magic word** — no contents, sharding, sizing, or
  failure model.
- **No freshness SLO** — without a number, every downstream sizing
  decision is unmotivated.

---

## 2. The 60-minute plan

The clock is approximate. The interviewer is not running a stopwatch —
they are running a budget. The signal they're producing for the packet is
*"candidate ran their own clock and got to the hard parts."*

### 0–5 min — Intro & setup

**Say:** One-line bio, candidate same, then deliberately flat prompt:
*"I'd like to design a social-media news feed. Think Twitter home
timeline, Instagram feed, or YouTube subscriptions. How would you
approach this?"* No scale, latency, or scope volunteered.

**Listening for:** Do they sit with ambiguity? L6 marker: 3-4
load-bearing clarifying questions, not 12 trivia ones.

**Stay quiet.** This is their warm-up.

### 5–15 min — Requirements & scope

**Say:** Mostly nothing. Crisp scale answers when asked ("yes, 200M
DAU"). If by minute 10 they haven't named a freshness SLO or R:W
ratio, prompt: *"What latency budget do you want for feed load?"*

**Listening for:** post / follow / view-feed / ranking signal / basic
engagement in scope. **Non-functional reqs with numbers** (the gate):
DAU, peak QPS, follow-graph distribution, R:W, p99 feed-load,
**freshness SLO**. Out-of-scope cuts named explicitly — L6 says
*"I'm cutting cold-start recommendations as a separate system, not
because they're easy."*

**Push back** if they wave at scale; stay quiet if they commit.

### 15–25 min — Capacity + high-level design

**Say:** Nothing for the first 5 min. If they're stuck, ask *"what
does that mean for storage footprint?"*

**Listening for:** napkin math that **changes a design decision**.
Not "2B posts/day" alone but "2B posts × ~150 avg followers = ~20M
fanout writes/sec peak — that's the system pressure point." Whether
they grok that **fanout volume**, not post volume, scales the system.
The high-level diagram must name a fanout service, feed cache, post
store, follow-graph store, ranking step.

**Stay quiet** if they pick pure write-fanout or pure read-fanout
without addressing the other case. Note it. Come back at minute 40.
Do *not* tip my hand.

### 25–45 min — Deep dives (~20 min)

Mandatory: **fan-out with hybrid decision**. Candidate picks the other
two; I steer if they pick low-yield. Strong seconds: **ranking
pipeline**, **caching strategy**, **multi-region delivery**.

**Listening for:** fan-out — a **threshold with a number**, worker
pool sized, lag SLO handled. Ranking — candidate-gen separated from
scoring, feature freshness named, model serving cost grounded.
Caching — contents, size per user, eviction, cold-start.

**Push back hard** on the celebrity case if not volunteered. Push
gently on cache invalidation if treated as "we update on write."

### 45–55 min — Evolution / failure / pushback

**Say:** *"How does this break at 10x? What if the fanout queue
backs up?"* Then curveball: *"A celebrity with 80M followers posts
and the queue shows 6-hour lag. What do you do now, and as
post-mortem action?"*

**Listening for:** a plan, not panic. *"Right now: prioritize active
followers, degrade that author to read-merge, alert. Post-mortem:
drop hybrid threshold from 1M → 500k, add per-author rate limit, add
kill switch."* Whether they name **blast radius** explicitly. Whether
the celebrity case was *designed in* (L6) or *invented now* (L5).

### 55–60 min — Wrap

*"What didn't we get to? Questions for me?"* Self-aware narration
(*"we skipped abuse and ML ranking depth"*) is positive signal.
They're still being scored.

---

## 3. Probing prompts (the kit)

The interviewer carries roughly this kit in their head. Most go unused
in any given round; the value is that they're pre-loaded so silence
can be used deliberately.

**Requirements**
1. *"What's a feed item — posts only, or retweets/replies/comments?"* — flushes scope creep; L6 cuts explicitly.
2. *"Strict recency, engagement-weighted, or ML-scored?"* — forces a ranking commitment, which propagates everywhere.
3. *"Ads in scope?"* — L6 models ad insertion as a parallel candidate-gen merged at ranking, then cuts.

**Capacity**
4. *"DAU? Posts per user/day? Read:write ratio?"* — these three numbers drive everything. Signal: committed, not ranges.
5. *"Is the follower distribution uniform?"* — if they say yes, design is wrong. Correct answer: long-tail power law.
6. *"Peak vs steady-state posts/sec?"* — the 10x peak factor sizes the fanout queue.

**Fan-out (the mandatory dive)**
7. *"How do you choose push vs pull?"* — L6: hybrid with defended threshold; L5: picks one, acknowledges the other; downlevel: picks one and stops.
8. *"At what follower count do you flip, and why?"* — forces a number with math, not a round guess.
9. *"Latency budget post-create → follower-visible?"* — the freshness SLO; without it, worker sizing is unmotivated.

**Storage**
10. *"Where do feeds, posts, and the follow graph live — one store or three? Why?"* — forces defended separation by access pattern.
11. *"Size of a single user's feed cache? Eviction policy?"* — exposes "Redis" used as a label.

**Ranking**
12. *"Ranking at fan-out or read time? Feature freshness?"* — L6 says *both*: cheap features bind at fanout, expensive at read.
13. *"Cost-per-query of the ranker? Running a 300ms model on the read path?"* — grounds the pipeline in a real budget.

**Caching & ops**
14. *"What invalidates the feed cache, and who's responsible?"* — strong answer: fanout writer is sole producer; reads never invalidate; eventually consistent.
15. *"Cold-start: a user returns after a month — what happens?"* — forces a build-on-demand path that survives a cohort returning.
16. *"Three regions now. Where are writes home-roomed? Cross-region consistency budget?"* — the L6 evolution prompt.
17. *"Fanout queue is 6 hours behind. Walk me through what you do."* — operational scar tissue. Signal: plan, not panic.
18. *"Storage cost of materialized feeds vs recomputing on read?"* — cost reasoning unprompted is an L6 lean-in signal.

**Abuse / cold-start**
19. *"What does a new user see on day 1 before any follows?"* — most candidates fumble cold-start.
20. *"How do we stop a coordinated spam ring?"* — Google-shaped concern; L6 has a one-paragraph answer.

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

Three deep dives the interviewer is most likely to steer into. One is
mandatory; the others depend on candidate strengths.

### Deep dive A (MANDATORY) — Fan-out strategy & hybrid threshold

**Question:** *"Walk me through what happens when a user creates a post.
Who writes what, where? And what changes if that user has 50M followers?"*

**Strong L5 answer:** fanout service consumes a post-created event,
writes post_id into each follower's feed cache. Identifies the celebrity
break; proposes a threshold (e.g. 100k); notes feed reads now have two
sources (cached fanout + on-demand merge); calls out ordering and dedup.
Shaky on the math behind the threshold.

**Strong L6 answer adds:**
- **Defended threshold with math:** "Below 1M followers, push. At 1M
  followers × 1 post/active-hour, peak per-author fanout is ~17k
  writes/sec — within a sharded worker pool. Above 1M, push is
  cheaper to *skip*: a 50M-follower celebrity post is 50M writes in
  seconds; we'd rather merge at read time for the ~10M of those
  followers who'll actually be online inside the 60s window.
  Threshold sits at 1M because worker-saturation cost equals
  amortized read-merge cost there."
- **Per-path freshness SLO:** normal p99 < 5s post-to-visible;
  celebrity p99 < 60s with a 30-60s merge TTL.
- **Worker-pool sizing:** ~3.5M fanout writes/sec peak (post-carve-out)
  ÷ ~50k writes/sec/worker = ~70 workers; 3x headroom + mid-tier
  burst = ~250 workers, sharded by author_id with per-author rate
  limit so a single mid-tier burst can't starve others.
- **Threshold as a knob:** A/B against fanout-lag p99 and feed-load
  p99; lower if fanout-lag breaches, raise if feed-load breaches.
- **Migration when an author crosses 1M:** dual-write 24h → flip
  reads → GC fanout entries. Bidirectional (sheds → reverse).

**Anti-signal packet quote:** *"Acknowledged the celebrity problem but
did not commit to a threshold or size the fanout worker pool. On the
80M-follower curveball, did not articulate which followers see
staleness or for how long."*

### Deep dive B — Ranking pipeline

**Question:** *"You said it's ranked. Where does ranking happen, what
features, where do they live?"*

**Strong L5 answer:** two-stage candidate-gen → ranker. Features:
recency, author affinity, engagement. Mentions a feature store. Ranks
at read time because features are fresher. Picks a tree/linear model.

**Strong L6 answer adds:**
- **Feature freshness budgets:** static (author trust, follower bucket)
  hourly in KV; near-real-time (post 5-min engagement) every 30s via
  streaming aggregator; request-time (session, time of day) bound at
  request.
- **Cost per query:** ~1000 candidates × tree ensemble batched/vectorized
  → p99 80ms per feed load. At 2M feed loads/sec peak → ranker fleet
  of ~5k cores.
- **Separates policy filter** (NSFW, blocked, recently-seen dedup)
  from scoring; policy is a fast pre-filter on the candidate set.
- **Pre-rank-at-fanout vs score-at-read** split: cheap features bake
  into the feed entry; expensive features score at request.
- **Evolution:** linear/tree today → two-tower + transformer reranker
  in 12 months, candidate-set 500 → 5000, ~10x query cost. Ranking
  becomes the cost dominator.

**Anti-signal packet quote:** *"Named ranking but did not separate
candidate-gen from scoring, did not size serving cost, did not
articulate feature freshness. Stayed at vocabulary level."*

### Deep dive C — Caching & feed materialization

**Question:** *"The feed cache — what's in it, how big per user, who
writes, what evicts, what if a user returns after a month?"*

**Strong L5 answer:** per-user list of recent post IDs (pointers, not
payloads); LRU on active set; fanout writer is producer; cold-start
rebuilds from the follow graph on demand.

**Strong L6 answer adds:**
- **Size math:** ~500 post_ids × ~50 bytes = ~25KB/user. 100M active
  users × 25KB = ~2.5TB. Memcache fleet ~50 nodes × 64GB.
- **Active-user gating:** don't fanout to users idle >30d; rebuild on
  return. Cuts steady-state fanout ~40%.
- **Cache stampede protection:** per-user singleflight on rebuild +
  negative cache, so returning cohorts don't N-amplify the post-store.
- **Write-through:** fanout writer write-throughs to cache; post-store
  is source of truth.
- **No cross-region replication of cache** — we tolerate per-region
  cold rebuild within the 60s budget.

**Anti-signal packet quote:** *"Named Redis as a feed cache but did
not size per-user footprint, did not describe eviction, did not
address returning inactive users. Cache was a label, not a design."*

---

## 5. Watch-outs / common traps

### Candidate traps

- **Picks one fan-out and stays.** Pure-write ignores celebrities;
  pure-read ignores active users with hundreds of follows.
- **Names the celebrity problem but waves at the threshold.** "Do
  something different" without a number, math, or migration path —
  the most common L5/L6 separator miss.
- **Ignores ranking.** Strict reverse-chrono in 2026 is outdated.
- **"Redis" without sizing.** Exposed instantly by *what's in it,
  how big, who writes, what evicts?*
- **Vague freshness SLO.** "Reasonably fresh" sizes nothing.
- **Cache invalidation as an afterthought.** "Invalidate on write"
  hides stampede + thundering-herd modes.
- **Forgets cost.** L6 must say "$X/mo, hybrid trades to $X/2."
- **Designs only steady-state.** No story for celebrity bursts,
  region failure, queue backup.

### Interviewer traps

- **Letting "feed service handles that" stand.** Push once: *"what's
  inside?"*
- **Not forcing a celebrity threshold number.** *"At what follower
  count, and why that count?"* — must be asked if not volunteered,
  or the packet has no signal on hybrid judgment.
- **Tipping the answer by naming "hybrid".** Ask *"how does this break
  for users with millions of followers?"* — never *"have you
  considered a hybrid?"* That contamination kills committee signal.
- **Letting "we'd use ML" stand** without features, latency, fleet.
- **Spending too long on ingestion.** Redirect at 15 min: *"assume
  post-write is normal — what happens after it lands?"*

---

## 6. The golden answer (what a strong L6 candidate would produce)

Specific, numeric, opinionated, self-narrated. Not "the right answer"
— an *internally consistent* answer that defends every decision.

### Functional requirements

In scope: post (text + media ref), follow/unfollow, view feed
(paginated), engagement-weighted ranking, basic engagement (like,
comment, repost — counted, not detailed).

Explicitly cut at minute 5: DMs, search, notification delivery, ad
insertion (modeled as a parallel candidate-gen stream merged at
ranking time), cold-start non-follow recommendations, monetization.

### Non-functional requirements (with numbers)

Assumptions, stated as assumptions:

| Dimension | Value | Why this number |
|---|---|---|
| DAU | 200M | A Twitter-scale platform; not Meta/YouTube-scale |
| Posts per user per day | avg 1.0, p99 50 | Skewed; most users lurk |
| Posts/day | ~200M | DAU × posts/user |
| Posts/sec peak (10x avg) | ~25k | Used to size post ingest |
| Read:write ratio | ~100:1 | Standard for read-dominated feeds |
| Feed loads/sec peak | ~2M | DAU × ~10 loads/day, with 10x peak |
| Median follower count | ~150 | Long tail |
| p99 follower count | ~50k | |
| Max follower count | ~100M | Top celebrity |
| **Fanout writes/sec peak (pure-write model)** | **~20M** | Posts × avg-followers, peak — sizes the fanout fleet |
| p99 feed load latency | < 200ms | Mobile-acceptable |
| **Freshness SLO — normal poster** | **p99 < 5s post-to-visible** | Sizes fanout workers + queue |
| **Freshness SLO — celebrity** | **p99 < 60s post-to-visible** | Sizes the read-time merge TTL |
| Availability | 99.95% on read path; 99.9% on write | Reads are user-facing; write failures retry |

### Capacity estimation

- **Post ingest:** 25k/sec peak — trivial; ~100-instance write service.
- **Fanout writes** (the pressure point): 200M posts × ~150 avg
  followers (post celebrity carve-out) = 30B writes/day = ~350k/sec
  avg, ~3.5M/sec peak. *Without* the carve-out: ~20M/sec peak.
  Hybrid cuts ~6x and removes the worst-case spikes.
- **Materialized feeds:** 200M × 500 IDs × 50B = ~5TB — Memcache fleet.
- **Post store:** 200M × 365 × 1KB ≈ 73TB/year — Bigtable.
- **Follow graph:** ~50B edges × 20B = ~1TB.

**Math drove the decision:** pure write-fanout is sustainable on
average but celebrity bursts of 50-100M writes/second exceed any
reasonable static fleet. That's what forces the hybrid.

### Data model

- **Posts (Bigtable):** row key = post_id (Snowflake: ts ‖ shard ‖ seq,
  64 bits); cols: author_id, created_at, body, media_refs, policy_flags.
  Sharded by post_id prefix.
- **Follow graph (Spanner):** two tables — `follows(follower, followee)`
  and `followers(followee, follower)`, denormalized bidirectionally.
  Spanner for transactional follow/unfollow and strong consistency.
  Celebrity rows: sharded follower-count counter; fanout writer skips
  materialized follower lists above threshold.
- **Feed cache (Memcache):** `feed:{user_id}` → sorted list of ~500
  (post_id, baseline_score) tuples. LRU on activity; idle >30d evicted.
- **Feature store (Bigtable + hot cache):** static (author trust,
  follower bucket) hourly; per-post engagement every 30s via streaming
  aggregator; request-time features bind on the read path.

### API design

```
POST   /v1/posts                          → { post_id }
GET    /v1/users/{id}/feed?cursor=...&limit=20
                                          → { items: [...], next_cursor }
POST   /v1/users/{id}/follow/{target_id}
DELETE /v1/users/{id}/follow/{target_id}
POST   /v1/posts/{id}/engage              → { type: like|repost|... }
```

- Auth via short-lived bearer token; rate-limited per user.
- Pagination via opaque cursor (post_id + score offset), not
  page-number — feeds are unbounded.

### High-level architecture

```
  client → API gw (auth, rate-limit)
              │
   ┌──────────┼──────────────┐
   │          │              │
POST /posts  GET /feed   POST /follow
   │          │              │
 Post Svc   Feed Svc    Follow Svc
   │          │              │
 Bigtable   Ranker      Spanner
 + Pub/Sub  (cand-gen   (follow graph)
   │        + scorer)
   │        ┌────┴────┐
   ▼        │         │
 Fanout    Feed     Celebrity-merge
 workers   Cache    (read-time pull
 (only     (Mem-     for followees
  authors  cache)    > 1M followers)
  < 1M)
```

Fanout workers consume post-created Pub/Sub and write into Feed Cache
for sub-1M authors. Ranker reads Feed Cache + Celebrity-merge +
Feature Store on every feed load.

### The fan-out decision (the L6 separator)

**Decision:** hybrid, threshold at **1M followers**.

**Why hybrid:** pure write-fanout costs ~20M writes/sec peak and
celebrity bursts (50-100M in seconds) exceed any static fleet sizing,
violating the 5s SLO. Pure read-fanout costs ~300M follow-fetches/sec
peak (2M feed loads × ~150 follows) — over budget on both latency
and cost. Hybrid wins both sides.

**Why 1M:** at 1M followers, per-author worker-saturation cost equals
amortized read-merge cost (most users follow <10 celebs, so ~10 extra
read-time fetches per feed load — within 200ms p99, especially with a
hot celebrity-timeline cache). Above 1M, pull wins; below, push wins.
Treat as a knob: tune monthly against fanout-lag p99 and feed-load p99.
If fanout-lag breaches, lower; if feed-load breaches, raise.

**Worker sizing:** 3.5M writes/sec peak ÷ 50k/sec/worker = ~70 workers;
3x headroom + mid-tier burst capacity → ~250 workers. Sharded by
author_id with per-author rate limit.

**Migration when an author crosses 1M:** dual-write 24h → flip reads →
GC fanout entries. Bidirectional on follower shed.

### Ranking pipeline

Two-stage at request time: **candidate-gen (~10ms) → scorer (~80ms) →
policy filter (~5ms)**.

- Candidate-gen: pull pre-fanned feed (~500) + per-followed-celebrity
  recent window (~50 each, ~5-10 celebs) → ~1000 merged, deduped vs
  recently-shown.
- Scorer: tree ensemble, vectorized batch over ~1000 candidates.
  Features split across freshness tiers: request-time (recency,
  session), 30s cache (engagement velocity), 1h cache (author
  affinity). 80ms p99 × 2M loads/sec = ~5k cores. 12-month evolution:
  two-tower + transformer reranker, ~10x cost; ranking becomes the
  bill dominator.
- Policy filter: NSFW, blocked, muted, already-seen.
- Return top 20 + next cursor.

### Caching strategy

- **Feed cache (Memcache):** ~500 IDs × 50B = 25KB/user × 100M
  active = ~2.5TB; fleet ~50 × 64GB, sharded by user_id. Fanout
  writer is sole producer; reads never mutate. LRU on activity;
  idle >30d evicted, rebuilt on return via singleflight.
- **Celebrity timeline cache:** small (~500MB), hot, replicated.
- **Post payload cache:** ~1GB for top ~1M posts, read-through
  against Bigtable.
- **Stampede protection:** singleflight on rebuilds, negative cache
  on misses, tail-load shedding at >80% util.

### Storage defense (in one paragraph)

Posts → **Bigtable** (append-heavy, time-sortable, single-row
atomicity enough; Spanner is 3-5x more expensive per QPS). Follow
graph → **Spanner** (transactional follow/unfollow, strong consistency
on follower-count, bidirectional; we eat ~3x storage cost vs Bigtable
because it saves reconciliation pipelines). Feed cache → **Memcache**
(tiny, hot, rebuildable, no durability needed). Engagement events →
**Pub/Sub → BigQuery + streaming aggregator** (stream for real-time
features; warehouse for offline ML training).

### Multi-region

- Posts/follows: writes home-roomed by author/follower; async global
  replication ~1s. LWW for follows, monotonic IDs for posts.
- Feed cache: per-region, not replicated. Roaming users hit cold
  rebuild — covered by the 60s budget.
- Fanout writers: per-region, subscribed to a global post-created
  Pub/Sub topic.
- Reads: from nearest region. Budget: p99 60s cross-region for
  celebrity content; p99 5s in-region for normal content.

### Celebrity problem (explicit)

Handled by the hybrid: authors >1M never push, posts pulled via the
celebrity-timeline cache; per-author rate limit on fanout writer
prevents mid-tier starvation; reader dedups cache + merge.
**Runbook:** if a single author's fanout breaches SLO, a per-author
circuit breaker forces them onto read-merge until queue recovers —
the threshold is dynamically follower-count *or* queue pressure.

### Spam / abuse

Per-user post-rate limit (token bucket, ~100/day); NSFW + policy
classifier on write path (flagged → shadow-banned, invisible in
fanout); coordinated-inauthentic-behavior detection offline on
engagement stream; low author-trust depresses ranking score
without removing from feed.

### Cost (order of magnitude, $/month)

Post Bigtable ~$10k · Spanner follow-graph ~$30k · Memcache feed
~$15k · Fanout fleet ~$10k · **Ranker fleet ~$200k** · Features +
streaming ~$50k · Egress + misc ~$30k. **Total ~$350k/mo.**

**Cost decision to defend:** ranking is the bill dominator at $200k.
Worth it because A/B on session length almost always justifies it at
this scale.

### Failure modes & blast radius

| Failure | Blast radius | Mitigation |
|---|---|---|
| Fanout workers behind | Mid-tier author followers see >5s staleness | Auto-scale, per-author throttle, temp-promote to merge path |
| Feed cache node loss | ~2% users hit cold-start for ~30s | Singleflight rebuild; transient |
| Spanner regional outage | Follow/unfollow down in region; feeds still serve from cache | Read-only mode; queue follow writes |
| Ranker fleet failure | Recency-only ordering (candidate-gen still works) | Graceful degradation by design |
| Pub/Sub backlog | All fanout lags | Shed inactive followers first; page on-call |
| Celebrity event spike | Single-author queue spike | Per-author circuit breaker → forced read-merge |

**Rollback:** every component independently rollback-able. Ranker
models go behind a feature flag with 48h shadow before flip; kill
switch reverts.

### Evolution

- **2x (400M DAU):** nothing structural. Fleets double, storage
  linear. Threshold may shift to 500k.
- **10x (2B DAU):** pure-write breaks for mid-tier as average-author
  bursts saturate shards. Push threshold to 100k, accept more
  read-merge. Ranker dominates cost; move to GPU serving.
- **100x:** no longer a single system. Split by geographic region
  with cross-region as federation; sparse cross-region merge for
  international follows. The per-region Memcache + fanout seams we
  build today exist *because* of this projected evolution.

### Brownfield migration to hybrid

Identify top-N celebrity accounts → dual-write (push + index into
merge path) → A/B reads (1% → 100% via merged path) → stop fanout
for those accounts → GC. ~6 weeks, ~1.5 engineer-quarters.

---

## 7. Signals scorecard

| Signal | Hire / Strong Hire (packet quote) | No Hire / Downlevel (packet quote) |
|---|---|---|
| **Requirements & numbers** | *"Committed to 200M DAU, 100:1 R:W, 200ms p99, two-tier freshness SLO by min 7, unprompted."* | *"Did not commit to scale; used 'highly scalable' as a substitute."* |
| **Capacity math** | *"Derived ~20M peak fanout writes/sec, named it as the pressure point, used it to justify hybrid."* | *"Math floated unconnected to design."* |
| **Fan-out decision** | *"Volunteered hybrid by min 22. Defended 1M threshold with math; named migration path."* | *"Picked one strategy and stopped; when pressed, redesigned ad hoc; no threshold or worker sizing."* |
| **Ranking** | *"Separated candidate-gen from scoring; named feature freshness tiers; sized ranker fleet against QPS; evolution path to heavier model."* | *"'Use ML' with no features, latency, or fleet. Vocabulary-level."* |
| **Caching** | *"Sized per-user footprint (~25KB), fleet (~50 nodes), eviction (LRU + 30d gate), stampede protection."* | *"'Redis' without sizing, eviction, or cold-start."* |
| **Operational** | *"Volunteered per-author rate limit, circuit breaker, graceful ranker degradation, model rollback story — unprompted."* | *"Ops as a min-55 footnote. No blast radius, no rollback."* |
| **Evolution** | *"On 10x: identified worker-saturation crossover, lowered threshold, named what wouldn't change. Had a runbook for the celeb-burst curveball."* | *"On 10x: proposed redesign. On curveball: 'scale up the workers.'"* |
| **Cost** | *"Estimated ~$350k/mo, identified ranking as dominator, defended spend."* | *"Did not address cost; treated compute as free."* |
| **Drive & narration** | *"Narrated plan twice, named what they'd cut, volunteered deep-dive list at min 24, ran own clock."* | *"Asked 'is this the right direction?' more than once; surprised at 5-min call."* |
| **Calibrated disagreement** | *"Held Spanner choice with sharpened reason; conceded threshold would shift at 10x and named the new value."* | *"Caved on every pushback OR dug in defensively. No middle gear."* |
| **Bottom line** | **Strong Hire L6** | **No Hire** or **Downlevel to L5** by count of failing rows |

---

*Bench-mark: a strong L6 produces ~70% of the golden answer in the
hour, with the rest sketched or named as "I'd cover X with more time."
100% in an hour is exceptional; the round is intentionally ~20%
over-scoped so prioritization is itself a scored signal. A clean,
internally consistent 50% delivered at L5 depth is the textbook
downlevel case.*
