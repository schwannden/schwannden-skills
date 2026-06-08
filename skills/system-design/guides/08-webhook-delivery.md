# Question 8: Webhook / Event-Delivery System (async fan-out, at-least-once, idempotency, DLQ)

> Interviewer's guide + golden answer. The **async event-delivery** anchor for
> the loop. Frame canonically around Stripe-style webhooks (or any generic
> event-delivery platform fanning events out to subscriber endpoints you do not
> control). Voice: L7 Senior Staff who has run hundreds of these rounds.
> Calibration against Hello Interview / System Design Handbook webhook
> breakdowns, the Stripe webhook spec, AWS SQS DLQ semantics, and the
> at-least-once / idempotency literature. Its calibration value is
> judgment-under-constraint — the network gives you nothing for free, the
> receiver is hostile/slow/buggy, and "exactly-once" is a fantasy you must
> talk the candidate out of.

---

## 1. Why this question (interviewer's framing)

Webhooks *look* like "POST a JSON body to a URL." They are not. The entire
difficulty is that **you are delivering to endpoints you don't own**: they
time out, they 500, they return 200 then crash before committing, they go
dark for three days, one of them is 90% of your fan-out and is slow. The
candidate who treats this as "an HTTP client with a retry loop" is telling
you they've never operated one.

Five things this tests that nothing else in the canon tests as cleanly:

1. **Delivery semantics under an unreliable receiver.** Exactly-once across a
   network is impossible; the honest answer is **at-least-once + receiver
   idempotency**. A candidate who promises exactly-once delivery has failed
   the question in one sentence.
2. **Idempotency as a *structural* property, not a footnote.** The strong move
   is a stable `event_id` the receiver dedupes on, *plus* a producer-stamped
   monotonic timestamp (`last_event_at`) so the receiver can do last-write-wins
   and safely *ignore* stale/out-of-order events. This is the load-bearing
   idea on the page.
3. **Retry / backoff / DLQ discipline.** A real retry schedule (numbers!),
   `maxReceiveCount`, jitter, and — critically — *which failures retry vs.
   which dead-letter on first encounter*. Bad schema dead-letters immediately;
   a stale event does not dead-letter at all, it logs-and-acks.
4. **Fan-out scale + per-subscriber fairness.** One event → N subscribers; a
   single slow/dead subscriber must not back up everyone else. Noisy-neighbor
   is the hot-key problem wearing a different costume.
5. **Event-driven sync is never complete without reconciliation.** The L6 tell
   is naming a **reconciliation cron as a required companion** to the event
   path — not an "and we'd also add monitoring" afterthought. Events are an
   optimization on top of a periodically-correct system, not a correctness
   guarantee by themselves.

### What "Hire" looks like at each level

**L5 Hire** looks like: states at-least-once + receiver idempotency on
`event_id` unprompted; draws producer → durable queue → delivery workers →
subscriber, with a DLQ; commits to a retry schedule with backoff and jitter
and a `maxReceiveCount`; returns 2xx-fast / process-async on the receiver
side; identifies that a slow subscriber is a problem when prompted; gives
correct fan-out napkin math; verifies signatures (HMAC) so endpoints can
trust the payload.

**L6 Hire** requires all of the above, **plus**: (a) volunteers the
**monotonic `last_event_at` last-write-wins** primitive as the *structural*
idempotency + ordering mechanism, and explicitly distinguishes the three
failure dispositions — **retry** (transient), **DLQ-on-first-encounter**
(schema/poison), **log-and-ack, never DLQ** (stale / out-of-order); (b)
designs the **multi-gate validation pipeline** (source allowlist → parse →
schema → freshness) and says *which gate routes where*; (c) volunteers
**per-subscriber isolation** (per-destination queues / partitioning + circuit
breaker + per-subscriber rate cap) before being asked about noisy neighbor;
(d) names the **reconciliation cron** as a required companion with a cadence
and a divergence metric; (e) commits to a cost number and a CAP stance
(AP on the delivery path, monotonic LWW for convergence).

### Classic downlevel traps

1. **Promising exactly-once delivery.** "We'll use a transactional outbox so
   it's exactly-once end-to-end." Outbox gives exactly-once *production*; the
   *delivery* hop to a third party is irreducibly at-least-once. Packet: "Did
   not understand that exactly-once across a network is impossible." No Hire.
2. **Idempotency as the receiver's problem only.** Saying "the subscriber
   should dedupe" and stopping. The platform must *supply* a stable
   `event_id` and a monotonic timestamp, or the receiver *can't* dedupe
   correctly. Half the answer.
3. **DLQ as a junk drawer.** Everything that fails N times goes to the DLQ,
   including stale events and transient blips. The DLQ fills with noise, the
   poison-message signal is lost, and on-call drowns. The disposition triage
   *is* the deep dive.
4. **One global queue.** A single delivery queue means one dead subscriber's
   backed-up retries delay everyone. The hot-key / noisy-neighbor follow-up
   collapses the design.
5. **Reconciliation as an afterthought.** "Events keep things in sync."
   Events drop, get reordered, and partition. Without a periodic
   reconciliation sweep the two systems silently diverge forever. At L6 this
   is a mandatory component, not a min-55 footnote.
6. **Sync delivery on the request path.** Doing the HTTP POST inside the API
   request that produced the event — couples your latency and availability to
   the subscriber's. Verify, enqueue, return 200 fast.

---

## 2. The 60-minute plan

Time-sliced against the canonical budget. For each slice: **Say** (verbatim),
**Listen for** (the signal), **Push back when** (trigger + line).

### 0–5 min — Intro & framing

**Say:** "Senior Staff on a platform team. I'll give you a deliberately
under-specified prompt and I want you to drive — I'll answer clarifying
questions but won't volunteer constraints. Design a webhook / event-delivery
system: we have internal events (say, payment / account-lifecycle events) and
we need to reliably deliver them to subscribers' HTTP endpoints — think Stripe
webhooks, or a generic event-delivery platform."

**Listen for:** do they restate the problem and name the hard part ("the
endpoints aren't ours, so reliability is the whole game") vs. jump to "POST
with a retry loop"? Restating + naming the delivery-to-untrusted-receiver
problem is an L6 tell.

**Push back when** they start drawing before scoping: "Hold on — what are we
actually promising the subscriber? That frames everything."

### 5–15 min — Requirements & scope

**Say:** mostly silent. Crisp numbers on demand: ~50K events/sec produced at
peak; average fan-out 5 subscribers/event (long tail to thousands for popular
event types); ~1M registered endpoints; delivery SLO "p99 < 5s under healthy
subscribers"; events retained/replayable for 3 days; payload ≤ 256 KB.

**Listen for:**

- "At-least-once or exactly-once?" → they should answer their *own* question:
  at-least-once + idempotency. *(critical)*
- "Ordered or unordered delivery?" *(L6 marker — forces the LWW conversation)*
- "Synchronous to the producer, or decoupled?" *(L5 minimum — must be async)*
- "What's a 'successful' delivery?" → 2xx within a timeout (e.g. 10s). *(L5)*
- "Do subscribers need to authenticate the payload?" → signing/HMAC. *(L5)*

**Push back when** they say "reliable" or "scalable" with no number — quote it
back at minute 30. Push back if they conflate "ordered" with "exactly-once":
"Those are different guarantees — which do you actually need?"

### 15–25 min — Capacity + high-level design

**Say:** "Let's see the picture and the napkin math."

**Listen for** a decoupled pipeline: producers → durable event log/queue →
**fan-out / dispatcher** (event → per-subscription delivery tasks) → durable
per-delivery queue → delivery workers (HTTP POST + retry) → DLQ. Plus a
delivery-attempt store for status/replay, and a subscription registry. The
**transport choice** should be justified: a pub/sub topic fanning out to
per-subscriber queues (SNS→SQS-shaped) with **raw message delivery** so the
subscriber's consumer gets the event body verbatim, not a broker envelope it
has to unwrap.

**Push back when** the fan-out happens synchronously inside the producer ("now
your checkout latency depends on 5 webhook POSTs"); when there's one global
delivery queue ("what happens when one endpoint is dead for an hour?"); when
there's no DLQ ("where does a payload that will *never* succeed go?").

### 25–45 min — Deep dives (the diagnostic zone)

Two **mandatory** dives, plus one chosen by weakness.

1. **Delivery semantics + idempotency + ordering.** Ask: *"A subscriber tells
   you they processed the same charge twice. Walk me through how that
   happens and how your system makes it safe."* This is where
   `event_id`-dedupe + monotonic `last_event_at` LWW must surface.
2. **Retries, backoff, DLQ, poison messages.** Ask: *"Give me the actual retry
   schedule. Then: what goes to the DLQ, and what never does?"* The
   three-way disposition triage is the L6 separator.

Third dive (pick from weakness): **fan-out fairness / noisy neighbor**
(*"one subscriber is 90% of your fan-out and is slow"*) — almost always worth
forcing if they haven't volunteered per-subscriber isolation.

**Listen for at L6:** stale-event → *log-and-ack, never DLQ*; schema-failure →
*DLQ on first encounter*; per-subscriber queue/partition + circuit breaker +
rate cap; reconciliation cron with a cadence.

**Push back hard** on "the DLQ catches everything" ("so a stale duplicate
pages on-call at 3am?"); on "we'd just retry forever" ("for three days against
a 410 Gone endpoint?").

### 45–55 min — Evolution / curveball

Throw 1–2 depending on coverage:

- *"Events and the subscriber's DB have drifted — they're missing a state
  change. How would you even know, and how do you fix it?"* → **reconciliation
  cron** + divergence metric. Mandatory if not yet covered.
- *"A subscriber endpoint has been returning 500 for 6 hours. What does your
  system look like right now?"* → circuit breaker open, their queue draining
  to DLQ or parked, *other* subscribers unaffected.
- *"10x the event rate overnight. What changes?"* → partitions up, worker
  fleet up; the per-subscriber isolation and LWW semantics don't change.
- *"Subscriber needs strict per-entity ordering. What do you give up?"* →
  partition by entity key, single in-flight per partition; you trade
  throughput and the failure of one event head-of-lines the rest.

**Listen for:** L6 triages to the changed seam fast and names what *doesn't*
change. L5 tends to redesign.

### 55–60 min — Wrap

Hard stop, ~3 min for candidate questions, still scoring. The best closing
question I've heard on this problem: *"When a subscriber's been down for a day
and comes back, does your team replay from the DLQ manually or is there an
automated redrive — and who owns that runbook?"* That's an engineer who's been
paged by a webhook backlog.

---

## 3. Probing prompts (the kit)

| # | Prompt | Signal hunted |
|---|---|---|
| 1 | "At-least-once or exactly-once? Defend it." | Names at-least-once + idempotency; rejects exactly-once-over-network as impossible. |
| 2 | "How does the *subscriber* dedupe? What do you give them to dedupe on?" | Platform supplies stable `event_id`; receiver keeps a processed-id set with a UNIQUE constraint. |
| 3 | "Two events for the same object arrive out of order. What happens?" | Monotonic `last_event_at` LWW — stale event is ignored, not applied. |
| 4 | "Give me the literal retry schedule." | Numbers + exponential backoff + jitter + a cap (e.g. 3 days), not "we retry a few times." |
| 5 | "What's your `maxReceiveCount`, and what happens on the Nth failure?" | A specific number (e.g. 5) and DLQ routing. |
| 6 | "What goes to the DLQ — and what *never* does?" | Schema/poison → DLQ first encounter; transient → retry; stale → log-and-ack. The triage. |
| 7 | "A payload fails to parse. Retry it?" | No — deterministic failure, DLQ immediately; retrying wastes attempts. |
| 8 | "One subscriber is 90% of fan-out and slow. What backs up?" | Per-subscriber queue/partition isolation; a global queue is the wrong answer. |
| 9 | "An endpoint 500s for 6 hours. What does the system do?" | Circuit breaker opens; back off; don't hammer; don't starve others. |
| 10 | "How do subscribers trust the payload came from you?" | HMAC-SHA256 signature over raw body + timestamp; constant-time compare; replay window. |
| 11 | "Events drop or reorder and the two systems drift. How do you catch it?" | Reconciliation cron + divergence metric; events alone don't guarantee convergence. |
| 12 | "Is the delivery POST on the producer's request path?" | Must be decoupled — verify, enqueue, 200 fast; producer latency independent of subscriber. |
| 13 | "Strict per-entity ordering — what do you give up?" | Partition by entity key, single in-flight; throughput + head-of-line blocking cost. |
| 14 | "Subscriber back after a day. Replay?" | DLQ redrive / replay-by-time-range; who owns the runbook. |
| 15 | "What does this cost per month, and what dominates?" | A dollar number; egress + queue ops + worker fleet, not "compute is free." |
| 16 | "10x event rate tomorrow. What changes vs. stays?" | Partitions + workers scale; LWW + isolation + DLQ semantics unchanged. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

Pick **2–3**. For each: phrasing, L5 vs L6 answer shape, anti-signal, packet
quote.

### Deep dive A — Delivery semantics, idempotency, and ordering

**Phrasing.** *"A subscriber says they processed the same charge twice — and
separately, they applied an old 'pending' state on top of a newer 'paid'
state. Walk me through how both happen and how your system makes each safe."*

**Strong L5 answer.** "At-least-once delivery, so duplicates are expected — a
worker can POST successfully, then crash before recording success, so we
redeliver. We give each event a stable `event_id` (UUID, assigned at
production, stable across retries). The subscriber stores processed
`event_id`s with a UNIQUE constraint and short-circuits before mutating state.
For ordering — Stripe-style — I'd tell subscribers to order by the event's
`created` timestamp and not assume arrival order." Correct, competent, covers
dedup. But ordering is offloaded to the subscriber as advice, not enforced as
a system property.

**Strong L6 answer.** "Two distinct problems, two mechanisms.

*Duplicates* → receiver idempotency keyed on `event_id`. The platform assigns
`event_id` once at production and it is stable across every retry and every
fan-out copy — so `(event_id, subscription_id)` is the natural idempotency
key. Receiver keeps a processed-key set (UNIQUE constraint, or a dedup table
with TTL ≥ our 3-day retry window). This is exactly-once *effect* on top of
at-least-once *delivery* — the only honest exactly-once there is.

*Out-of-order* → I make ordering a *structural* property with a **monotonic,
producer-stamped `last_event_at` timestamp** and **last-write-wins** on the
target entity. Every event carries `(entity_id, last_event_at)`. The consumer
applies an event only if `incoming.last_event_at > stored.last_event_at` for
that entity; otherwise the event is **stale or out-of-order, and it
degrades to log-and-ack — it is NOT an error and must NOT go to the DLQ.**
That's the subtle part: a reordered 'pending' arriving after 'paid' is a
*normal, expected* outcome of at-least-once + fan-out, so dropping it is
*correct convergence*, not a failure. LWW gives me convergence without
requiring global ordering, without a per-entity lock, and without
coordination — the stamp is monotonic because the producer is the single
writer of that entity's state, so its clock for that entity is monotonic by
construction. If two producers could write the same entity I'd need a
version/epoch instead of wall-clock, and I'd say so.

So: duplicate → idempotency drop; stale → LWW log-and-ack; genuinely new and
in-order → apply. Three outcomes, one of which (the stale one) most candidates
mistakenly route to the DLQ."

**What's different at L6:** separates duplicate from out-of-order as two
mechanisms; names monotonic `last_event_at` LWW as the *structural* ordering
primitive; explicitly says stale → log-and-ack, *never DLQ*; states the
single-writer assumption that makes the stamp monotonic and the fallback
(version/epoch) if it doesn't hold.

**Anti-signal.** "We'll use exactly-once delivery with a transactional
outbox." Outbox makes *production* exactly-once; the third-party hop is still
at-least-once. Or: "ordering is the subscriber's problem" with no
platform-supplied ordering token.

**Packet quote (Hire).**
> *"Separated dedup (stable event_id, receiver UNIQUE constraint) from
> ordering (monotonic producer-stamped last_event_at, last-write-wins).
> Volunteered that a stale/out-of-order event degrades to log-and-ack and
> must NOT go to the DLQ — 'that's correct convergence, not a failure.' Named
> the single-writer assumption and the version/epoch fallback. Unprompted."*

**Packet quote (No Hire).**
> *"Claimed exactly-once delivery via outbox; did not understand the
> third-party hop is irreducibly at-least-once. Offloaded all ordering to the
> subscriber."*

### Deep dive B — Retries, backoff, DLQ, and poison-message triage

**Phrasing.** *"Give me the literal retry schedule with numbers. Then tell me
exactly what goes to the DLQ — and what never does, no matter how many times
it 'fails.'"*

**Strong L5 answer.** "Exponential backoff with jitter. Something like:
immediate, then 30s, 2m, 10m, 1h, 5h, 12h, capped at ~3 days total, then give
up. On SQS I'd set a redrive policy with `maxReceiveCount` — say 5 — so after
5 receive attempts the message moves to the DLQ. The DLQ holds everything that
exhausted retries; on-call inspects it and can redrive. We alarm on DLQ
depth." Solid — real numbers, real DLQ mechanics, an alarm. What's missing is
the *disposition triage*: it treats every failure identically.

**Strong L6 answer.** "Schedule first, then the triage, because the triage is
the actual design.

*Schedule:* truncated exponential backoff with full jitter — base 10s,
doubling, capped at 12h per-attempt interval, total budget 3 days (matches
Stripe's window: roughly immediate, 5m, 30m, 2h, 5h, 10h, then every 12h).
Jitter is mandatory — without it, a broker hiccup that fails 100K deliveries
synchronizes their retries into a thundering herd against recovering
endpoints. `maxReceiveCount` on the per-subscriber queue is the backstop, but
I drive most backoff via `ChangeMessageVisibility` keyed on
`ApproximateReceiveCount` so the backoff curve is mine, not just the queue's.

*Triage — this is the part that matters.* Not every 'failure' is the same, and
routing them all to the DLQ is the classic mistake:

| Failure class | Example | Disposition |
|---|---|---|
| **Transient** | 503, timeout, connection reset, throttled | **Retry** with backoff; DLQ only after the 3-day budget / maxReceiveCount |
| **Poison / schema** | payload fails schema validation, unparseable body, signature won't verify | **DLQ on *first* encounter** — deterministic, retrying wastes the budget and can never succeed |
| **Stale / out-of-order** | `last_event_at` ≤ stored | **log-and-ack, NEVER DLQ** — this is correct convergence, not an error |
| **Permanent reject** | 410 Gone, endpoint deleted, 4 weeks of 404 | disable subscription, alert owner; don't DLQ-spam |

The insight: the DLQ is for *messages a human needs to look at* — poison
payloads, genuine permanent failures. If I dump stale events and transient
blips in there, the DLQ becomes noise, on-call stops trusting it, and a real
poison message hides in the pile. Schema-failures dead-letter immediately
*precisely because* they're deterministic — there is zero value in burning 3
days of retries on a body that will never parse. Stale events are the mirror
image: they're not failures at all, so they ack and log for observability and
that's it.

DLQ redrive is automated by class: poison messages get a fix-and-replay
runbook; permanent rejects get the subscription disabled; transient
exhaustions can auto-redrive once the endpoint's circuit breaker closes."

**What's different at L6:** the three-to-four-way disposition table; "DLQ is
for things a human looks at"; schema → DLQ *first encounter* with the reason
(deterministic, don't waste budget); stale → never DLQ; jitter justified by
the thundering-herd; backoff driven by the candidate, not just the queue
default.

**Anti-signal.** "Everything that fails `maxReceiveCount` times goes to the
DLQ." Or retrying a schema-invalid payload for 3 days. Or no jitter ("retry
storm" never crosses their mind).

**Packet quote (Hire).**
> *"Gave a concrete 3-day truncated-exponential-backoff-with-jitter schedule
> and maxReceiveCount=5, then volunteered a failure-disposition triage:
> transient→retry, schema/poison→DLQ on first encounter (deterministic, don't
> waste budget), stale→log-and-ack-never-DLQ, permanent→disable subscription.
> Framed the DLQ as 'for messages a human looks at.' Unprompted."*

**Packet quote (No Hire).**
> *"Routed all failures, including stale duplicates, to a single DLQ; retried
> schema-invalid payloads for the full window. No jitter; didn't anticipate a
> retry storm."*

### Deep dive C — Fan-out scale + per-subscriber fairness (noisy neighbor)

**Phrasing.** *"One subscriber — call them Acme — is 90% of your total fan-out
volume, and their endpoint is slow (p99 8s, sometimes times out). Walk me
through what your system looks like right now, and what the *other* subscribers
experience."*

**Strong L5 answer.** "If everyone shares one delivery queue, Acme's slow,
timing-out deliveries hold workers and back up the queue, so everyone's
deliveries lag. I'd give Acme their own queue — partition by subscription — so
their backlog is isolated. And I'd add a circuit breaker so we stop hammering
their endpoint when it's clearly down." Identifies the problem and the core
fix (isolation + breaker), usually after the prompt.

**Strong L6 answer.** "The failure mode without isolation: shared queue +
shared worker pool → Acme's 8s timeouts occupy workers, the queue's effective
throughput collapses, and a fast healthy subscriber's event sits behind a wall
of Acme retries — head-of-line blocking at the fleet level. So:

1. **Per-subscriber queues / partitioning.** Fan-out writes each subscriber's
   delivery task to a queue (or partition) keyed by `subscription_id`. Acme's
   backlog drains independently; a tail subscriber is never behind Acme.
   SNS→SQS gives me this naturally — topic fans out, each subscription has its
   own SQS queue, raw message delivery so the body is verbatim.
2. **Per-subscriber concurrency + rate caps.** Cap concurrent in-flight
   deliveries per subscriber (e.g. ≤ 50) and a delivery rate cap so a burst to
   Acme can't consume the whole worker fleet. This is the rate-limiter pattern
   applied to *outbound* fan-out.
3. **Per-subscriber circuit breaker.** Track rolling failure rate per
   endpoint. Threshold breach → open the breaker → deliveries for that
   subscriber fail fast (no HTTP call, straight to backoff) for a cooldown,
   then half-open with a single probe. Critically, the breaker is *per
   subscriber*, never global — Acme being down must not trip delivery to
   anyone else.
4. **Worker-pool fairness.** Workers pull across subscriber queues with
   weighted-fair scheduling so a deep Acme backlog can't starve shallow
   queues, even though Acme is 90% of volume.

Blast radius with isolation: Acme being down/slow affects *only Acme's*
delivery latency and *only Acme's* DLQ. Everyone else is at SLO. Without it:
one slow subscriber degrades the entire platform — the textbook noisy-neighbor
outage. The hot subscriber is the hot-key problem; the answer is the same
shape as hot-tenant rate limiting — isolate, cap, and schedule fairly."

**What's different at L6:** names head-of-line blocking at the fleet level;
per-subscriber queue + concurrency cap + rate cap + circuit breaker as a
*system*, not one fix; breaker is explicitly per-subscriber-never-global;
weighted-fair scheduling so the 90% subscriber can't starve the 10%; states
the blast radius both ways.

**Anti-signal.** "We'd add more workers." Postponement — scale the fleet and
Acme just consumes the bigger fleet too. Or "a global circuit breaker" — trips
delivery to *everyone* when one endpoint dies.

**Packet quote (Hire).**
> *"Volunteered per-subscriber queue isolation + per-subscriber concurrency/
> rate caps + per-subscriber (never global) circuit breaker + weighted-fair
> worker scheduling. Named fleet-level head-of-line blocking as the failure
> mode and stated blast radius both ways. Connected it to hot-key/hot-tenant.
> Unprompted."*

**Packet quote (No Hire).**
> *"On the 90%-noisy-subscriber prompt, proposed adding workers; no isolation;
> proposed a global circuit breaker that would have stopped delivery to every
> subscriber."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **Exactly-once delivery promise.** One sentence and you know. Push: "How,
  across a network, to an endpoint that can 200-then-crash?"
- **Idempotency offloaded entirely to the receiver** with nothing supplied.
  The platform owes a stable `event_id` and (for ordering) a monotonic stamp.
- **Stale events to the DLQ.** Reordered duplicates are normal at-least-once
  output; DLQ-ing them poisons the DLQ. Strong candidates *never* do this.
- **Retrying deterministic failures.** Schema-invalid payload retried for 3
  days. Waste; should DLQ on first encounter.
- **One global queue / one global circuit breaker.** Collapses on the
  noisy-neighbor follow-up.
- **Sync delivery on the producer's request path.** Couples your latency to
  the subscriber. Verify, enqueue, 200 fast.
- **No signing.** Subscribers can't trust the payload; anyone can spoof your
  webhook. HMAC-SHA256 over raw body + timestamp, constant-time compare.
- **Reconciliation never mentioned.** Treats the event stream as a correctness
  guarantee. It isn't; events drop and reorder.
- **No cost reasoning.** Egress and worker-fleet at fan-out scale are real
  dollars.

### Interviewer-side (your own traps)

- **Letting "at-least-once + idempotency" stand without the ordering follow-up.**
  Many recite the slogan. The signal is the monotonic-LWW *mechanism* and the
  log-and-ack disposition, not the slogan.
- **Not driving to reconciliation.** It's the L6 separator; if unprompted by
  minute 50, push the drift scenario. Don't hand them the word.
- **Accepting "we'd use a DLQ" without the triage.** The DLQ is easy to name;
  the disposition triage (what goes, what never goes) is the diagnostic.
- **Leading them to per-subscriber isolation.** It's the right answer, so it's
  tempting. If they don't get there on the 90%-subscriber prompt, that's a
  finding — the packet won't write convincingly if you handed it over.
- **Over-rewarding "we'd use SNS→SQS."** Name-drop is not a signal. "SNS→SQS
  with raw message delivery so each subscriber gets an isolated queue and the
  verbatim body" *is*.

---

## 6. The golden answer (what a strong L6 candidate would produce)

A complete L6-quality walk-through. ~25–30 minutes delivered.

### 6.1 Functional requirements (committed scope)

- Subscribers register endpoints + the event types they want; CRUD on
  subscriptions.
- Internal producers emit events; the platform fans each event out to all
  matching subscriptions and delivers via HTTPS POST.
- **At-least-once delivery** with retries until success or a bounded budget.
- Each delivery carries a stable `event_id`, an `entity_id`, a monotonic
  `last_event_at`, and an **HMAC signature** subscribers verify.
- Delivery status + history queryable; manual/automated **replay** from a
  given time or from the DLQ.
- A **reconciliation** mechanism that periodically corrects drift between
  producer state and what subscribers have applied.

**Explicitly out of scope (named aloud):** exactly-once *delivery* (impossible —
we do at-least-once + idempotency); the subscriber's internal processing;
inbound webhooks (we're the sender); a full pub/sub broker (we build on one).

### 6.2 Non-functional requirements (numbers)

| NFR | Target |
|---|---|
| Events produced (peak) | 50K events/sec |
| Avg fan-out | 5 subscriptions/event (tail: thousands for hot event types) |
| Delivery tasks (peak) | ~250K/sec |
| Registered endpoints | ~1M |
| Delivery p99 (healthy subscriber) | < 5s end-to-end (event produced → 2xx) |
| Per-delivery HTTP timeout | 10s |
| Retry budget | 3 days, truncated exponential backoff + jitter |
| `maxReceiveCount` | 5 (per-subscriber queue → DLQ) |
| Replay / retention | 3 days, time-range and by-subscription |
| Reconciliation cadence | every 15 min (incremental); full sweep nightly |
| Availability (delivery pipeline) | 99.95% — must not couple to subscriber health |
| Payload cap | 256 KB |
| Cost target | < $50K/month |

### 6.3 Capacity estimation

- **Ingest.** 50K events/sec × ~1 KB avg = 50 MB/s = ~4.3 TB/day raw. With
  3-day retention ≈ 13 TB in the durable log — fine for Kafka/Kinesis-class.
- **Fan-out amplification.** 50K events × 5 = 250K delivery tasks/sec peak.
  *This number changes the design:* the delivery queue tier and worker fleet
  are sized to 250K/sec, not 50K/sec — fan-out is the load multiplier, and a
  hot event type (e.g. a system-wide announcement) spikes it far higher, which
  is exactly why per-subscriber isolation matters.
- **Worker fleet.** Healthy delivery ≈ 100ms RTT → one worker thread sustains
  ~10 deliveries/sec; but timeouts up to 10s mean we size for the *unhealthy*
  case. At 250K/sec with generous concurrency, ~5–10K worker threads (a few
  hundred machines). The fleet is dominated by *slow/dead subscribers holding
  connections*, not by healthy throughput — the cost argument for isolation.
- **Delivery-attempt store.** 250K/sec × (a few hundred bytes/attempt) ×
  3-day retention ≈ tens of TB. Bigtable/Cassandra-shaped, TTL'd.
- **Receiver dedup set.** Subscriber-side; `event_id` set with TTL ≥ 3 days.

### 6.4 API design

```
# Subscription management (control plane)
POST /subscriptions
  { url, event_types[], secret_ref, description }
  → { subscription_id, signing_secret }    # secret shown once

PATCH /subscriptions/{id}   { url?, event_types?, status: active|paused }
DELETE /subscriptions/{id}

# Delivery introspection / replay (control plane)
GET  /subscriptions/{id}/deliveries?status=&from=&to=   → paginated attempts
POST /subscriptions/{id}/replay   { from, to } | { event_ids[] }   # redrive

# What the subscriber's endpoint receives (data plane, signed POST)
POST <subscriber_url>
  Headers:
    Webhook-Id:        <event_id>            # stable across retries — dedup key
    Webhook-Timestamp: <unix_seconds>        # signed; replay-window check
    Webhook-Signature: v1,<base64(HMAC_SHA256(secret, id.timestamp.body))>
  Body (verbatim, raw):
    { event_id, type, entity_id, last_event_at, created, data{...} }
  Expected: 2xx within 10s  → success; else retry per schedule
```

> "The receiver verifies the signature over the **raw body** (any
> re-serialization breaks the HMAC), checks `Webhook-Timestamp` is within a
> tolerance window (replay defense), dedupes on `Webhook-Id`/`event_id`, and
> applies last-write-wins on `last_event_at`. Return 2xx fast and process
> async on their side — same advice we follow internally."

### 6.5 Data model

```
subscription:  subscription_id (PK), url, event_types[], signing_secret_ref,
               status (active|paused|disabled), circuit_state, created_at
event:         event_id (PK), type, entity_id, last_event_at (monotonic),
               created, payload_ref          # immutable, in durable log
delivery:      (subscription_id, event_id) PK, attempt_count, last_status,
               next_attempt_at, terminal_state (delivered|dlq|disabled)
entity_cursor: (subscription_id, entity_id) → applied_last_event_at   # for recon
```

### 6.6 High-level architecture (ASCII)

```
   producers (payments, account, ...)
        |  emit event (event_id, entity_id, last_event_at stamped at source)
        v
   +-------------------+
   | Durable Event Log |   Kafka / Kinesis — 3-day retention, replayable
   +-------------------+
        |
        v
   +-------------------+        subscription registry
   |  Fan-out / Disp.  |<------- (which subs match this event type?)
   +-------------------+
        |  one delivery task per matching subscription
        |  (SNS topic per event type, raw message delivery)
        v
   per-SUBSCRIBER queues  (SNS -> SQS fan-out; one SQS queue / subscription)
   +------+   +------+   +------+
   | sub1 |   | sub2 |   | Acme |  <-- noisy subscriber isolated to its own queue
   +------+   +------+   +------+
        \        |         /
         v       v        v
   +--------------------------------+
   |        Delivery Workers         |
   |  per-sub concurrency + rate cap |
   |  per-sub circuit breaker        |
   |  multi-gate validation:         |
   |   source-allowlist -> parse ->  |
   |   schema -> freshness(LWW)      |
   |  HTTP POST + HMAC sign          |
   +--------------------------------+
     |          |              |
   2xx        retry        terminal
     |       (backoff)     /        \
     v          |     poison/schema  stale/out-of-order
  record     visibility   |              |
  delivered  timeout    DLQ            log + ACK
                       (1st enc.)     (NEVER DLQ)
        |
        v
   delivery-attempt store (Bigtable) ---> introspection / replay API

   +---------------------------------------------+
   | Reconciliation cron (every 15m / nightly)   |  REQUIRED companion:
   |  diff producer state vs entity_cursor;      |  emits "repair" events for
   |  emit catch-up events for diverged entities |  anything events missed
   +---------------------------------------------+
```

### 6.7 Delivery semantics: at-least-once + idempotency + LWW (the heart)

> "Exactly-once delivery across a network is impossible — a worker can POST,
> get a 200, and crash before recording success, so we *must* be able to
> redeliver, which means duplicates are inevitable. So: **at-least-once
> delivery, exactly-once *effect*.**
>
> **Dedup:** every event gets a stable `event_id` at production, constant
> across all retries and fan-out copies. `(event_id, subscription_id)` is the
> idempotency key. The receiver keeps a processed-id set (UNIQUE constraint,
> TTL ≥ 3 days) and short-circuits before mutating state.
>
> **Ordering:** the producer stamps a **monotonic `last_event_at`** on every
> event for an entity (valid because the producer is the single writer of that
> entity's state). The consumer applies **last-write-wins**: apply only if
> `incoming.last_event_at > stored.last_event_at`. A stale or out-of-order
> event — a 'pending' arriving after 'paid' — is **not an error**. It
> **degrades to log-and-ack and never touches the DLQ**, because dropping it
> is *correct convergence*. This is the whole trick: LWW gives convergence
> with zero coordination, no global ordering, no per-entity locks. If two
> producers could write the same entity, wall-clock LWW is unsafe and I'd use
> a version/epoch counter instead."

### 6.8 The multi-gate validation pipeline

> "Before a worker applies/delivers, the event passes four gates, each with a
> *defined* disposition:
>
> 1. **Source allowlist** — is this from a producer we trust? Fail → reject +
>    security alert (someone's injecting events). Never DLQ to the *delivery*
>    DLQ; this is an auth event.
> 2. **Parse** — is the body well-formed? Fail → **DLQ on first encounter**
>    (deterministic; retrying a malformed body is pointless).
> 3. **Schema** — does it match the registered event schema/version? Fail →
>    **DLQ on first encounter** (same logic — a human needs to look; a schema
>    drift is a producer bug or a version mismatch).
> 4. **Freshness (LWW)** — is `last_event_at` newer than what we've applied?
>    Stale → **log-and-ack, never DLQ.**
>
> The asymmetry is deliberate: schema failures dead-letter *immediately*
> because they're deterministic and the DLQ is where a human looks; stale
> events *never* dead-letter because they're expected and correct to drop.
> Routing both to the same place is the classic mistake that turns the DLQ
> into noise."

### 6.9 Retries, backoff, DLQ

> "Truncated exponential backoff with full jitter: base 10s, doubling, per-
> attempt cap 12h, total budget 3 days — matching the Stripe-style curve
> (~immediate, 5m, 30m, 2h, 5h, 10h, then every 12h). Jitter is mandatory: a
> broker blip failing 100K deliveries would otherwise synchronize their
> retries into a thundering herd against recovering endpoints. `maxReceiveCount
> = 5` on each per-subscriber queue is the structural backstop, and I drive the
> backoff curve myself via `ChangeMessageVisibility` keyed on
> `ApproximateReceiveCount`.
>
> Disposition recap: transient (5xx/timeout) → retry to budget; poison/schema
> → DLQ first encounter; stale → log-and-ack; permanent (410 Gone, weeks of
> 404) → disable subscription + alert owner. The DLQ is *only* for messages a
> human must triage. Automated redrive: poison → fix-and-replay runbook;
> transient-exhausted → auto-redrive when the circuit closes."

### 6.10 Fan-out fairness / noisy neighbor

> "Fan-out via SNS topic per event type → one SQS queue per subscription
> (raw message delivery, so subscribers get the verbatim body). Per-subscriber
> queue isolation means Acme at 90% of volume and slow drains *its own* queue
> — never head-of-lines a healthy subscriber at the fleet level. Add
> per-subscriber concurrency cap (≤50 in-flight), per-subscriber delivery rate
> cap, per-subscriber (never global) circuit breaker (open on rolling failure
> threshold → fail fast → cooldown → half-open probe), and weighted-fair worker
> scheduling so a deep Acme backlog can't starve shallow queues. Blast radius:
> Acme down affects only Acme's latency and DLQ; everyone else at SLO."

### 6.11 Reconciliation cron (required companion, not afterthought)

> "Events alone do **not** guarantee convergence — they drop, reorder, and
> partition. So event-driven sync *requires* a reconciliation companion. A cron
> (every 15 min, incremental; full sweep nightly) diffs authoritative producer
> state against `entity_cursor` (what each subscription has applied, by
> `last_event_at`). For any entity where producer state is newer than the
> subscriber's applied cursor, it emits a catch-up event through the normal
> delivery path — which is naturally safe because LWW + idempotency make
> re-emission a no-op if the subscriber is actually current. The divergence
> count is a first-class SLI: if it climbs, the event path is silently failing
> and I want to know *before* a subscriber does. This is the part L5 answers
> skip and the part that makes the system actually correct rather than
> usually-correct."

### 6.12 Security / signing

> "HMAC-SHA256 over `id.timestamp.rawbody` with a per-subscription secret;
> subscribers verify with constant-time comparison and reject if
> `Webhook-Timestamp` is outside a ~5-min tolerance (replay defense). Secrets
> are rotatable (dual-secret window). HTTPS only; we don't follow redirects
> (SSRF / open-redirect defense); destination URLs are validated against a
> denylist of internal ranges at registration."

### 6.13 Multi-region / consistency

> "Delivery is **AP** — we favor availability and accept that a given event may
> be delivered late or twice; LWW + idempotency make that safe. The durable
> event log is replicated per-region; producers write locally. Fan-out and
> delivery run per-region against region-local subscriber queues. The
> *subscription registry* is the one thing wanting stronger consistency (a
> paused/deleted subscription must stop receiving), so it's a globally-
> consistent store (Spanner-shaped) with low write QPS. Cross-region: an event
> produced in region A for a global subscriber is delivered by A's workers; we
> don't need cross-region delivery coordination because the event_id dedup +
> LWW tolerate the rare double-delivery if a failover replays."

### 6.14 Cost (back-of-envelope)

> "Dominators at 250K deliveries/sec:
>
> - **Worker fleet:** ~few hundred machines (sized for slow/dead subscribers
>   holding connections, not healthy throughput) ≈ $15–25K/month. The biggest
>   line, and the direct payoff of per-subscriber isolation + circuit breakers
>   — without them we'd over-provision for the worst subscriber globally.
> - **Queue ops:** SNS+SQS at 250K msg/sec ≈ low-single-digit $/month per
>   million × ~650B msgs/month ≈ ~$10–15K.
> - **Durable log + attempt store:** ~13 TB + tens of TB TTL'd ≈ $5–8K.
> - **Egress:** dominated by payload size; 50 MB/s × fan-out, modest at 1 KB.
>
> ~$35–45K/month, under target. **Dominator: the worker fleet**, which is why
> isolation/breakers (which let us provision for the *healthy* case + a
> bounded slow-subscriber reserve) are a cost argument, not just a reliability
> one."

### 6.15 Failure modes & blast radius

| Mode | Symptom | Blast | Recovery |
|---|---|---|---|
| Subscriber endpoint down | deliveries 5xx/timeout | that subscriber's queue only | retry to budget; circuit breaker opens; DLQ + alert if permanent |
| Subscriber 410 Gone / deleted | permanent reject | that subscriber | disable subscription, notify owner; stop wasting attempts |
| Poison payload | schema/parse fail | one event | DLQ on first encounter; fix-and-replay runbook |
| Stale / reordered event | LWW rejects | none | log-and-ack; *correct*, not a failure |
| Noisy subscriber (90%) | their queue deep | isolated to them | per-sub isolation + weighted-fair scheduling; others at SLO |
| Broker/queue partition | delivery stalls | one region | events durable in log; replay on recovery |
| Worker fleet saturation | delivery lag | global delivery latency | autoscale; circuit breakers shed dead-endpoint load |
| Events silently dropped | subscriber drift | one subscriber | reconciliation cron catches it; divergence SLI alerts |
| Signing-secret leak | spoofable payloads | one subscription | rotate via dual-secret window |

> "Single most useful runbook: delivery lag on a subscriber → check circuit
> state (endpoint down?), queue depth (backlog?), and DLQ rate (poison?). Three
> different fixes. And the divergence SLI is the one that catches the *silent*
> failure — the event the system thinks it delivered but didn't."

### 6.16 Evolution at 10×

> 1. **10× event rate (50K → 500K/sec, 2.5M deliveries/sec).** Partitions up,
>    worker fleet up, more SQS queues. The seams that *don't* change: LWW +
>    idempotency semantics, per-subscriber isolation, DLQ triage,
>    reconciliation. Knobs, not architecture.
> 2. **Strict per-entity ordering demanded by a subscriber.** Partition that
>    subscriber's queue by `entity_id`, single in-flight per partition. Cost:
>    throughput drops and one stuck event head-of-lines its entity's stream —
>    I'd surface that trade-off and default to LWW unless they truly need it.
> 3. **Subscriber-pull (polling) mode for endpoints that can't accept pushes.**
>    Same event log, a cursor-based pull API instead of POST; reuses dedup +
>    LWW. Clean seam.
> 4. **Org seams:** the control plane (subscription registry, signing, replay
>    UI) is a natural team handoff distinct from the data-plane delivery fleet;
>    reconciliation is owned alongside whoever owns the producer's
>    source-of-truth, since it diffs against that state."

---

## 7. Signals scorecard

| Lean-in (packet-quotable Hire) | Lean-back (packet-quotable No Hire) |
|---|---|
| "At-least-once delivery, exactly-once *effect* via stable event_id + receiver UNIQUE constraint." | "We'll do exactly-once delivery with an outbox." (impossible across the third-party hop) |
| "Monotonic producer-stamped last_event_at, last-write-wins; stale event → log-and-ack, NEVER DLQ — that's correct convergence." | Offloads all ordering to the subscriber; or DLQs stale/out-of-order events. |
| Three/four-way disposition triage: transient→retry, schema/poison→DLQ first encounter, stale→log-and-ack, permanent→disable. | "Everything that fails maxReceiveCount times goes to the DLQ." |
| Concrete schedule: truncated exp backoff + full jitter, base 10s, 12h cap, 3-day budget, maxReceiveCount=5, jitter justified by thundering-herd. | "We retry a few times then give up." No numbers, no jitter, retries schema-invalid payloads. |
| Multi-gate pipeline: source-allowlist → parse → schema → freshness, each with a defined disposition. | Single validation step; no notion of which failure routes where. |
| Per-subscriber queue isolation + concurrency/rate cap + per-subscriber (never global) circuit breaker + weighted-fair scheduling. | One global queue; or a global circuit breaker that stops delivery to everyone. |
| "Reconciliation cron is a *required companion* — events drop/reorder; divergence is a first-class SLI." | Reconciliation never mentioned; treats the event stream as a correctness guarantee. |
| Verify, enqueue, 200-fast; delivery decoupled from producer request path. | Synchronous webhook POST inside the producing request. |
| HMAC-SHA256 over raw body + timestamp tolerance, constant-time compare, SSRF/redirect defense. | No signing; or hand-rolled HMAC with naive string compare. |
| AP on delivery path, strongly-consistent subscription registry, CAP stated out loud. | No consistency stance; assumes the broker gives ordering/exactly-once. |
| Cost number with worker-fleet as the dominator and isolation framed as a cost lever. | Treats workers, egress, and queue ops as free. |
| On 10×: partitions + fleet scale; LWW/isolation/DLQ/recon unchanged — names what *doesn't* change. | Treats 10× as a redesign. |

---

> Related: the noisy-neighbor / fail-open reasoning here is the outbound mirror
> of `05-rate-limiter.md`; the at-least-once / idempotency / replay machinery
> rhymes with the payments-ledger reconciliation story. Next: `09-multi-tenant-saas.md`.

## Sources & references

- Hello Interview / System Design Handbook — *Design a Webhook System*
  (decoupled producer→queue→worker pipeline, at-least-once + idempotency,
  per-tenant queue isolation):
  systemdesignhandbook.com/guides/design-a-webhook-system/
- Stripe Documentation — *Receive Stripe events in your webhook endpoint*
  (retry schedule: immediate, 5m, 30m, 2h, 5h, 10h, then every 12h up to 3
  days; raw-body HMAC-SHA256 signing; order by `created`; dedupe on event id;
  return 2xx fast): docs.stripe.com/webhooks
- AWS — *Using dead-letter queues in Amazon SQS* (`maxReceiveCount`, redrive
  policy, poison-message isolation; DLQ replay):
  docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
- AWS — *Sending and receiving webhooks on AWS* and *event-driven patterns
  with SNS/SQS/EventBridge* (SNS→SQS fan-out, raw message delivery, cron via
  EventBridge): aws.amazon.com/blogs/compute/sending-and-receiving-webhooks-on-aws-innovate-with-event-notifications/
- Hookdeck — *Building a Reliable Service for Sending Webhooks* and *Webhooks
  at Scale* (per-tenant queues, per-endpoint circuit breakers, rate limits,
  noisy-neighbor isolation): hookdeck.com/blog/building-reliable-outbound-webhooks
- Microsoft Azure Architecture Center — *Noisy Neighbor Antipattern* (the
  fairness/isolation framing applied to fan-out):
  learn.microsoft.com/azure/architecture/antipatterns/noisy-neighbor
- Practitioner aggregate on idempotency + ordering: Hookdeck
  *Implement Webhook Idempotency*, bugfree.ai *Idempotency and Ordering in
  Webhook Handlers*, and the exactly-once-is-a-consumer-property consensus from
  the SNS/SQS event-sourcing literature.
