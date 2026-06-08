# Question 9: Design a Multi-Tenant SaaS Platform (tenant isolation / noisy-neighbor / per-tenant routing)

> Interviewer-side preparation pack for a 1-hour Google L5/L6 system-design
> round. The candidate prompt is deliberately vague: *"Design a multi-tenant
> SaaS platform — a shared control plane serving thousands of organizations,
> think Slack / Datadog / GitHub-style multi-tenancy."*
>
> This is a second **operational / multi-tenant** anchor, sibling to the rate
> limiter (`05`). Its calibration value is *judgment under constraint, not
> knowledge recall*: every load-bearing axis — isolation model, where tenant
> context is enforced, hot-tenant containment, per-tenant routing and its
> security — has a clean L5 answer that is *wrong at L6 scale*. The room is
> watching whether the candidate treats "tenant" as a `WHERE` clause or as a
> first-class isolation boundary enforced top-to-bottom.

---

## 1. Why this question (interviewer's framing)

Multi-tenancy *looks* like CRUD with an extra column. A prepared L4 adds
`tenant_id` to every table, scopes queries in the app layer, and stops.
That is the trap. The real question is: *given one shared control plane
serving thousands of orgs with wildly skewed sizes, how do you isolate
them, keep one tenant from sinking the others, route per-tenant config
safely, and operate the whole thing — and what breaks first?*

What I'm actually testing:

- **Isolation is a spectrum, not a column.** Silo / pool / bridge is the
  central trade-off (cost vs. blast-radius vs. compliance). Does the
  candidate pick *per data class* rather than one global answer?
- **Where is tenant context enforced?** App-layer `WHERE tenant_id`
  alone is one missing clause away from a cross-tenant breach. The hire
  signal is **defense-in-depth** — context enforced *below* the app, in
  the data layer (RLS) and a policy engine, with the safe failure mode
  (no rows, not all rows).
- **Noisy neighbor.** Traffic and data are power-law. One tenant is 50%+
  of load. Naive pooling lets that tenant degrade everyone.
- **Per-tenant routing and its security.** Tenant config (SSO endpoint,
  data region, feature flags) is dispatched at request time. Letting a
  tenant inject the *host* it routes to is an SSRF in waiting.
- **O(1) tenant operations.** Tenant-level changes (suspend, retier,
  region-move) must not fan out per-member. A 50k-seat org change that
  touches 50k rows is an L5-ceiling design.

### What "Hire" looks like at each level

**L5 Hire.** Splits control plane from data plane unprompted. Names the
silo/pool/bridge trade-off and commits — typically pool with `tenant_id`
plus per-tier escalation. Knows app-layer scoping is insufficient and
reaches for **row-level security** as a backstop. Identifies noisy-neighbor
risk and proposes per-tenant rate limits / connection caps. Designs a
tenant→config lookup and a clean onboarding flow. Names specific tech
(Postgres RLS, a token-carried `tenant_id`, a shared gateway) with
one-sentence justifications. Reasons about failure when asked.

**L6 Hire** = all of the above, **plus**: commits to a *tiered* isolation
model and states the **promotion path** (pool → bridge → silo) as a
migration, not a redesign; insists tenant context is enforced **server-side
by a policy engine**, not trusted from the request, and treats the
`tenant_id` claim's *provenance* (signed at auth, never client-asserted) as
a security control; designs hot-tenant containment with **named overshoot
and the shuffle-shard / dedicated-shard escalation**; makes the per-tenant
routing safe by dispatching from a **code-level template map with hosts
pinned to an internal namespace** — no payload-injected hosts; guarantees
**one authoritative tenant per user (PK-enforced)** and **one domain → one
tenant (verified)**; makes tenant-level changes **O(1)** via an epoch/version
bump, never per-member fan-out; volunteers cost, blast-radius, and the org
seams (who owns the control plane vs. the data plane). States CAP commitments
out loud.

### Classic downlevel traps

1. **`tenant_id` column and stop.** App-layer scoping only; one forgotten
   `WHERE` leaks every tenant. No RLS, no policy engine. Modal L5→L4.
2. **One global isolation answer.** "Everyone shares one database" *or*
   "every tenant gets their own database" — neither survives the
   cost-vs-compliance follow-up. The answer is *tiered*.
3. **Trusting the request for tenant identity.** Reading `tenant_id` from a
   header/body the client controls. Cross-tenant access by parameter
   tampering — a security no-hire.
4. **Payload-injected routing host.** Letting the tenant config carry the
   URL host the platform calls. Classic SSRF; instant flag.
5. **Per-member fan-out on tenant ops.** Suspending a 50k-seat org by
   writing 50k rows. Doesn't scale; misses the O(1) insight.
6. **Ignoring the power law.** Designing for the median tenant; collapses on
   "one tenant is 60% of traffic."

---

## 2. The 60-minute plan

Minute-by-minute. What you'll say, what you're listening for, when to push
vs. stay quiet.

### 0–5 min — Intro

**Say:** "Hi, I'm $X. Tell me about yourself, then design a multi-tenant
SaaS platform — a shared control plane serving thousands of organizations,
Slack/Datadog/GitHub-style. Take it wherever you think it should go."

**Listen for** whether they sit with the ambiguity or bolt to "add
`tenant_id` everywhere." Restating the problem and asking "what *kind* of
tenants — self-serve SMB, or regulated enterprise?" is an L6 tell — it
tees up the tiered isolation answer. **Stay quiet**; this is their space.

### 5–15 min — Requirements and scope

**Listen for** them to volunteer: control plane vs. data plane;
isolation requirements (any tenants with data-residency / compliance
contracts?); per-tenant config (SSO, regions, flags, quotas); the
*identity* questions — can a user belong to >1 tenant? how does a domain
map to a tenant?; and hard numbers (tenant count, size skew, per-tier p99,
storage per tenant).

**Numbers to provide when asked:** ~50k tenants; size skew is a power law —
the top 1% of tenants are ~60% of traffic and data; ~20M total users; p99
budgets per tier (Enterprise ≤150ms, Pro ≤250ms, Free ≤500ms); storage from
~10MB (free) to ~50TB (largest enterprise); 99.95% control-plane
availability; tenant-config change visible in <30s.

**Push back** if they commit to "highly scalable / isolated" without
numbers — quote them back at minute 30. Push back if they don't ask
whether a user can span tenants (the PK-enforced single-tenant insight
hides here). Stay quiet while they enumerate.

### 15–25 min — Estimation + isolation model + high-level architecture

**Listen for** numbers that *change a decision* (the power-law skew should
force tiering, not "we have 50k tenants" in the abstract); a committed
isolation model — **pool by default with bridge/silo for upper tiers**,
defended on cost and blast-radius; an architecture with **separate control
and data planes**, a routing/context layer at the edge, and isolation
enforced *below* the app. **If tenant context lives only in app code, the
design is L5-ceiling and the room knows it.**

**Push back** on a single global database for 50k tenants ("the 50TB
enterprise tenant shares a buffer cache with 10k free tenants — what's the
p99 for the free tenants when the whale runs a backfill?"). Push back on
silo-everything ("50k Postgres instances — what's the ops cost and the
patch story?"). Stay quiet when commits are crisp.

### 25–45 min — Deep dives (the diagnostic zone)

Three **mandatory** dives — all three should be hit; pick order by where
they're weakest:

1. **Isolation model + context enforcement on every path.** Ask: *"A
   request comes in. Trace how the platform knows which tenant it's for,
   and how a bug in app code still can't read another tenant's data."*
2. **Noisy-neighbor / hot-tenant containment.** Ask: *"One tenant is 60%
   of traffic. What changes?"*
3. **Per-tenant config & routing, and its security.** Ask: *"Tenants have
   their own SSO endpoint / data region. How do you route to it at request
   time without it becoming an SSRF?"*

**Listen for at L6:** defense-in-depth (signed `tenant_id` claim → policy
engine → RLS, with the no-rows failure mode); tiered/shuffle-shard hot-tenant
isolation with named overshoot; routing dispatched from a **code-level
template map, hosts pinned to an internal namespace, no payload hosts**;
the **O(1) tenant-op** insight (epoch bump, not fan-out).

**Push back hard** on "we scope queries by tenant_id" with no backstop
("show me the breach: one engineer ships a query missing the clause — what
stops it?"). Push back on "the tenant configures their callback URL" ("can
they point it at `169.254.169.254`?"). Stay quiet on specifics + trade-offs.

### 45–55 min — Evolution and failures

**Mandatory scenario** — drive to it if unprompted by 45:

> *"Your biggest enterprise tenant — 40% of platform load — runs a
> runaway job. Walk me through what every other tenant experiences,
> minute by minute, and what your design does about it."*

**Listen for** blast-radius reasoning bounded by isolation tier (whale is
already on a dedicated shard / silo, so tail tenants are insulated; if
pooled, the per-tenant quota + circuit breaker caps the bleed); the recovery
path; cost reasoning (why not silo-everyone). Curveballs if time: *"A tenant
must move to the EU region for GDPR — migration?"* (re-tier pool→silo, dual
-write + backfill + cutover, the tenant epoch makes routing flip atomically);
*"10× tenants overnight."*

### 55–60 min — Wrap

Hard stop. ~3 min for candidate questions. Still scoring — "how's the
on-call split between the control-plane and data-plane teams?" reads very
differently from "how fast can I get promoted?"

---

## 3. Probing prompts (the kit)

~15 prompts you can drop verbatim at any point. Each maps to one signal.

| # | Prompt | Signal you're hunting |
|---|---|---|
| 1 | "Silo, pool, or bridge — pick one and tell me why." | Commits *and* defends on cost/blast-radius; ideally picks *per data class*. |
| 2 | "A request arrives. How does the platform know which tenant it's for?" | Tenant identity from a *signed* claim, established at auth — not read from a client-controlled field. |
| 3 | "An engineer ships a query missing the tenant filter. What stops the breach?" | RLS / policy engine as the backstop; the no-rows-not-all-rows failure mode. |
| 4 | "Can a user belong to two tenants? What's the data model?" | One authoritative tenant per user, PK-enforced; transitions are delete-then-insert. |
| 5 | "Two tenants both verify `acme.com`. What happens?" | Domain verification; one domain → exactly one tenant; uniqueness enforced. |
| 6 | "One tenant is 60% of traffic. What changes?" | Per-tenant quota + dedicated shard / shuffle-shard escalation; named overshoot. |
| 7 | "The whale runs a backfill. What's the free tier's p99?" | Resource isolation below the quota — connection pools, query budgets, separate compute. |
| 8 | "Tenants have their own SSO endpoint. How do you route to it?" | Dispatch from a code-level template map; host pinned to an internal namespace. |
| 9 | "Where does the URL host for that callback come from?" | NOT the tenant payload. SSRF awareness; allowlist / namespace pin. |
| 10 | "Suspend a 50k-seat tenant right now. How many rows do you write?" | O(1) — epoch/status bump on the tenant, not per-member fan-out. |
| 11 | "How does a tenant-config change propagate, and how fast?" | Control plane → versioned config → data plane pull/push; <30s SLA; cache + version. |
| 12 | "Enterprise wants data residency in the EU. Migration path?" | Pool→silo re-tier; dual-write + backfill + atomic cutover via tenant epoch. |
| 13 | "What's your per-tier p99 and how do you keep them separate?" | Per-tier SLOs *and* the isolation that makes them defensible, not aspirational. |
| 14 | "What dominates your monthly cost, and what's the lever?" | Compute/DB density per tenant; pooling the free tail is the lever. |
| 15 | "Control plane has a 10-min outage. Can tenants still serve traffic?" | Data plane runs on cached config; fail-static, not fail-closed-everything. |

---

## 4. Where to dig deeper (interviewer's picks)

All three are effectively mandatory. For each: phrasing, L5 vs. L6 answer
shape, anti-signal, and the packet quote you'd love to write.

### Deep dive A — Isolation model + tenant-context enforcement

**Phrasing.** *"A request comes in. Trace how the platform knows which
tenant it's for, and explain how a bug in application code still can't
read another tenant's data."*

**L5 shape.** "Pool model: one database, every table has `tenant_id`, every
query filters on it. We extract `tenant_id` from the JWT and pass it down."
Correct skeleton. Reaches for RLS when prompted: "we'd also add Postgres
row-level security as a backstop." Competent — but enforcement is still
described as app-mediated, and the *provenance* of the tenant claim is
unexamined.

**L6 shape.** "Isolation is **tiered, picked per data class**. Default
**pool** — shared database, `tenant_id` on every row — for the long tail of
small tenants, because density is the whole cost argument. **Bridge**
(schema-per-tenant on shared instances) for mid-tier. **Silo** (dedicated
DB/instance) for enterprise tenants with residency or contractual
isolation. The tier is a *property of the tenant* in the control plane, and
moving between tiers is a migration, not a redesign.

Now enforcement — three independent layers, **defense in depth**:

1. **Provenance.** `tenant_id` is *never* read from a client-controlled
   field. It's resolved at auth from the user's authoritative tenant
   binding and signed into the session/token. The API boundary validates
   the claim; nothing downstream trusts a header.
2. **Policy engine, server-side.** Every read/write goes through a central
   authorization decision — *not* scattered `if` checks in each service.
   The engine takes `(subject, tenant, resource, action)` and returns
   allow/deny. Isolation is a platform property, not a per-feature
   responsibility, so a new endpoint can't *forget* to be tenant-scoped.
3. **Row-level security at the database.** The request's tenant is set into
   the DB session with `SET LOCAL` (per-transaction, so it can't leak across
   a pooled connection), and an RLS policy filters every row. The critical
   property: **a query missing the tenant context returns zero rows, not all
   rows** — fail-closed by construction. Index `tenant_id` as the leading
   column or RLS is two orders of magnitude slower. `BYPASSRLS` is reserved
   for migration roles only; admin access is an explicit policy.

So the breach scenario — an engineer ships a query without the filter —
is caught twice below the app: the policy engine denies the un-scoped
action, and even if that were bypassed, RLS returns no rows. App-layer
scoping is the convenience layer, not the security boundary."

**Anti-signal.** "We filter by `tenant_id` in the service layer" with no
layer beneath it; or reading the tenant from a request header; or `SET`
(session-persistent) instead of `SET LOCAL` under connection pooling — a
cross-tenant leak waiting for the next request on that connection.

**Packet quote.**
> *"Committed to tiered isolation (pool/bridge/silo per data class) and
> enforced tenant context in three independent layers — signed claim,
> server-side policy engine, and database RLS with SET LOCAL — naming the
> no-rows-not-all-rows fail-closed property unprompted. Treated the tenant
> claim's provenance as a security control."*

### Deep dive B — Noisy-neighbor / hot-tenant containment

**Phrasing.** *"Tenants follow a power law — your top tenant is 60% of
platform traffic. What changes in your design, and what does the free
tenant on the same infrastructure experience when the whale spikes?"*

**L5 shape.** "Per-tenant rate limits and per-tenant DB connection caps so
one tenant can't monopolize. Maybe move the big tenant to its own
database." Recognizes the problem; the solution is mechanical and reactive.

**L6 shape.** "Containment at three layers, and the whale shouldn't be in
the pool at all:

- **Request layer:** per-tenant quotas (token bucket per `(tenant,
  endpoint)`) so a spike is throttled at the edge before it reaches shared
  resources. Quotas are per-*tier*; overshoot bounded and named (≤5% per
  tenant per minute on shared pools).
- **Resource layer:** the real noisy-neighbor vector isn't QPS, it's shared
  *capacity* — DB buffer cache, connection pool, I/O. Per-tenant connection
  caps and per-query cost budgets (statement timeout per tenant) so a
  runaway analytical query can't evict the free tier's working set. This is
  the part L5s miss — rate-limiting QPS doesn't stop one expensive query.
- **Placement layer:** the whale is a *tier promotion trigger*, not a
  runtime problem. Above ~1% of platform traffic, a tenant is **promoted to
  a dedicated shard or silo** — data-driven (hourly job on observed load),
  not contract-driven, because sales' 'small customer' lags real QPS. For
  the mid tail, **shuffle sharding**: each tenant maps to a small random
  subset of shards, so any one tenant's blast radius is a fraction of the
  fleet and two tenants rarely fully overlap. A whale that hasn't been
  promoted yet is bounded to its shuffle-shard subset; the free tenant
  almost certainly doesn't share all of the whale's shards.

So when the whale spikes: if promoted (the steady state), it's on its own
silo and the free tenant sees *nothing*. If still pooled, the per-tenant
quota throttles it, the connection cap stops it from starving the pool, and
shuffle sharding bounds the bleed to a small overlap. The free tier's p99
budget (≤500ms) holds because the isolation is structural, not best-effort."

**Anti-signal.** "Rate-limit per tenant" and stop — misses that the
dangerous noisy neighbor is a cheap-QPS / expensive-per-query tenant.
"Auto-scale the cluster" — scaling doesn't isolate; the whale just gets a
bigger share of a bigger pool.

**Packet quote.**
> *"Three-layer containment — per-tenant quota, per-tenant connection/query-
> cost caps (named the expensive-query vector that QPS limits miss), and
> placement via shuffle sharding plus data-driven promotion to dedicated
> shards above 1% traffic. Bounded the free tier's p99 structurally.
> Unprompted."*

### Deep dive C — Per-tenant config & routing, and its security

**Phrasing.** *"Tenants own their own enforcement endpoint — SSO callback,
data region, webhook target. The platform has to dispatch to it at request
time. How do you do that, and how do you keep it from becoming an SSRF or a
cross-tenant routing bug?"*

**L5 shape.** "Tenant config table: `tenant_id → {sso_url, region,
flags}`. At request time we look it up and call the endpoint. Cache it for
performance." Functionally correct, security-naive — the URL came from
tenant-supplied config, so the platform will happily make a server-side
request to whatever host the tenant put there.

**L6 shape.** "Two separate concerns: *what* to dispatch, and *where* it's
allowed to go.

- **What:** the per-tenant enforcement endpoint is **owned by the tenant**
  (their config), resolved from the control plane and cached in the data
  plane with a version. A config change propagates in <30s — the data plane
  pulls the new version (or is pushed a delta) and atomically swaps; stale
  reads bounded by the version SLA.
- **Where — the security control:** the dispatch target is **not a host the
  tenant injects in a payload**. The platform dispatches from a **code-level
  template map** — a fixed, code-reviewed set of endpoint *templates* keyed
  by enforcement type, where the URL **host is pinned to an internal
  namespace** the platform controls. The tenant supplies *parameters*
  (their realm ID, their region selector), never the host. So even a
  malicious tenant config cannot point the platform's server-side request at
  `169.254.169.254` or another tenant's internal service — the host is not
  theirs to set. This is the difference between 'tenant configures a
  webhook URL we blindly call' (SSRF) and 'tenant selects from
  platform-controlled routing templates' (safe).
- **Identity invariants that make routing unambiguous:**
  - **One authoritative tenant per user, PK-enforced.** The user→tenant
    binding has the user as primary key, so a user resolves to exactly one
    tenant — no ambiguity at routing time. Tenant transitions are
    **delete-then-insert** (atomic re-binding), never an additive second
    row, so there's never a moment where a user belongs to two tenants.
  - **One domain → exactly one tenant, verified.** Domain ownership is
    proven (DNS TXT / file challenge) before binding, and the
    `domain → tenant` mapping has the domain as a unique key. Two tenants
    cannot both claim `acme.com`; the second verification fails. This is
    what makes 'route by email domain at login' safe.
- **O(1) tenant operations.** Tenant-level changes — suspend, retier,
  region-move, feature-flag flip — are a **single write to the tenant
  record plus a version/epoch bump**, *not* a fan-out across the tenant's
  50k members. The data plane reads the tenant's current epoch/status on the
  request path (cached), so a suspend is visible everywhere within the
  config-propagation SLA without touching a single member row."

**Anti-signal.** "We call the URL in the tenant's config" (SSRF). "User has
a list of tenants they belong to" with no single-authority constraint
(ambiguous routing, and the delete-then-insert transition insight is gone).
"To suspend a tenant we update every user's status" (per-member fan-out).

**Packet quote.**
> *"Dispatched per-tenant routing from a code-level template map with hosts
> pinned to an internal namespace — explicitly rejected payload-injected
> hosts as SSRF — and grounded routing in PK-enforced single-tenant-per-user
> and verified one-domain-one-tenant invariants. Made tenant ops O(1) via an
> epoch bump rather than per-member fan-out. Unprompted on the security
> framing."*

---

## 5. Watch-outs / common traps

### Candidate-side traps (anti-signals)

- **`tenant_id` column as the entire isolation story.** No RLS, no policy
  engine, no defense in depth. One missing `WHERE` = breach. Down-level.
- **One global isolation model.** Pool-everything ignores the whale and
  compliance; silo-everything ignores cost and the patch/ops story.
- **Tenant identity from the request.** Header/body-supplied `tenant_id`;
  trivially tampered. Security no-hire.
- **Payload-injected routing host.** Tenant config carries the URL host the
  platform calls server-side. SSRF; quotable mistake.
- **Per-member fan-out on tenant ops.** Suspend/retier touches every member
  row. Misses the O(1) epoch-bump insight.
- **Noisy neighbor = rate limit and done.** Misses the expensive-query /
  shared-capacity vector that QPS limits don't cover.
- **`SET` vs `SET LOCAL`.** Session-persistent tenant context under a pooled
  connection leaks to the next request. Subtle but career-ending.
- **Config/ops as a minute-55 footnote.** No propagation SLA, no
  control/data-plane split, "we'd add monitoring" at the end.
- **No cost reasoning.** Treats per-tenant compute/DB as free; can't say why
  pooling the tail is the lever.

### Interviewer-side traps (your own)

- **Letting them stay in CRUD-with-a-column territory.** Easy to nod along.
  By minute 25 force the breach question: *"missing WHERE clause — what
  stops it?"*
- **Not driving to the whale-spike scenario.** It's mandatory. If unprompted
  by minute 45, push.
- **Leading them to RLS / template-map / epoch-bump.** These are the answers
  that earn the level. If you hand them over, the packet won't write
  convincingly — that's a finding, not a rescue.
- **Over-rewarding name-drops.** "We'd use Postgres RLS" is not a signal.
  "RLS so a forgotten clause returns no rows, with `SET LOCAL` so context
  doesn't leak across pooled connections" *is*. Test the depth.
- **Accepting silo-everyone uncritically.** It "solves" isolation but at a
  cost most candidates can't defend. Push on ops/patch/cost.

---

## 6. The golden answer (what a strong L6 candidate would produce)

A complete walk-through at L6 quality. ~25–30 minutes of speaking time.

### 6.1 Functional requirements

- **Tenancy:** thousands of orgs (tenants); each has users, resources, and
  config; strict cross-tenant isolation of data and traffic.
- **Identity:** users authenticate and resolve to **exactly one
  authoritative tenant**; tenant membership transitions are atomic.
- **Domains:** a tenant verifies ownership of one or more domains; **a
  domain maps to exactly one tenant** (used for login routing / auto-join).
- **Per-tenant config:** SSO endpoint, data region, feature flags, quotas,
  SKU tier — all tenant-owned, dispatched at request time.
- **Control plane:** tenant lifecycle — onboard, suspend, retier,
  region-move, bill/meter — all **O(1) tenant-level operations**.
- **Tiering:** Free / Pro / Enterprise with different isolation, SLOs, and
  quotas.

**Out of scope (named aloud):** the product features themselves (we're
designing the *platform*, not the app); a full billing engine (we emit
metering events); end-to-end identity-provider internals (covered by the SSO
guide `06`) — here we only route to the tenant's IdP.

### 6.2 Non-functional requirements (with numbers)

| Dimension | Commitment |
|---|---|
| Tenants | ~50k; power law — **top 1% ≈ 60% of traffic + data** |
| Users | ~20M total; largest tenant ~80k seats |
| Per-tier p99 (read) | Enterprise ≤150ms · Pro ≤250ms · Free ≤500ms |
| Storage per tenant | ~10MB (free) → ~50TB (largest enterprise) |
| Isolation | tiered: pool (free/Pro tail) · bridge (mid) · silo (enterprise) |
| Cross-tenant breach | **zero tolerance** — enforced in ≥2 layers below app |
| Control-plane availability | 99.95%; data plane survives control-plane outage (fail-static) |
| Config propagation | tenant-config change visible <30s p99 |
| Tenant op latency | suspend/retier visible <30s; **O(1)** writes (no member fan-out) |

### 6.3 Capacity estimation (worked — call out what changed a decision)

- **The skew is the design driver.** 50k tenants is small; the *power law*
  is everything. Top 1% (500 tenants) ≈ 60% of load. Designing for the
  median tenant (~10MB, low QPS) and then putting the 50TB whale in the same
  pool is the mistake — its backfill evicts everyone's buffer cache. **This
  number forces tiering**, not a single shared store.
- **Pooled tail.** ~49.5k small tenants × ~10–100MB ≈ a few TB total —
  trivially fits a sharded pooled cluster. Density is the cost win.
- **Whales.** 500 tenants × up to 50TB → siloed; each its own DB
  instance(s). The ops cost (patching, backups) is bounded to 500 instances,
  not 50k — *this* is why we don't silo everyone.
- **Routing/context overhead.** Tenant-config lookup on every request →
  cache in the data plane keyed by `tenant_id` with a version; ~0.1ms cache
  hit. RLS `SET LOCAL` + policy eval ≈ <0.5ms with `tenant_id` as leading
  index column. Hot path stays sub-ms below the app logic.

### 6.4 API surface

```
# Control plane (low QPS, strongly consistent)
POST   /tenants {name, tier}                  -> {tenantId}
POST   /tenants/{id}/domains {domain}         -> {challenge}        # verify before bind
POST   /tenants/{id}/domains/{d}/verify       -> {bound: bool}      # DNS TXT / file challenge
PATCH  /tenants/{id} {status|tier|region}     -> {versionId}        # O(1): record write + epoch bump
PUT    /tenants/{id}/config {sso, flags, ...} -> {versionId}        # versioned; data plane pulls delta
POST   /tenants/{id}/users {userId}           -> {ok}               # delete-then-insert re-bind
GET    /tenants/{id}/config?since={version}   -> {config, version}  # data-plane pull

# Data plane (hot path; tenant resolved from signed session, NOT from body)
GET    /v1/resources/{id}    Authorization: Bearer <session>        # tenant = signed claim
POST   /v1/resources {...}   Authorization: Bearer <session>
```

`tenant_id` is **never** an API parameter on the data plane — it is resolved
server-side from the authenticated session. Accepting it from the request is
the cross-tenant tampering hole.

### 6.5 Data model

```
tenant(tenant_id PK, name, tier, status, region, config_version, epoch)
user(user_id PK, tenant_id FK, role)         -- user_id is PK => ONE tenant per user
domain(domain PK, tenant_id FK, verified_at) -- domain is PK => ONE tenant per domain
resource(resource_id PK, tenant_id, ...)     -- tenant_id leading index col; RLS policy on it
tenant_config(tenant_id, version, payload)   -- versioned; control plane writes, data plane reads
```

- **`user.user_id` as PK** is the single-authoritative-tenant invariant.
  Re-binding a user to another tenant is **delete-then-insert** in one
  transaction — there is never a row state where the user is in two tenants.
- **`domain.domain` as PK** is the one-domain-one-tenant invariant; the
  second tenant to verify `acme.com` fails on the unique key.
- **`tenant.epoch`** is the O(1) lever: suspend = `status='suspended',
  epoch++`; the data plane reads epoch/status on the request path (cached),
  no member rows touched.

### 6.6 High-level architecture (ASCII)

```
                         clients (web / mobile / API)
                                     |
                                     v
                          +----------------------+
                          |   Edge / Routing      |  domain-driven (DNS/subdomain)
                          |   + Auth boundary     |  + data-driven (signed claim)
                          +----------+-----------+
                                     | tenant_id = SIGNED claim (never from body)
                  +------------------+------------------+
                  |                                     |
                  v                                     v
        +-------------------+                 +----------------------+
        |  CONTROL PLANE    |                 |   DATA PLANE          |
        |  (shared, always) |                 |   (tiered isolation)  |
        |  - onboarding     |   versioned     |  +-----------------+  |
        |  - tenant mgmt    |   config        |  | Policy Engine   |  | (subject,tenant,
        |  - domain verify  |---- push/pull -->|  | (authz decision)|  |  resource,action)
        |  - tier/billing   |   <30s SLA      |  +--------+--------+  |
        |  - config store   |                 |           |          |
        +---------+---------+                 |           v          |
                  |                           |  +-----------------+ |
                  v                           |  | App services    | |
        +-------------------+                 |  +--------+--------+ |
        |  Tenant DB        |                 |           | SET LOCAL tenant
        |  (Spanner-class)  |                 |           v  + RLS policy
        +-------------------+                 |  +------------------------------+
                                              |  | Pool DB | Bridge | Silo DBs  |
                                              |  | (tail)  |(schema)|(whales)   |
                                              |  +------------------------------+
                                              +----------------------+
       Per-tenant routing: dispatch from CODE-LEVEL TEMPLATE MAP
       { enforcementType -> url-template, host pinned to internal namespace }
       tenant supplies PARAMS only (realm, region) -- never the host (anti-SSRF)
```

Three deliberate separations: **control plane** (shared, strongly
consistent, low QPS) owns tenant lifecycle and config; **data plane**
(tiered, high QPS) serves traffic and is where isolation is enforced; the
**edge** establishes tenant identity as a signed claim once, so nothing
downstream trusts the request body.

### 6.7 Isolation model (tiered, per data class)

| Tier | Model | Store | Rationale |
|---|---|---|---|
| Free / Pro tail | **Pool** | Shared sharded DB, `tenant_id` + RLS | Density = the cost win; tenants small + similar |
| Mid | **Bridge** | Schema-per-tenant on shared instances | Stronger isolation, no `tenant_id` column risk, still dense |
| Enterprise / regulated | **Silo** | Dedicated DB/instance, own region | Contractual isolation, residency, no noisy neighbor; ops bounded to ~500 |

Tier is a **property of the tenant** in the control plane. Promotion
(pool→bridge→silo) is a **migration** (§6.11), not a redesign — same API,
same policy engine, different placement.

### 6.8 Tenant-context enforcement (defense in depth)

1. **Provenance:** `tenant_id` resolved at auth from the user's PK-enforced
   tenant binding, signed into the session. Edge validates; downstream never
   reads it from a header/body.
2. **Policy engine:** every action is an `(subject, tenant, resource,
   action)` decision at a central authorizer — isolation is a platform
   property, so a new endpoint *cannot forget* to be tenant-scoped.
3. **Database RLS:** `SET LOCAL app.tenant_id = ...` per transaction (not
   `SET` — would leak across pooled connections); RLS policy filters every
   row. **Missing context → zero rows, not all rows.** `tenant_id` leading
   index column. `BYPASSRLS` only for migration roles; admin is an explicit
   policy.

The breach scenario (forgotten filter) is caught by the policy engine and,
failing that, by RLS. App scoping is convenience, not the boundary.

### 6.9 Noisy-neighbor / hot-tenant containment

- **Request layer:** per-`(tenant, endpoint)` token-bucket quotas, per-tier;
  overshoot ≤5%/tenant/min on shared pools.
- **Resource layer:** per-tenant DB connection caps + per-tenant statement
  timeouts so an *expensive query* (not just high QPS) can't evict the tail's
  working set. This is the vector pure rate-limiting misses.
- **Placement layer:** **shuffle sharding** for the pooled tail (each tenant
  → small random shard subset, bounding blast radius); **data-driven
  promotion** to dedicated shard/silo above ~1% platform traffic (hourly job
  on observed load, because sales categorization lags real QPS).

Net: a promoted whale is on a silo → tail sees nothing; an un-promoted whale
is quota-throttled, connection-capped, and shuffle-shard-bounded.

### 6.10 Per-tenant routing and its security

- **Owned by tenant, dispatched at request time** from the versioned config.
- **Code-level template map:** fixed, code-reviewed templates keyed by
  enforcement type; **URL host pinned to an internal namespace**. Tenant
  supplies parameters (realm, region selector), **never the host** →
  payload-injected hosts are impossible → SSRF closed by construction.
- **Identity invariants:** PK-enforced one-tenant-per-user (delete-then-
  insert transitions); verified one-domain-one-tenant.
- **O(1) ops:** suspend/retier/region-move = tenant-record write + epoch
  bump; data plane reads epoch on request path; no per-member fan-out.

### 6.11 Multi-region / consistency commitments (CAP, out loud)

- **Control plane: CP.** Tenant identity, domain bindings, tier — strongly
  consistent (Spanner-class). Low QPS; we pay the geo-commit tax because a
  tenant must not exist in two inconsistent states (e.g. two tenants owning
  one domain). Choosing CP here is the right CAP call.
- **Data plane config: AP-ish with bounded staleness.** Tenant config
  propagates eventually (<30s), data plane caches with a version. A
  tenant-config change is not instantaneously global — acceptable, and the
  version bound makes the staleness explicit.
- **Data residency / region-move migration:** re-tier pool→silo in the
  target region — **dual-write + backfill + atomic cutover via the tenant
  epoch** (flip the tenant's region pointer; routing follows the new epoch
  atomically; drain the old). The epoch is what makes the cutover a single
  consistent flip rather than a racey per-record move.

### 6.12 Cost (back-of-envelope; name the dominator)

- **Dominator: per-tenant compute + DB instances.** Siloing all 50k tenants
  = 50k DB instances to provision, patch, back up — the ops + license cost is
  the killer. **Pooling the ~49.5k-tenant tail onto a sharded cluster is the
  lever** — it's the difference between ~500 managed instances (whales only)
  and 50k.
- **Routing/context overhead** is a rounding error (sub-ms cache + RLS).
- The cost argument *is* the isolation argument: tier so you pay for
  isolation only where it's contractually required.

### 6.13 Failure modes & blast radius

| Failure | Blast radius / response |
|---|---|
| Forgotten tenant filter in a query | Caught by policy engine; else RLS returns zero rows. No leak. |
| Pooled connection reused with stale tenant ctx | Prevented by `SET LOCAL` (per-txn); never `SET`. |
| Whale runaway job | Promoted → siloed, tail unaffected. Pooled → quota + conn-cap + shuffle-shard bound the bleed. |
| Control-plane outage (10 min) | Data plane **fails static** on cached config — tenants keep serving; no new onboards/config changes. |
| Tenant suspended | Epoch bump; visible <30s everywhere; O(1), no member fan-out. |
| Two tenants claim one domain | Second `verify` fails on unique PK. Impossible by construction. |
| Tenant injects malicious callback host | Impossible — host pinned to internal namespace; tenant supplies params only. |

### 6.14 Evolution at 10×

- **10× tenants (50k→500k):** pool shards re-split on `hash(tenant_id)`
  (trivial); control-plane DB partitions split; the *promotion threshold*
  re-tunes but the architecture holds. Seam that moves: the silo fleet (more
  whales) — push silo provisioning automation in the control plane.
- **10× per-tenant size:** more whales cross the silo threshold; data-driven
  promotion absorbs it without a redesign.
- **New region / residency regime:** add a region; the pool/bridge/silo +
  epoch-cutover migration is the same mechanism.
- **Org seams (who owns what):** **control-plane team** owns onboarding,
  tenant lifecycle, billing, config store; **data-plane / platform team**
  owns the policy engine, RLS, sharding, and the silo fleet. The versioned-
  config contract between them is the clean handoff. At L6 I'd own the
  isolation contract (policy engine + RLS + routing-template map) personally
  and delegate per-tier provisioning automation.

---

## 7. Signals scorecard

| Hire / Strong Hire (quotable in packet) | No Hire / Down-level (quotable in packet) |
|---|---|
| Split control plane from data plane unprompted; named per-tier p99 and the power-law skew by minute 15. | Hand-waved scale; one global database for 50k tenants; never named the skew. |
| Committed to **tiered** isolation (pool/bridge/silo per data class) with cost + blast-radius defense. | One global isolation model — pool-everything or silo-everything — undefended on cost/compliance. |
| Enforced tenant context in ≥2 layers below the app (policy engine + RLS); named no-rows-not-all-rows. | `tenant_id` column + app-layer `WHERE` only; no backstop; one missing clause = breach. |
| Treated the tenant claim's **provenance** as a security control (signed at auth, never from request). | Read `tenant_id` from a header/body the client controls. |
| Hot tenant: per-tenant quota + connection/query-cost caps + shuffle-shard + data-driven promotion to silo. | "Rate-limit per tenant" only; missed the expensive-query vector; "auto-scale the cluster." |
| Routing from a **code-level template map, host pinned to internal namespace**; rejected payload hosts as SSRF. | Tenant config carries the callback host the platform calls server-side (SSRF). |
| One-tenant-per-user **PK-enforced**, delete-then-insert transitions; verified one-domain-one-tenant. | User belongs to a *list* of tenants; ambiguous routing; no domain verification. |
| Tenant ops **O(1)** via epoch/status bump; no per-member fan-out; <30s propagation. | Suspend/retier writes every member row. |
| `SET LOCAL` (per-txn) called out vs. `SET` leaking across pooled connections. | `SET` session-persistent, or no awareness of pooled-connection context leak. |
| CAP stated: control plane CP (strong), config plane bounded-stale; region-move via epoch cutover. | No consistency commitment; treated config as instantly global. |
| Cost: pooling the tail is the lever; ops bounded to ~500 siloed whales, not 50k. | Treated per-tenant compute/DB as free. |
| Control-plane outage → data plane **fails static** on cached config. | Control-plane outage takes down all tenant traffic. |
| On 10× / residency curveball, identified the seam (silo fleet, epoch cutover), not a redesign. | Treated every new constraint as a redesign. |
| Narrated plan and budget; named what to own vs. delegate across control/data-plane teams. | Drifted; surprised when time was called; no org seams. |

---

*Closing note for the packet.* The three sentences I want to write
themselves from the transcript: **"Committed to tiered isolation and
enforced tenant context in three independent layers — signed claim, policy
engine, RLS with SET LOCAL — naming the no-rows fail-closed property
unprompted."** · **"Contained the hot tenant structurally via per-tenant
query-cost caps, shuffle sharding, and data-driven promotion to silo, not
just QPS limits."** · **"Dispatched per-tenant routing from a code-level
template map with hosts pinned to an internal namespace, rejecting
payload-injected hosts as SSRF, on PK-enforced one-tenant-per-user and
verified one-domain-one-tenant invariants, with O(1) tenant ops."** All
three honestly from the transcript = Hire at L6. With prompting or
reservations = Hire at L5 / Lean No-Hire at L6.

This is the operational/multi-tenant sibling of `05-rate-limiter.md` —
where that guide isolates *traffic*, this one isolates *everything*.

---

## Sources used in preparing this guide

- AWS — *SaaS Tenant Isolation Strategies* whitepaper (silo / pool / bridge,
  noisy-neighbor): https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/pool-isolation.html
  and .../silo-isolation.html and .../the-bridge-model.html
- AWS Well-Architected — *SaaS Lens: Silo, Pool, and Bridge Models*:
  https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/silo-pool-and-bridge-models.html
- AWS — *Control plane vs. application plane* (SaaS Architecture
  Fundamentals): https://docs.aws.amazon.com/whitepapers/latest/saas-architecture-fundamentals/control-plane-vs.-application-plane.html
- AWS — *Tenant routing strategies for SaaS applications on AWS*
  (domain-driven vs. data-driven routing):
  https://aws.amazon.com/blogs/networking-and-content-delivery/tenant-routing-strategies-for-saas-applications-on-aws/
- AWS — *Tenant Onboarding Best Practices* (registration → tenant mgmt →
  tier-based provisioning):
  https://aws.amazon.com/blogs/apn/tenant-onboarding-best-practices-in-saas-with-the-aws-well-architected-saas-lens/
- AWS — *Multi-tenant data isolation with PostgreSQL Row Level Security*:
  https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/
- MVP Factory / techbuddies.io — *PostgreSQL RLS for multi-tenant SaaS*
  (`SET LOCAL` vs `SET`, no-rows failure mode, composite-index performance,
  `BYPASSRLS` caution):
  https://mvpfactory.io/blog/row-level-security-in-postgresql-multi-tenant-data-isolation-for-your-saas
- WorkOS — *The developer's guide to SaaS multi-tenant architecture*
  (isolation models, tenant context propagation):
  https://workos.com/blog/developers-guide-saas-multi-tenant-architecture
- Microsoft Azure Architecture Center — *Considerations for Multitenant
  Control Planes*:
  https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/control-planes
- Practitioner aggregate: techinterview.org *System Design: Multi-Tenant
  SaaS*; Algoroq *Multi-Tenancy Interview Questions for Senior Engineers
  (2026)*; GeeksforGeeks *Multi-Tenancy Architecture*.
