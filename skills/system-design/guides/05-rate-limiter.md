# Question 5: Distributed Rate Limiter / Quota Service

*Interviewer-side preparation pack for a 1-hour Google L5/L6 system design
round. The candidate prompt is deliberately vague: "Design a distributed
rate-limiter / quota service for a multi-tenant API platform."*

This is the **operational / multi-tenant** anchor in the rotation. It is the
single best L5/L6 separator in the canonical set because every load-bearing
question — sync vs async, fail-open vs fail-closed, hot tenants, per-region
vs global enforcement, cost — has a clean L5 answer that is *wrong at L6
scale*. The room is essentially watching whether the candidate produces a
textbook Redis-INCR answer or a real production design.

---

## 1. Why this question (interviewer's framing)

Rate limiting *looks* shallow. A prepared L4 can recite the five
canonical algorithms and stop. Algorithm comparison is table stakes;
it is **not the question being asked**. The real question is: *given a
multi-tenant API platform where the rate-limit check sits in the hot
path of every request, what do you commit to, and what happens when
your committed design fails?*

That forces explicit reasoning on five axes:

- **Correctness vs availability.** A perfectly accurate global limiter
  takes ~5ms of central RTT per request and dies with the store. A
  perfectly available limiter is a local bucket that drifts. The
  interesting work is in between.
- **Fail-open vs fail-closed.** The L6 fork. Doorman's design note is
  explicit — a managed service should fail open so the limiter can't
  take down the protected service. But "always fail open" is also
  wrong on billing-sensitive endpoints. The L6 answer is **per-endpoint
  policy with blast-radius reasoning**.
- **Hot tenants.** Traffic is a power law; whales are 1000x the median.
  Naive designs hot-shard on them.
- **Per-tenant fairness.** Not just isolation — weighted fairness
  across SKU tiers.
- **Multi-region.** Global quotas without cross-region RTT is a real
  constraint with a real answer (per-region budgets + periodic
  rebalance + bounded overshoot).

**L5 vs L6 bar.**

- **L5 Hire**: picks an algorithm, defends numerically, names Redis,
  identifies the check as hot path, knows hot-tenant risk exists,
  reasons about failure when asked.
- **L6 Hire**: all of the above, *plus* unprompted commit to a
  **sync/async hybrid with named staleness budget** (e.g. 200ms
  refresh, ≤5% per-tenant per-minute overshoot), *plus* a
  **per-endpoint fail-open/fail-closed policy with blast-radius**,
  *plus* a **multi-region budget-allocation story**, *plus* at least
  one cost argument in dollars-or-shards.

**Classic downlevel traps.** "Redis INCR with TTL" and stop —
modal L5→L4 answer; fail-closed-everywhere — makes the limiter a
SPOF for the protected service; ignoring hot tenants — collapses
under one follow-up; single-region when "multi-tenant API platform"
was in the prompt; proposing sliding-window-log seriously at scale.

---

## 2. The 60-minute plan

Minute-by-minute. What you'll say, what you're listening for, what
would make you push back vs stay quiet.

### 0–5 min — Intro

**Say:** "Hi, I'm $X. Tell me about yourself. Then I'd like you to
design a distributed rate limiter or quota service for a multi-
tenant API platform — think Cloud APIs, Stripe-style limits, or
an internal service mesh. Take it wherever you think it should go."

**Listen for** whether the candidate sits with the ambiguity vs
launching into "I'll use Redis with token bucket" before clarifying
scope. Restating the problem in their own words is an L6 tell.
**Stay quiet** — this is their space.

### 5–15 min — Requirements and scope

**Listen for** the candidate to volunteer: which limits (per-API-key,
per-endpoint, per-IP, tuples), burst vs sustained, SKU tiers, hard
vs soft cap, refund-on-failure semantics, propagation SLA, and hard
numbers (target QPS, distinct keys, p99 budget).

**Numbers to provide when asked**: 1M req/s peak; ~10M active keys;
≤2ms p99 check; limiter availability ≥ protected service; quota
propagation <60s.

**Push back** if they commit to "high QPS" or "low latency" without
numbers — quote them back at minute 30 if they do. Push back if
they don't distinguish burst from sustained ("1000 req/s sustained
vs 1000 req/s avg-over-a-minute pick different algorithms"). Stay
quiet while they're enumerating.

### 15–25 min — Estimation + algorithm + high-level architecture

**Listen for** numbers that change a design decision (not "we have
1M QPS" in the abstract); algorithm commit with defense
(sliding-window-counter or token bucket, defended on memory and
boundary-spike grounds); an architecture with at least
client → gateway → local cache → central store + admin plane. **If
the local cache is missing, the design is L5-ceiling and the room
knows it.**

**Push back** on sliding-window-log without memory cost ("how much
memory per tenant?"); on single Redis without sharding ("what's the
QPS to that one Redis?"). Stay quiet when commits are crisp.

### 25–45 min — Deep dives (the diagnostic zone)

Two **mandatory** dives:

1. **Sync vs async with local cache + fail-open.** Ask: *"Walk me
   through every request. Is the check synchronous with central?"*
2. **Hot tenants.** Ask: *"One tenant is 80% of traffic. What
   changes?"*

Third dive — pick based on weakness — usually multi-region or
per-tenant fairness across SKU tiers.

**Listen for at L6**: named staleness budget with specific numbers;
per-endpoint fail-open/fail-closed policy with blast radius; whale
isolation via dedicated shards / larger local allocations and a
per-tier overshoot budget.

**Push back hard** on "Redis Cluster handles it" ("p99 under
sustained 1M QPS with hot keys? What about Redis failover?"). Push
back on universal fail-open ("billing endpoints?"). Stay quiet on
specifics + trade-offs.

### 45–55 min — Evolution and failures

The rate-limiter outage scenario is **mandatory**. Drive to it:

> *"Your central counter store has a region-wide outage for 10
> minutes. Walk me through what happens minute by minute."*

**Listen for** specific blast-radius reasoning ("read endpoints fail
open, audit log captures, post-hoc reconciliation invoices egregious
overuse; billing endpoints fail closed because dollar-loss"); the
recovery path (local counters during outage are not authoritative,
reconciliation is approximate); cost reasoning (hybrid ~10x cheaper
than centralized — defensible).

Curveball if time: *"AI inference endpoints — each request costs
different compute. Token bucket has uniform-cost tokens. What
changes?"* (Answer: `cost(request)` tokens per call; algorithm
unchanged, API generalizes.)

### 55–60 min — Wrap

Hard stop. ~3 min for candidate questions. Still scoring — "how
does the on-call rotation look?" reads differently from "how fast
can I get promoted?"

---

## 3. Probing prompts (the kit)

~14 prompts you can drop at any point. For each: *why you'd ask*
and *what signal you're hunting*.

| # | Prompt | Signal you're hunting |
|---|---|---|
| 1 | "Hard cap or soft cap? What happens at the limit?" | Distinguishes reject vs degrade vs queue; L6 picks per-endpoint. |
| 2 | "Per-API-key, per-endpoint, per-IP — which do you support and how do they compose?" | Recognizes AND-composition over tuple keys, not a flat keyspace. |
| 3 | "Burst vs sustained — different limits or same?" | Picks an algorithm *because of* burst characteristics, not recall. |
| 4 | "Walk me through your algorithm choice. Why not the other three?" | Names memory cost of log, boundary-spike of fixed window. |
| 5 | "At 1M QPS, what's the central store doing?" | Realizes single Redis is hot-keyed and needs sharding *and* a client-side tier. |
| 6 | "Is the limit check synchronous with central?" | "Yes" = L5 ceiling. "No — local cache with periodic refill, staleness budget X" = L6. |
| 7 | "What's the staleness budget? How bounded is overshoot?" | Defensible number with derivation. |
| 8 | "One tenant is 80% of traffic. What changes?" | Dedicated shards / larger local allocations for whales. |
| 9 | "Central store dies. Walk me through what happens." | Per-endpoint fail-open/fail-closed; audit log + reconciliation. |
| 10 | "Global limit or per-region?" | Per-region budgets with rebalance; quantified cross-region overshoot. |
| 11 | "How fast does a quota change propagate?" | Admin plane separate from data plane; pub-sub or pull-with-versioning. |
| 12 | "Two tenants on the same plan, both hammering. How don't they starve each other?" | Weighted FQ or strict per-key budgets, not "sharding will balance it." |
| 13 | "What does your monitoring page look like day-1 after launch?" | Burn rate + limit-hit rate + false-positive tracking. |
| 14 | "What does this cost per year at 1M QPS?" | Hybrid ~10x cheaper than centralized with one-line napkin. |
| 15 | "AI inference — each request costs different compute. What changes?" | Cost-weighted `cost(request)` tokens; trivial API change. |

---

## 4. Where to dig deeper

Pick **2–3** of these. Below: phrasing, L5 vs L6 answer shape,
anti-signal, packet quote you'd love to write.

### Deep dive A — Sync vs async with local cache, plus fail-open

**Phrasing.** *"Walk me through the path a single request. Is the
check synchronous with central?"*

**L5 shape.** Each gateway calls (sharded) Redis with atomic INCR
or Lua token bucket. Sub-2ms. Redis failure is "we fail open" or
"fail closed" — named, not analyzed. Competent L5 answer.

**L6 shape.** Hybrid (full design in §6.7). Hot path = in-process
bucket only; 200ms background loop reconciles with central.
Staleness ≤200ms; overshoot bounded by
`instances × local_bucket_size`, sized to ≤5% of quota. Outage
default = fail-open + audit log; per-endpoint override flags
billing endpoints fail-closed. May cite Doorman as prior art.

**Anti-signal.** "Just Redis with a Lua script" — has not separated
hot path from coordination path, which is the entire point.

**Packet quote.**
> *"Proposed hybrid local+central with named 200ms staleness budget
> and explicit overshoot bound. On central outage, fail-open default
> + fail-closed per-endpoint for billing, citing blast-radius cost.
> Unprompted on both."*

### Deep dive B — Hot tenants

**Phrasing.** *"One tenant — Acme — is 80% of platform traffic.
What changes?"*

**L5 shape.** "Shard Acme onto dedicated Redis" or "scale the
cluster." Recognizes the problem; solution is mechanical.

**L6 shape.** Tier-based (full design in §6.8): whales get larger
*local* allocations per instance (so their hot path almost never
touches central) *and* dedicated central shards (so a whale burst
can't bleed into tail p99) *and* tighter contractual overshoot
(≤1% vs ≤10% for tail). Strong L6 adds: tier promotion is
data-driven (hourly job on observed traffic), not contract-driven,
because sales' "small customer" lags real QPS.

**Anti-signal.** "Redis will handle it" with no isolation story.

**Packet quote.**
> *"Three-tier response — larger local allocations for whales,
> dedicated central shards above 1% traffic, per-tier overshoot
> budgets. Noted tier promotion should be data-driven because
> customer growth lags sales categorization. Unprompted."*

### Deep dive C — Multi-region

**Phrasing.** *"Global limit or per-region? What does it cost?"*

**L5 shape.** "Per-region limits summing to global." Right shape,
vague math.

**L6 shape** (full design in §6.10): per-region budgets proportional
to *observed* traffic with 30s rebalance; cross-region overshoot
bounded by `traffic_shift × rebalance_interval` and quantified;
strict-global endpoints (billing, fraud) carved out to a single
authoritative region accepting cross-region RTT; region failure →
reapportionment on next rebalance.

**Anti-signal.** "One global Redis" with cross-continental RTT on
hot path; or independent regional limits with no rebalance.

**Packet quote.**
> *"Per-region budgets proportional to observed traffic with 30s
> rebalance, overshoot explicitly bounded at (shift × interval),
> strict-global endpoints carved out. Reasoned about region-failure
> reapportionment unprompted."*

---

## 5. Watch-outs / common traps

### Candidate-side traps (anti-signals)

- **Single Redis, no failover story.** No mention of Cluster,
  Sentinel, replication lag, primary failure. Down-level.
- **Algorithm-comparison without a commit.** Recites four
  algorithms, picks none. Packet: "listed textbook options without
  committing" — Hello Interview's *performing knowledge* anti-signal.
- **Sliding-window-log at scale.** 1M req/s × 60s × 16B ≈ 1GB per
  tenant per minute. Fine to mention, not to commit.
- **No per-tenant key strategy.** Flat keyspace collapses on the
  hot-tenant follow-up.
- **Fail-closed without blast-radius reasoning.** Makes the limiter
  a SPOF for the protected platform. Quotable mistake.
- **Monitoring as afterthought.** "We'd add dashboards" at minute
  55. At L6, burn-rate-per-tenant belongs in the design at minute 30.
- **No cost reasoning.** Treats compute and central-store QPS as
  free. L6 owes at least one dollar-or-shards argument for why
  hybrid beats centralized.

### Interviewer-side traps (your own)

- **Letting them stay in algorithm-comparison textbook territory.**
  Easy to nod along. Don't. By minute 20 force the commit: *"Which
  are you using? Why?"*
- **Not driving to the outage scenario.** It's mandatory. If
  unprompted by minute 45, push.
- **Leading the candidate to the hybrid design.** Tempting because
  it's the right answer. Don't. If they don't get there alone,
  that's a finding — the packet won't write convincingly if you
  handed it to them.
- **Over-rewarding name-drops.** "We'd use Doorman" is not a
  signal. "We'd use Doorman because we need cooperating clients
  apportioning a shared global budget" *is*. Test the depth.

---

## 6. The golden answer (what a strong L6 candidate would produce)

A complete walk-through at L6 quality. ~25-30 minutes of speaking
time when delivered well.

### 6.1 Functional requirements

- Enforce limits across multiple axes: per-API-key, per-endpoint,
  per-IP, per-(tenant, endpoint) tuples — composed with AND.
- Burst + sustained per limit (token-bucket shape: capacity =
  burst, refill rate = sustained).
- Multiple SKU plan tiers; per-tenant plan assignment.
- Read-your-quota API; burn-rate alerts.
- Admin plane: quota changes propagate end-to-end in <60s.
- Per-endpoint fail-open vs fail-closed policy.

### 6.2 Non-functional requirements

- **Target QPS** 1M req/s peak; **active keys** ~10M.
- **p99 of limit check (hot path)** ≤2ms; target ≤500µs.
- **Limiter availability** ≥ protected platform (≥99.95%) — must
  not be a SPOF.
- **Staleness budget** ≤500ms (200ms refresh target).
- **Cross-instance overshoot** ≤5% per tenant per minute.
- **Config propagation** <60s p99.

### 6.3 Capacity estimation

- **Central counter state.** 10M keys × 128 bytes × 3-way
  replication ≈ 4GB per shard set — trivial.
- **Central QPS, naive (sync on every request).** 1M req/s ×
  1 RTT = 1M QPS to central, hot-keyed by whales. Untenable on a
  single primary; requires sharding *and* a client-side tier.
- **Central QPS, hybrid.** Each instance refills every 200ms =
  5 refills/sec/instance. At ~10K instances, ~50K QPS to central
  — **20x reduction**. Each refill batches all keys the instance
  saw; effective rate is lower.
- **In-process cache per instance.** ≤100K active keys × 128
  bytes ≈ 13MB. Comfortable.

### 6.4 API surface

```
checkAndConsume(key, cost=1) → {allowed: bool, retryAfterMs: int, remaining: int}
   - key = (tenantId, apiKeyId, endpoint, ip?) tuple, canonicalized
   - cost = number of tokens to consume (1 for simple, N for cost-weighted, e.g. AI tokens)
   - hot path; local-only when local bucket has tokens

getQuota(key) → {limit: int, remaining: int, refillRate: float, planTier: string}
   - tenant-facing read-your-quota
   - eventually consistent (≤500ms)

admin.setQuota(key, plan, overrides?) → {versionId: string}
   - admin plane, writes to durable store, triggers propagation
   - 60s SLA to data plane
```

### 6.5 High-level architecture

```
  Admin Plane ─► Durable Quota DB (Spanner) ─► Config Distributor ──┐
                                                                    │ pub-sub
                                                                    ▼
  Client ──► API Gateway / Sidecar ─── 200ms refill RPC ──► Central Counter Store
                  ├ Local Bucket Cache (RAM)                (sharded Redis-like)
                  └ Decision Log ──► Audit Log Stream  (for fail-open reconciliation)
```

Three planes, deliberately separated:

1. **Data plane** (hot): API gateway with local bucket cache.
   Sub-ms decisions.
2. **Coordination plane** (warm): central counter store, reached
   async ~every 200ms per instance.
3. **Control plane** (cold): admin writes to Spanner (global
   consistency on plan changes); Config Distributor pushes to data
   plane via pub-sub.

### 6.6 Algorithm: sliding-window-counter (or token bucket)

**Pick:** sliding-window-counter for sustained rates; token bucket
for burst-plus-sustained (which the prompt asked for).

- **Not sliding-window-log:** at 1M req/s with 1-min window =
  ~60M timestamps per tenant. Dies on memory.
- **Not fixed-window:** boundary spike — a 1000 req/min quota
  allows 2000 across two adjacent seconds.
- **Sliding-window-counter / token bucket:** O(1) per key. SWC
  linearly weights prev-window count against current-window
  partial; token bucket is the same shape (capacity + refill rate
  + last-refill ts). Stripe, GitHub, Cloudflare, AWS all run
  variants of these — consensus production answer.

### 6.7 Sync vs async hybrid (the heart of the design)

The hot path **does not** synchronously call central.

**Local state per instance.** In-memory map: `key →
LocalBucket(allocation, remaining, last_refill_at)`. On
`checkAndConsume(key, cost)`:

1. Cold miss → fetch initial allocation from central (~1ms).
2. `remaining >= cost` → decrement, return `allowed=true`.
   Sub-µs in process.
3. `remaining < cost` → sync probe central (~1ms) to see if
   global budget allows a top-up, else return `allowed=false`.

**Background reconciliation every 200ms.** Each instance batches a
report of `(key, consumed, remaining)` for active keys, receives a
refreshed allocation per key proportional to its recent traffic
share (Doorman's apportionment idea), atomically swaps in local
map.

**Bounded overshoot.** Worst-case cross-instance overshoot per key
= `local_allocation_size × instances_holding_key`. Sized so each
instance holds ≤ `quota × (refresh_interval / 60s) ≈ quota × 0.003`
per refresh → ≤5% global overshoot per tenant per minute.

### 6.8 Hot-tenant strategy

Three tiers, data-driven promotion (hourly re-evaluation):

- **Whales** (>1% platform traffic): dedicated central shards,
  larger local allocations, ≤1% contractual overshoot.
- **Heavy** (0.01–1%): reserved hash-sharded pool, moderate local
  allocations.
- **Tail** (everyone else): general hash-sharded pool, smaller
  local allocations, ≤10% overshoot tolerated (absolute volumes
  are low).

Contracts can pin a tenant to a tier for predictability, but the
default is observed traffic — sales-driven tier assignment lags
real QPS.

### 6.9 Storage

- **Central counter store**: in-memory KV sharded by
  `hash(tenantId)`, 3-way intra-region replication, Lua scripts
  for atomic CAS-style updates.
- **Durable quota config**: Spanner globally — low write QPS, but
  admin writes ("tenant X → plan Y") must be globally agreed.
- **Audit log stream**: Kafka-shaped, ~30 days retention; the
  reconciliation substrate during fail-open windows.

### 6.10 Multi-region

- Global quotas **split into per-region budgets** proportional to
  observed traffic share; rebalance every **30s**.
- Cross-region overshoot bounded by `traffic_shift ×
  rebalance_interval`. Worst-case 50% sudden shift → 15s of
  mis-allocation.
- **Strict-global endpoints** (billing, fraud) use a single
  authoritative region; cross-region RTT cost absorbed for the
  ≤5% of traffic that needs it.
- **Region failure**: dead region's budget reapportioned to
  survivors on next rebalance.

### 6.11 Failure modes and fail-open vs fail-closed

The L6 commit: **per-endpoint policy, default fail-open with audit.**

| Endpoint class | Policy on limiter failure |
|---|---|
| Read APIs (default) | Fail open, audit-logged |
| Write APIs (non-billing) | Fail open with stricter audit + faster reconciliation |
| Billing-sensitive writes (charge endpoints, metered AI inference) | Fail closed — each request = dollars; <5% of traffic so blast bounded |
| Abuse/safety (auth, account creation) | Fail closed, with a tiny standalone in-process limiter as backstop |

**Blast-radius reasoning.** Default fail-open: protected API stays
up; audit log captures every served request; hourly reconciliation
computes actual overuse and either invoices, notifies, or tightens
local limits going forward. Bounded cost — a tenant on 1000 req/min
could do ≤60K unbilled requests during a 60-min outage; real but
recoverable. Fail-closed-everywhere makes the limiter a SPOF for
the entire platform — worse than the disease.

### 6.12 Per-tenant fairness

- Strict per-key budgets are the first line — every (tenant,
  endpoint) tuple has its own counter, no cross-tenant
  interference at the algorithm layer.
- For tenants on the same SKU plan competing for a *shared
  underlying resource* (e.g. database connections, GPU capacity),
  a second-layer weighted fair queue at the gateway prevents one
  tenant from monopolizing the resource even within their quota.
- Noisy-neighbor isolation: whale tenants are on dedicated
  shards (see 6.8) so their burst doesn't bleed into tail-tenant
  latency.

### 6.13 Config propagation

Admin writes to Spanner (source of truth, globally consistent). A
**Config Distributor** watches the change feed and publishes
deltas via pub-sub to all data-plane instances; each instance
atomically swaps its in-memory quota config table on receipt. SLA:
ACK-to-last-instance <60s p99, <10s p50. Configs are versioned;
data plane reports current version in heartbeats so admin knows
when propagation is complete.

### 6.14 Monitoring

Three classes, per-tenant and aggregate:

1. **Burn rate** — quota consumption velocity. Alerts at 80/95/100%.
2. **Limit-hit rate** — % throttled. Upsell *and* abuse signal.
3. **False-positive rate** — legitimate traffic blocked by local
   mis-allocation; compare decisions to post-hoc "true global
   state at that moment." Target <0.1%.

Plus standard ops: limiter p50/p99/p999 latency, central-store
saturation, per-shard QPS, fail-open events/min (alert if non-zero
for >5 min).

### 6.15 Cost

Naive sync-to-central: 1M QPS at managed-Redis pricing,
over-provisioned for hot keys. Hybrid: 50K QPS to central + cheap
in-process state. Same store shape, ~1/15 the cluster size after
headroom. **~10-15x cheaper** at 1M QPS. Defensible in one
paragraph; the ratio matters more than the absolute dollar figure.

### 6.16 Failure-mode recap

The point of the hybrid is that central is **not in the critical
path**:

- Central store dies → instances serve from local allocations →
  fail-open with audit (default) or fail-closed (billing).
- Gateway instance dies → its in-flight allocation is "lost" for
  ≤200ms, reapportioned on next refresh. Negligible.
- Region dies → budgets reapportioned among survivors on next 30s
  rebalance; one-interval of under-allocation in worst case.
- Config distributor dies → existing config keeps running; new
  changes don't propagate. Tolerable for minutes, not days.

### 6.17 Evolution

- **10x growth** (1M → 10M QPS): more central shards, larger
  fleet, possibly shorter refresh interval. Knobs change, not
  architecture.
- **Per-resource limits beyond per-API** (GPU-seconds,
  storage-bytes): `cost` parameter on `checkAndConsume`
  generalizes — request consumes `cost(request)` tokens. No
  algorithm change.
- **AI-API cost-weighted limits**: same shape; gateway estimates
  cost per request from model + token count.
- **Org seams**: admin plane is a natural team handoff — a quota-
  config team owns SKUs/admin; platform-infra owns data plane.

---

## 7. Signals scorecard

| Hire (quotable in packet) | Down-level / No-Hire (quotable in packet) |
|---|---|
| Committed to 1M QPS, ≤2ms p99, 200ms staleness budget unprompted by minute 10. | Hand-waved scale; never named a number unprompted. |
| Hybrid local-cache + central reconciliation with explicit overshoot bound (≤5% per tenant per minute). | Single Redis with sync INCR; no client-side tier; no overshoot reasoning. |
| Defended sliding-window-counter (or token bucket) on memory + boundary-spike grounds. | Listed four algorithms without committing; named one without defending it. |
| Per-endpoint fail-open/fail-closed policy with blast-radius reasoning + audit log. | "Always fail open" or "always fail closed"; treated outage as one binary decision. |
| Hot tenants: tier-based local allocation, dedicated shards for whales, data-driven tier promotion. | "Redis Cluster handles hot keys" with no isolation story. |
| Multi-region: per-region budgets proportional to observed traffic, 30s rebalance, bounded overshoot, strict-global carve-out. | One global Redis with cross-region RTT; or independent regional limits with no global enforcement story. |
| Cost trade-off: hybrid ~10x cheaper than centralized at 1M QPS, napkin defense. | Designed as if compute and central QPS were free. |
| Volunteered the outage scenario with named recovery path (audit log → post-hoc reconciliation). | Required interviewer to drive to outage, then proposed fail-closed-everywhere. |
| Monitoring: burn rate + limit-hit rate + false-positive tracking, named at minute 30. | "We'd add dashboards" at minute 55. |
| On 10x curveball, identified 2–3 knobs (shards, allocations, refresh interval) without redesigning. | Treated 10x as a redesign. |
| Per-tenant fairness: weighted FQ for shared downstream resources beyond the quota layer. | Treated fairness as solved by sharding. |
| Calibrated pushback: "I'd reconsider X if Y; for the steady state I described I'd keep this." | Capitulated immediately or dug in defensively without engaging. |
| Narrated time budget unprompted. | Surprised when interviewer flagged 10 minutes left. |

---

## Sources used in preparing this guide

- Hello Interview — *Design a Distributed Rate Limiter* (problem
  breakdown, algorithm comparison, hybrid architecture):
  hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter
- Stripe Engineering Blog — *Scaling your API with rate limiters*
  (token bucket in production, 4 limiter types, feature-flag
  rollout): stripe.com/blog/rate-limiters
- YouTube/Google — *Doorman: Global Distributed Client-Side Rate
  Limiting* (cooperating-clients model, fail-open as default for
  managed services): github.com/youtube/doorman/blob/master/doc/design.md
  and SREcon16 talk
- Practitioner aggregate: ByteByteGo "Design A Rate Limiter",
  System Design Handbook rate-limiter guide, Mockingly's
  interview-shaped breakdown
