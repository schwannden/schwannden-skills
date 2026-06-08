# Question 3: Real-Time Top-K / Trending Hashtags

> Interviewer's guide + golden answer. Streaming/real-time anchor for the loop.
> Voice: L7 Senior Staff running an L5/L6 round. Calibration against Hello
> Interview's Top-K problem breakdown, Flink/Beam canonical semantics, and
> the streaming-systems literature (Cormode-Muthukrishnan CMS, Metwally-
> Agrawal-El Abbadi Space-Saving, MillWheel/Dataflow papers).

---

## 1. Why this question (interviewer's framing)

This is the cleanest **streaming-systems fundamentals** test in the canon.
Unlike chat (which leaks into connection management) or feed (which leaks
into ranking), top-K trending forces the candidate to live inside the
streaming model for the full hour: events arrive, time progresses, state
grows unboundedly unless you do something smart, and the output is a
continuously-updated derived view. Nowhere to hide.

Five things this tests that nothing else tests as well:

1. **Windowing semantics** — tumbling vs sliding vs session; event time vs
   processing time. A surprising number of L5 candidates can't say the words.
2. **Watermarks and late data** — when does a window close? What about the
   event 11 seconds after the watermark passed? Highest-signal area; strong
   L6s volunteer an allowed-lateness number unprompted.
3. **Approximate algorithms** — name CMS / Space-Saving / HyperLogLog and
   reason about ε/δ tradeoffs, or defend exact counting with memory math.
   Not knowing the option exists is a packet-quotable miss.
4. **Hot-key handling** — trending *is* the hot-key problem. A candidate who
   partitions by hashtag and doesn't notice `#worldcup` lands on one worker
   is ringing the L5 alarm bell.
5. **Exactly-once vs at-least-once for derived state** — does
   double-counting a hashtag matter? Does the candidate *say so* and pick the
   cheaper guarantee? L6 cost-discipline signal.

### L5 vs L6 bar

**L5 Hire** looks like: picks a windowing strategy (tumbling, 1 minute) with
a one-sentence reason, names Kafka + Flink + Redis, identifies hot-key risk
when prompted, gives correct napkin math, mentions "we'd checkpoint state for
fault tolerance," doesn't say anything embarrassing about watermarks.

**L6 Hire** requires all of the above plus: (a) explicit sliding-window
choice with named size **and slide** **and allowed-lateness number**, with
the tradeoff against tumbling articulated; (b) names Count-Min Sketch with
ε and δ, or defends exact counting with memory math; (c) volunteers a
hot-key strategy (salting, two-stage aggregation) *before I ask*; (d)
defends at-least-once for the count path with a specific argument about
why the duplicate cost is bounded; (e) talks about per-region trending
and the merge problem; (f) names a cost number.

**Classic downlevel traps** (each has sunk L6 candidates in front of me):

- **"Kafka + Spark Streaming"** with no windowing semantics — pipeline-shape
  thinking, not stream-processing thinking.
- **Ignoring late events.** "Once the window closes, we output." When does it
  close? Silent on watermarks.
- **Not knowing what Count-Min Sketch is.** Defensible if they reason through
  exact counting and the math works — but most don't know the option exists.
- **Never naming a window strategy.** Just "we count over time." No Hire at L6.
- **"Real-time" as a vibe.** Commit to a number — 30s, 5s, sub-second; each
  is a different system.

---

## 2. The 60-minute plan

### 0–5 min: Intro

**Say:** "Senior Staff on a streaming team. I'll give you a deliberately
under-specified prompt and I want you to drive. I'll answer clarifying
questions but won't volunteer constraints."

Then: *"Design a real-time trending hashtags pipeline — pick a product
(Twitter trends, YouTube trending, Spotify top songs)."*

**Listening for:** do they pick a product fast and start scoping? Either
choice is fine. **Push back if** they spend >90s picking — that's
indecision, not clarification.

### 5–15 min: Requirements & scope

**Say:** Mostly silent. Crisp answers when asked. Hard data on demand:
~500M DAU, peak 100K events/sec global, K=50, "trends update within a
minute," p99 < 100ms reads.

**Listening for:**

- "What window?" *(critical)* — if not asked, I feed: "what does
  'trending' mean to you, over what time horizon?"
- "Global or per-region?" *(L6 marker)*
- "Freshness SLO?" *(L5 minimum)*
- K? Smoothing / EWMA / rate-of-change? *(L6 bonus — trending is a delta)*

**Push back if** they say "low latency" without a number or "billions of
events" without per-second math. **Stay quiet** if they're stating
assumptions out loud and labeling them.

### 15–25 min: Estimation + high-level streaming architecture

**Say:** "Let's see the picture."

**Listening for** a box-and-arrow with at minimum: ingest tier → durable
log (Kafka/Pub-Sub with explicit partitioning key) → stream processor
(Flink, Beam-on-Dataflow, Kafka Streams) → windowed aggregation with
state → serving store (Redis-shaped) → history store (Bigtable/BigQuery).
Bonus if they draw windowing as its own logical stage, not "the Flink job
does it."

**Push back if** they draw request/response with a DB in the middle —
that's batch. Ask: "If a hashtag spikes 10x in 5s, when do users see it?"

### 25–45 min: Deep dives

**Mandatory:** windowing semantics + approximate counting. **Likely seconds:**
hot-key shuffle, exactly-once. Pick order from what they volunteered — if
they named CMS already I go hot-key first; if they're hand-wavy on windows I
push windowing.

- *Windowing:* tumbling vs sliding, why sliding for trending, specific size
  and slide, allowed-lateness named, behavior past the deadline (drop?
  side-output? downstream recompute?).
- *Approximate counting:* CMS with ε and δ, or a memory argument for exact.
  Bonus: Space-Saving / heavy-hitters and why CMS+heap beats pure CMS.
- *Hot-key:* two-stage aggregation or key salting. Either works — I want the
  *symptom* (skew → worker OOM → checkpoint timeout → pipeline lag).
- *Exactly-once:* I want them to *not* default-pick it. Right answer:
  at-least-once is fine for trending — relative ranking is what matters,
  and Kafka redelivery duplicates are bounded. If they say "we need
  exactly-once" I push back hard.

### 45–55 min: Evolution / failures

Throw 2, depending on coverage:

- *"Pipeline lags by 10 minutes. What do you see, what do you do?"* —
  watermark stall, checkpoint stall, hot-key OOM, which?
- *"`#worldcup` is now 30% of traffic. What breaks first?"* — worker OOM →
  checkpoint timeout → watermark stall.
- *"A bug double-counts for an hour. Recovery?"* — replay from Kafka offsets
  with new pipeline version; version-tag the results store.
- *"How does this become global multi-region?"* — per-region streams +
  cross-region merge; consistency story.
- *"10x traffic tomorrow. What changes?"* — partitions up, sketch dimensions
  up, salt cardinality up; re-window? probably not.

**Listening for:** L6 triages to the right component fast. L5 redesigns
instead of diagnoses.

### 55–60 min: Wrap

Candidate questions, still scoring. Best closing question I ever got on
this problem: *"What does your team actually do when the watermark stalls
— runbook, or manual advance?"* That's an engineer who's been on call.

---

## 3. Probing prompts (the kit)

| # | Prompt | Why I ask | Signal I'm hunting |
|---|---|---|---|
| 1 | *"What is 'trending' to you? Raw counts? Velocity?"* | Forces a product-shaped definition before architecture | Strong candidates name velocity / rate-of-change; weaker ones never separate "popular" from "trending" |
| 2 | *"K=10, 100, 1000 — does the design change?"* | Tests whether they understand that K affects state size and the heap structure | L6 says "K=10 fits a heap per partition; K=10K means we keep more state but the algorithm is the same" |
| 3 | *"Per-region or global trends?"* | The merge problem is real | L6 names a two-tier (per-region stream + global merge) without me having to prompt for it |
| 4 | *"Events per second? Distinct keys per window?"* | Forces capacity math | Anyone serious commits within 60s |
| 5 | *"Tumbling, sliding, or session windows?"* | Vocabulary test | L5 picks one; L6 picks sliding-by-30s with a stated reason about freshness |
| 6 | *"What's your allowed lateness?"* | The L5/L6 separator on streaming | L6 gives a number (e.g., 10s) and what happens past it (drop to side output) |
| 7 | *"Are you counting exactly, or estimating?"* | Opens the sketch door | If they name CMS with ε/δ unprompted that's a quotable L6 moment |
| 8 | *"What if `#worldcup` is 30% of traffic?"* | Hot-key | Two-stage aggregation or salting — anything else is L5- |
| 9 | *"Do you need exactly-once?"* | Cost discipline | Right answer is no for the count path, with reasoning |
| 10 | *"Where does the top-K live for the read path?"* | Serving | Redis sorted set, refreshed every N seconds; p99 budget worked out |
| 11 | *"What's your p99 read budget?"* | Forces serving design | <100ms means it's a cached pre-computed view, not a query |
| 12 | *"Pipeline breaks for an hour. Recovery?"* | Replay story | Reset Kafka offsets, version the result store, swap on completion |
| 13 | *"How do you stop a bot army from making `#buyMyCoin` trend?"* | Spam / abuse | L6 names per-user rate cap + diversity-of-source filter + (later) ML score |
| 14 | *"What does this cost per month?"* | L6 marker | Anyone who quotes a dollar number is showing ops maturity |
| 15 | *"10x traffic. What changes first?"* | Evolution | Partitions, sketch dimensions, salt cardinality — in that order |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

### Deep dive A: Windowing semantics and late data

**Phrasing:** *"Walk me through what window you're using, when it closes, and
what happens to events that arrive after it closes. Be specific."*

**L5 answer shape:** "Tumbling 1-minute windows, we close at the end of the
window and emit results. Late events — I guess we drop them?" Acceptable but
flat. They know what a window is but haven't internalized event-time vs
processing-time.

**L6 answer shape:** "Sliding window, 5 minutes wide, sliding every 30
seconds — 5-minute trending with 30s freshness cadence. Event time, not
processing time, because clients can buffer on the producer side and a
connectivity blip shouldn't distort trends. Watermark is heuristic — p99
of `now() - event_time` over the last minute, probably ~10s. Allowed
lateness 10s on top, so events up to 20s late still update the window via
Flink's late-firing trigger. Past 20s they go to a side-output topic for
batch backfill into the history store only. Watermark lag and
side-output rate are my primary SLIs — if either spikes the pipeline is
sick."

**What's different at L6:** sliding-by-X with both numbers; allowed
lateness as a number; *side output* not "drop"; named SLI on watermark
lag. Sounds like someone who has operated a Beam/Flink pipeline.

**Anti-signal:** "Processing-time tumbling, it's simpler." Defensible only
if they name what's lost (skew under ingest backpressure) and why this
product absorbs it.

**Packet quote (Hire):** *"Chose event-time sliding 5min/30s with
watermark heuristic and 10s allowed lateness; named side-output for
past-lateness events; cited watermark lag as primary SLI."*

**Packet quote (No Hire):** *"On late data, candidate said 'we'd drop
them' and could not distinguish event time from processing time."*

### Deep dive B: Approximate counting

**Phrasing:** *"How big is your state at peak? Walk me through the memory."*
(Then if they go exact — *"What if K were 1000 and we wanted ten of these
trending views at once?"*)

**L5 answer shape:** "We keep a hashmap per partition, key→count. At
100K events/sec × 60s × ~16 bytes per entry, the memory is maybe a few
hundred MB per worker, that's fine." Honest, correct at this scale, doesn't
demonstrate awareness of the sketch option.

**L6 answer shape:** "Count-Min Sketch, width=2718 (e/ε for ε=0.001),
depth=5 (ln(1/δ) for δ=0.01) — ~13K counters per partition, kilobytes
of memory, per-key error bounded by ε·N. CMS overestimates, only. Pair
with a Space-Saving heap of top ~500 — CMS gives 'is this key plausibly
heavy', Space-Saving gives 'here are the K heavy hitters with bounded
displacement error.' I keep 500 not 50 so the heap can absorb CMS
misranks at the boundary. Real reason I want sketches even at this scale:
I want *many* of these queries — per region, per language, per category —
without linear-in-views memory. Sketches make the cross-product affordable."

**What's different at L6:** named both CMS and Space-Saving and why you
pair them; gave ε and δ; explained the over-provisioned heap; reasoned
about the cross-product problem.

**Anti-signal:** "HyperLogLog." HLL counts *distinct elements*, not
*frequency of elements*. If they conflate, push: "Walk me through how HLL
tells you the top hashtag." Failure to self-correct is a strong No Hire.

**Packet quote (Hire):** *"Named CMS (ε=0.001, δ=0.01) paired with
Space-Saving heap of size 500; explained the pairing and the
over-provisioning. When asked about HLL, explicitly distinguished
frequency from cardinality."*

### Deep dive C: Hot-key skew

**Phrasing:** *"Walk me through what happens during the World Cup final
when `#goal` is 40% of all traffic."*

**L5 answer shape:** "We'd partition by hashtag, so... oh, that means one
worker gets all the `#goal` events. We could partition by user instead."
Identifies the problem post-prompt; partial recovery.

**L6 answer shape:** "Partitioning by hashtag is naive — `#goal` lands on
one worker and we get checkpoint timeouts within minutes. Two-stage
aggregation: stage one keys by `(hashtag, salt)` where salt is 0..15 for
general traffic, dynamic up to 256 for known-hot keys. Each salted worker
keeps a CMS + heap. Stage two keys by `hashtag` only and merges. CMS
merges additively — element-wise sum of the counter arrays — which is
the algebraic reason this works. Space-Saving heaps merge by union plus
prune. Identify known-hot keys with a Misra-Gries detector at stage one
and dynamically widen the salt. Cost is doubled inter-stage bandwidth —
worth it. Blast radius without salting: hot key → worker OOM →
checkpoint fail → watermark stalls → entire pipeline lags. With salting,
worst case is 1/16 of one key on one worker — well within headroom."

**What's different at L6:** explicit two-stage shuffle; CMS-additive-merge
named as the algebraic reason; dynamic salt cardinality; blast radius
walked OOM → checkpoint → watermark → lag.

**Anti-signal:** "Give that worker more memory." Postponement, not a fix;
ask "and next time it's 10x bigger?"

**Packet quote (Hire):** *"Volunteered two-stage salted aggregation with
CMS additive merge before I asked about hot-key. Walked the blast radius
through OOM → checkpoint timeout → watermark stall."*

---

## 5. Watch-outs / common traps

### Candidate traps

- **"Kafka + Spark Streaming, done."** Pipeline-shape, not stream-shape. Push:
  "What is the unit of computation here?"
- **No watermark.** Press until they say "watermark" or "processing time"; if
  the latter, ask what happens on a 30s ingest delay.
- **Defaulting to exactly-once.** Costs 2-3x in throughput and ops complexity.
  Right answer for trending is at-least-once. Ask: "What does that buy here?"
- **Exact counting where sketches are right.** Defensible at low scale,
  indefensible across a cross-product (per-region × per-language × per-category).
- **"Real-time means every second."** Force a number.
- **Redis-sorted-set as the only store.** Fine for current top-K — but
  history? Replay? Push toward a serving + history split.

### Interviewer traps (for me)

- **Letting them stay in pipeline-shape.** If 25 minutes in they haven't said
  "watermark" or "window," push. Otherwise I fail them by writing "candidate
  did not discuss streaming semantics" — true, but my fault.
- **Accepting "we'd use CMS" with no parameters.** Many know the word. The
  signal is the ε/δ math, not the word.
- **Letting them skip cost.** Streaming compute is 5-10x batch per event.
- **Over-grilling on algorithm internals.** Describing what CMS does and its
  tradeoffs is enough; I don't need them to re-derive hash function bounds.

---

## 6. The golden answer (what a strong L6 candidate would produce)

What follows is what a hire-band L6 candidate sounds like across 60 minutes.
Not a transcript — a synthesis of what the packet write-up could quote.

### Functional requirements (minute 5)

> "Twitter-style trending hashtags. Functional:
>
> 1. Rank top K hashtags by *trending score* over a rolling window, per
>    region (and globally).
> 2. Freshness ≤ 30s end-to-end.
> 3. Read API with p99 < 100ms.
> 4. 30 days of history for replay and analytics.
>
> I'm separating *trending* from *popular*. Popular is raw count; trending
> is rate-of-change — `100/min → 10K/min` should rank above stable
> `50K/min`. Start with raw count per window and layer a velocity score."

### Non-functional requirements (minute 7)

> "Numbers, stated as assumptions:
>
> - 500M DAU, avg 1 hashtagged event/day → ~6K/sec avg, peak ~100K/sec.
> - Distinct hashtags/5-min window: ~5M (long tail is huge).
> - K = 50 displayed; compute top-500 internally for stability.
> - Window: 5 min, sliding 30s. Allowed lateness: 10s.
> - Freshness SLO: 30s ingest → top-K update.
> - Availability 99.9% for serving (pipeline can lag — serve last-known-good).
> - Cost target: <$100K/month for the streaming tier."

### Capacity estimation (minute 9)

> "100K events/sec × ~200 B = 20 MB/s = 1.7 TB/day ingest. Kafka with 6h
> retention → ~430 GB on disk, easy. Distinct keys/window: 5M. Naive
> exact state at 24 B/entry → 120 MB/window per partition, × 10 panes
> (5min/30s) ≈ 1.2 GB per partition. CMS: width 2718, depth 5, 4-byte
> counters = ~55 KB per pane, plus a 500-entry heap ~12 KB. Total ~700 KB
> per partition. Four orders of magnitude smaller — load-bearing when I
> multiply by (regions × languages × categories)."

### API (minute 11)

```
GET /trending?region={r}&category={c}&k={k}&window={w}
  → 200 [{hashtag, score, rank, sample_volume}]
GET /trending/history?region={r}&from={t1}&to={t2}&granularity=5m
  → 200 paginated time-series of top-K snapshots
```

> "Auth via service token; the public API would proxy through a separate
> service that rate-limits and filters by viewer's content prefs. K capped
> at 200 to bound response size."

### High-level architecture (minute 15)

```
       clients
          |
          v
   [ingest API] -- bot-score, rate-limit per user --> drop / accept
          |
          v
   Pub/Sub  (or Kafka)   <-- 256 partitions, key=(hashtag, salt)
          |
          v
+-------------------------------+
|  Dataflow / Flink streaming   |
|                               |
|  stage 1: partial top-K       |
|   - sliding 5min/30s, EvtTime |
|   - watermark + 10s lateness  |
|   - CMS(2718, 5) per pane     |
|   - SpaceSaving heap (top-500)|
|                               |
|  stage 2: global merge        |
|   - key by hashtag only       |
|   - merge CMS additively      |
|   - merge heaps, prune        |
|   - compute velocity score    |
+-------------------------------+
          |
          v
   results writer
          |
     +----+--------+
     v             v
 Redis sorted   Bigtable
 set (current   (history,
 top-K, TTL)    snapshots)
          |
          v
   serving API (read-through cache, edge)
```

> "Two stages because of hot-key skew (deep dive below). State in Flink
> managed/RocksDB, checkpointed to GCS every 30s. Results writer is
> idempotent on `(window_end, region, rank)` — no exactly-once needed
> upstream."

### Windowing decision (minute 19)

> "Sliding 5min / 30s. Tumbling gives either coarse freshness (5min) or
> tiny noisy windows (30s rankings bounce wildly). Sliding gives smooth
> continuous updates with stable rankings. Event time, heuristic
> watermark: p99 of `now() - event_time` over the last 60s — set
> watermark at `now - p99_skew`. Allowed lateness 10s past watermark,
> Flink late-firing trigger updates the window. Past 20s total
> lateness → side-output topic, flushed to Bigtable for offline
> reconciliation only; never retroactively edits live top-K. Watermark
> lag is my primary SLI; alert if > 60s for 2+ minutes."

### Approximate counting decision (minute 24)

> "CMS with ε=0.001, δ=0.01: width = ⌈e/ε⌉ = 2718, depth = ⌈ln(1/δ)⌉
> = 5. Error: estimate within ε·N of true with probability ≥ 1−δ. At
> 30M events/window, ε·N ≈ 30K — fine for top-K where the cutoff is
> in the millions; noise on the long tail which I don't rank anyway.
>
> CMS alone can't give top-K (you'd query every key). Pair it with a
> Space-Saving heap of size 500 (Metwally–Agrawal–El Abbadi 2005):
> bounded displacement error guarantees any item with true frequency >
> N/m is in the heap. With m=500 and N=30M, anything above 60K
> events is tracked — well below where K=50 lives.
>
> I keep 500 not 50 so the heap absorbs CMS overestimate noise at the
> boundary; final top-50 is re-ranked from CMS estimates at output."

### Hot-key strategy (minute 30)

> "Naive partition-by-hashtag breaks: `#goal` at 30-40% of volume OOMs
> one worker. Two-stage aggregation:
>
> Stage 1 keys by `(hashtag, salt)`. Salt = 0..15 default; dynamically
> widened to 0..255 for keys exceeding ~5% of partition traffic.
> Misra-Gries sketch alongside CMS detects hot keys cheaply (sub-MB).
> Stage 1 emits partial CMS + heap every pane (30s).
>
> Stage 2 keys by `hashtag` only, merges. CMS merges *additively* —
> element-wise sum of counter arrays — the structural reason this works.
> Heaps merge by union, prune to top 500. Velocity score computed here:
> `score = count + α·(count − prev_window_count)`, α ≈ 2.
>
> Blast radius without salting: hot key → worker OOM → checkpoint
> timeout → Flink can't snapshot → watermark stalls → all regions
> degrade. With salting, worst case is 1/16 of one key on one worker."

### Exactly-once vs at-least-once (minute 36)

> "At-least-once on the count path. (a) Trending is *ranking* — relative
> scores matter, not absolute, and duplicates shift counts roughly
> uniformly so K=50 rankings are stable. (b) Kafka redelivery dupes are
> bounded (sub-second window), well below per-item CMS noise. (c)
> Exactly-once in Flink roughly halves throughput because of
> 2-phase-commit sinks and longer checkpoint barriers.
>
> The *output* path is effectively exactly-once via idempotent writes
> keyed on `(window_end, region, rank)` — Redis and Bigtable see one row
> per window even if Flink redelivers. Standard pattern: at-least-once
> internal, idempotent external."

### State storage (minute 40)

> "Three tiers:
>
> - **In-stream:** Flink managed state, RocksDB-backed, off-heap. Incremental
>   checkpoints to GCS every 30s. Disk small because CMS + heap is small.
> - **Current top-K:** Redis / Memorystore. Sorted set per `(region,
>   category)`, hashtag → score. TTL 10min so stale partitions self-clean.
>   Read p99 1ms.
> - **History:** Bigtable, rowkey `(region, reverse_ts, category)`, one row
>   per window-end with top-500 as a proto. 30-day TTL → BigQuery export."

### Serving (minute 44)

> "Read path is precomputed top-K, dead simple. Edge cache (CDN or
> memcached at API layer) with 10s TTL absorbs millions of concurrent
> readers while respecting freshness. On miss, ZRANGEBYSCORE Redis. p99
> budget: edge hit ≈ 10ms RTT; edge miss → Redis ≈ 5ms + 30ms RTT.
> p99 target 100ms — comfortable tail headroom."

### Multi-region (minute 46)

> "Per-region pipelines: regional Pub/Sub → regional Dataflow → regional
> Redis. Trends are inherently regional. For *global*, a stage-3 job
> consumes regional partial-CMSes and heaps from a global topic and
> produces a merged view — CMS associativity makes this clean. Global
> freshness coarser (60s) because we wait for all regions' panes."

### Spam / bot defense (minute 48)

> "Three layers:
>
> 1. **Producer-side rate caps:** ≤5/min per-user-per-hashtag at ingest.
>    Kills obvious amplification.
> 2. **Diversity-of-source filter:** HyperLogLog per hashtag in stage 1
>    (correct use of HLL — cardinality, not frequency). Hashtag eligible
>    only if distinct users ≥ threshold.
> 3. **Async ML bot-score:** weight events by `1 − bot_probability(user)`,
>    score consumed from a separate team's feature pipeline. Seam is
>    clean; we accept lag on the bot signal."

### Cost (minute 51)

> "Rough monthly:
>
> - Pub/Sub: ~$2K (1.7 TB/day × 30 × $0.04/GB).
> - Dataflow/Flink: ~$10K (~50 workers × n2-standard-8). Streaming is
>   2-3× batch per event.
> - Redis HA: ~$2K. Bigtable 3-node: ~$3K. Egress + monitoring: ~$2K.
> - **~$20K/month/region, ~$60K/month for three regions.** Under my
>   $100K target; mostly streaming compute."

### Failure modes & blast radius (minute 53)

> | Mode | Symptom | Blast | Recovery |
> |---|---|---|---|
> | Watermark stall | freshness lag grows | one region | manual watermark advance via side-input; RCA the source |
> | Hot-key OOM | worker restart loop | one partition | dynamic salt expansion; force redistribute |
> | Checkpoint failure | can't snapshot | full replay on recovery | shorter checkpoint, more GCS bandwidth |
> | Kafka lag | events queue up | global ingest delay | scale partitions/consumers |
> | Redis unavailable | top-K stale | reads degrade gracefully | failover replica; pipeline catches up |
> | Bad deploy | wrong counts | rankings drift | version the results store; swap to prev |
>
> "Single most useful runbook: on watermark lag > 60s, diagnose hot key
> (CPU pegged on one worker), checkpoint (slow GCS), or ingest
> backpressure (Kafka consumer lag). Each has a different fix."

### Evolution (minute 56)

> 1. **10x events/sec.** Partitions 256 → 2048; salt cap 256 → 1024.
>    CMS dimensions: since error grows linearly with N, loosen ε → 0.0001
>    and accept bigger sketches. Same shape, roughly 10× cost.
> 2. **Global cross-region.** Already designed; interesting wrinkle is
>    *consistency* under partition — I'd serve stale-but-flagged with a
>    `last_updated` timestamp.
> 3. **ML-ranked trending.** Replace velocity score with a GBDT ranker on
>    volume, velocity, diversity-of-source, novelty, user-interest
>    embedding similarity. Drift is real (sports-finals day suppresses
>    legitimate trends if trained on yesterday) — run champion-challenger
>    with bounded divergence from the rule-based ranker as a safety net."

---

## 7. Signals scorecard

| Lean-in (packet-quotable Hire) | Lean-back (packet-quotable No Hire) |
|---|---|
| "Sliding window, 5min wide, sliding every 30s, event-time, watermark heuristic at p99 of `now() - event_time`, allowed lateness 10s, side-output past lateness" | "We'll use a windowed aggregation" (no size, no slide, no lateness, no time-semantic) |
| "Count-Min Sketch ε=0.001 δ=0.01, paired with Space-Saving heap of size 500 to absorb misranks" | "We'd use some kind of sketch" or "we'd use HyperLogLog for the top-K" (conflates cardinality and frequency) |
| "Two-stage salted aggregation; CMS merges additively which is the algebraic reason this works; blast radius walked through OOM → checkpoint → watermark stall" | "We'd partition by hashtag" and never notices the skew problem |
| "At-least-once on count path, exactly-once on output via idempotent writer keyed on (window_end, region, rank); justified by ranking-invariance to bounded duplicates" | Defaults to exactly-once everywhere, can't articulate the cost |
| "Per-region pipelines + global merge job; CMS associativity lets us merge cross-region cleanly; global view has coarser 60s freshness" | "We'd run it everywhere" with no merge or consistency story |
| "Spam: per-user rate cap + HyperLogLog diversity-of-source filter + async bot-score from separate ML pipeline" | Doesn't mention spam, or proposes a 'we'd filter bots' with no mechanism |
| Walks the blast radius end-to-end: hot key → worker OOM → checkpoint timeout → watermark stall → pipeline lag → user-visible | Treats failures as 'we'd add retries and monitoring' |
| Cites a dollar number per month and where it's spent | Treats compute as free |
| Volunteers velocity ≠ popularity unprompted | Counts raw frequencies and calls that 'trending' |
| Names operational SLI: watermark lag, side-output rate, checkpoint duration, partition lag | Names only RED metrics (rate, errors, duration) — no streaming-specific SLI |
| Drives the deep-dive ordering: "I want to do windowing first, then hot-key, because hot-key only makes sense once we agree on the window" | Waits for me to pick the deep-dive each time |
| "10x traffic: partitions up, salt up, ε looser. Same shape, more boxes." | Redesigns from scratch on the 10x prompt |

---

## Sources & references

- Hello Interview, *Top-K Problem Breakdown* —
  hellointerview.com/learn/system-design/problem-breakdowns/top-k
- Cormode & Muthukrishnan (2005), *An Improved Data Stream Summary: The
  Count-Min Sketch and its Applications* — the canonical CMS reference;
  ε/δ derivation, width = e/ε, depth = ln(1/δ).
- Metwally, Agrawal, El Abbadi (2005), *Efficient Computation of Frequent
  and Top-k Elements in Data Streams* — Space-Saving algorithm, the
  natural CMS pair for top-K.
- Akidau et al. (2013/2015), *MillWheel* and the *Dataflow Model* papers
  — event time, watermarks, triggers, allowed lateness as
  first-class concepts.
- Apache Flink docs, *Windows + Allowed Lateness + Side Outputs* —
  nightlies.apache.org/flink/flink-docs-master/docs/dev/datastream/operators/windows
- Apache Beam, *Windowing* — beam.apache.org/documentation/programming-guide/#windowing
- Misra & Gries (1982), *Finding Repeated Elements* — the older heavy-hitters
  algorithm; useful for L6 candidates who want a third lever.
- Cormode (encyclopedia entry), *Count-Min Sketch* —
  dimacs.rutgers.edu/~graham/pubs/papers/cmencyc.pdf
