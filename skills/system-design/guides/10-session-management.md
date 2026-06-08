# Question 10: Distributed Session Store / Session-Management Service

> Interviewer's guide for the 1-hour Google L5/L6 system-design round.
> Anchor problem for the **session lifecycle / revocation / multi-device**
> archetype. The prompt is canonical (every auth platform, every "log out
> everywhere" feature, OWASP's session-management cheat sheet, NIST
> 800-63B). The calibration value is *not* whether the candidate knows what
> a JWT is — it's whether they can hold the central tension in their head
> for an hour: **stateless tokens validate cheaply but revoke painfully;
> stateful sessions revoke instantly but cost a lookup on every request.**
> Revocation at scale is the part that separates levels.

---

## 1. Why this question (interviewer's framing)

A session service *looks* like a CRUD problem with a Redis box. A prepared
L4 will say "signed JWT, 15-minute expiry, refresh token, done" and stop.
That answer is not wrong — it is *incomplete in exactly the place the
question is asking about*. The real prompt is: **you are the authority for
who is logged in, across dozens of products and billions of devices; a
security team needs to kill a session in seconds, not minutes; and the
validation path is in front of every authenticated request on the
platform. What do you commit to, and what happens when it fails?**

That forces explicit reasoning on five axes:

- **Validation cost vs. revocation latency.** A signed, self-contained
  token validates with zero network calls — but you cannot un-issue it.
  A server-side session record revokes the instant you delete the row —
  but now every request pays a lookup. This is *the* trade-off, and it
  is not binary: the interesting designs live in the hybrid middle.
- **Revocation at scale (the hard part).** "Log out everywhere," password
  reset, "we think this account is compromised, kill all sessions now,"
  tenant unenrollment. A blocklist of revoked tokens is the L4 reflex and
  it grows without bound. The L6 answer is **O(1) per user**, not O(sessions).
- **Read-heavy, fan-in workload.** Validations outnumber issuances ~1000:1.
  This is not a write-scaling problem; it is a read-scaling + freshness
  problem. The shape drives every caching decision.
- **Multi-device & assurance.** One human, many sessions; a step-up to
  AAL2 for a sensitive action; a "trust this device" bypass. Each is its
  own lifecycle with its own revocation semantics.
- **Multi-tenant identity.** The same user acts inside different orgs; the
  active tenant must ride *inside* the session, not in a parallel cookie
  that can desync. Unenrolling a user from a tenant must kill the right
  sessions and not the wrong ones.

### What "Hire" looks like at each level

**L5 Hire.** Commits to numbers by minute 10 (validations/sec, store size,
validation p99, revocation SLA, token size). Names the stateless-vs-stateful
trade-off explicitly and *picks a side with a reason* — or, better, picks the
hybrid (short stateless access token + stateful refresh/session record) and
defends the expiry window. Designs a Redis-or-equivalent session store with
TTL and sane cookie flags (`HttpOnly`, `Secure`, `SameSite`, `__Host-`).
Handles "what happens when the store is down" calmly. Identifies that a
naive revocation blocklist grows unbounded.

**L6 Hire.** All of the above, plus: **drives the room** (narrates the budget,
pre-ranks the deep dives off the NFRs). Proposes **epoch-bump revocation** — a
monotonic per-user integer that makes "log out everywhere" an O(1) write and a
single integer comparison on validate — *before* being asked how to revoke at
scale. States an explicit **CAP commitment** for the revocation path (you
cannot have instant global revocation *and* a zero-RPC validate; name which
you give up and bound the staleness). Volunteers the **multi-device / step-up /
trusted-device** lifecycles and their distinct revocation rules. Carries the
**tenant as a claim inside the existing session**, not a second cookie.
Surfaces $/month and the dominator. Names what they'd own vs. delegate.

### Classic downlevel traps

1. **"Signed JWT, done" with no revocation story.** The modal L4 answer.
   When pushed — "security needs this user out in 5 seconds" — they either
   shrug ("tokens are short-lived, they'll expire") or invent an
   ever-growing blocklist on the spot. Either way the packet writes itself.
2. **Revocation blocklist sized at O(active sessions).** "We'll keep a set
   of revoked token IDs in Redis." Now you're checking a growing set on
   every request *and* you've reintroduced the lookup you used JWTs to
   avoid — without getting instant per-user revocation. Worst of both worlds.
3. **Stateful session lookup on every request with no caching tier.** A
   single central store doing 1M validations/sec is a hot-keyed SPOF; one
   region-wide blip logs out the entire platform. Missing the local cache
   is an L5-ceiling signal, exactly as in the rate-limiter.
4. **Tenant in a second cookie.** A parallel `active_tenant` cookie desyncs
   from the session cookie on the account-switch / logout edge and becomes a
   privilege-confusion bug. The tenant must be a *signed claim inside the one
   session*.
5. **Sliding-window everywhere.** Auto-refreshing every session on activity
   defeats IdP-enforced max-session-lifetime (the enterprise admin set a
   12-hour cap; your sliding window keeps a tab open for a week). Fixed-window
   for IdP-enforced logins, sliding for native.

---

## 2. The 60-minute plan

Minute-by-minute. What you say, what you listen for, when you push back vs.
stay quiet.

### 0–5 min — Intro

**Say:** *"I'm <name>, L7 on <unrelated infra team>. 60-second bio, then:
design a distributed session store / session-management service. Think the
thing that issues, validates, and revokes sessions for a whole product
suite — many products, many devices per user. You're the authority on who's
logged in. Drive it however you like; I'll interject."*

**Listen for:** do they restate the problem and sit with the ambiguity, or
immediately draw a Redis box? Restating ("so I'm the session *authority*,
not the thing doing the password check?") is an L6 tell.
**Push back when:** they whiteboard before scoping. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** almost nothing. If asked "scale?" → *"Google scale — you tell me
what that means."* If asked "do we do the login itself?" → *"You're the
session authority; assume something upstream attested the identity. What do
you own?"* If asked "revocation SLA?" → *"What would you commit to, and
what does the number cost you?"*

**Listen for:**
- Tight functional commit: issue / validate / refresh / revoke-one /
  revoke-all-for-user / multi-device list. Bonus for explicitly cutting
  the login flow and the IdP federation (that's question 6, not this one).
- NFRs **with numbers**: validations/sec (and the read:write ratio),
  validation p99, revocation propagation SLA, session-store size, token/
  cookie size, availability.

**Push back when:**
- "Highly scalable" with no number → *"Quantify. Validations/sec? Read:write?"*
- No revocation SLA → *"Security wants a compromised account's sessions dead.
  How fast, and what does that number force in your design?"*
- Conflates this with the auth/login service → *"Who attested the identity?
  Assume that's solved upstream."*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip math, *"Before we draw — what does the
math say you need?"*

**Listen for:**
- Worked numbers: validations/sec (peak), issuances/sec, store size
  (sessions × bytes), cache working set, revocation write rate.
- **The number that decides the architecture:** validations are ~1000×
  issuances and sit on every request → this is a read-scaling/freshness
  problem, which is what justifies a stateless-or-cached validate path
  with a *bounded-staleness* revocation signal.
- Box diagram: client cookie → edge/gateway local validate → session store
  (+ per-user epoch table) → revocation propagation. Refresh path separate.

**Push back when:**
- 9 boxes → *"Which are on the request hot path? p99 budget per hop?"*
- Reflexive Spanner-for-sessions → *"What does Spanner cost you at 1M
  validations/sec, and do you need its consistency on this path?"*

### 25–45 min — Deep dives (the diagnostic zone)

Two **mandatory** dives:

1. **Token design: stateless vs. stateful, and the hybrid.** Ask: *"Walk me
   through validating one request. How many network calls? Now revoke that
   session in under 5 seconds. What changed?"*
2. **Revocation at scale.** Ask: *"User clicks 'log out of all devices.' They
   have 40 sessions. Then: 'we think this account is compromised, kill
   everything now.' Walk me through both. What's the data structure?"* This
   is where epoch-bump should appear. If it doesn't, that's a finding.

Third dive — pick on weakness — **multi-device + step-up (AAL) + tenant-scoped
session**: *"Same user, laptop and phone. They step up to AAL2 to change
their bank details on the laptop. They switch active tenant on the phone.
Now revoke. What lives where?"*

**Listen for at L6:** epoch-bump (O(1) revoke-all), bounded-staleness CAP
commit, per-device session rows, AAL2 state in a *secondary* cookie cleared
on revoke, tenant as a claim *inside* the session, fixed vs sliding window
distinction.

**Push back hard** on "blocklist of revoked tokens" (*"how big does that set
get, and what's the lookup cost on the hot path?"*), on "just make tokens
short-lived" (*"so a compromised account is live for your full token TTL?
Security accepts that?"*), on second tenant cookie (*"what happens on logout
if those two cookies disagree?"*).

### 45–55 min — Evolution / curveball

Pick **one**:
- *"Your session store has a region-wide outage for 10 minutes. Walk me
  through what happens to validations and revocations, minute by minute."*
  (Mandatory if not already covered — fail-open/fail-closed by token type.)
- *"10× growth — 10M validations/sec. What breaks first?"*
- *"A tenant admin unenrolls a user from their org. Which sessions die?"*
  (Tenant-scoped revocation; the no-silent-rebind subtlety.)

**Listen for:** seam identification, not redesign. L6 names the 2–3 knobs and
the migration path.

### 55–60 min — Wrap

**Say:** *"That's time. What would you do differently with 15 more minutes?
Then — questions for me?"*

**Still scoring:** self-aware retro ("I didn't get to multi-region replication
lag on the epoch table") and what they ask.

---

## 3. Probing prompts (the kit)

Pre-loaded, with the signal each hunts. Drop verbatim; use silence after.

| Prompt | Signal hunted |
|---|---|
| *"Validations/sec vs. issuances/sec — commit, and the ratio."* | Workload-shape grounding. ~1000:1 read-heavy should drive everything. |
| *"Revocation SLA — how fast must a killed session stop validating?"* | Forces the central trade-off into the open. A number here is load-bearing. |
| *"Validate one request. How many network calls on the hot path?"* | Stateless (zero) vs stateful (one) — do they see the cost? |
| *"Now revoke that exact session in 5 seconds. What changed?"* | The whole question. Stateless answer must produce a revocation mechanism. |
| *"'Log out everywhere' — user has 40 sessions. Data structure?"* | Epoch-bump (O(1)) vs delete-40-rows vs blocklist (O(sessions)). |
| *"How big does your revoked-token set get over a year? Lookup cost?"* | Trap for the blocklist reflex — unbounded growth + hot-path lookup. |
| *"What's in the token vs. what's in the store? Token size in bytes?"* | Claims-design discipline; cookie-size limits (~4KB) matter. |
| *"Compromised account — kill everything NOW. Propagation path?"* | Push-invalidate vs pull-on-validate; bounded staleness named. |
| *"Same user, 3 devices. Revoke one. How are sessions keyed?"* | Per-device session rows, not one blob per user. |
| *"Step up to AAL2 for a sensitive action. Where does that state live?"* | Secondary cookie / elevated claim; cleared on revoke; TTL. |
| *"User belongs to 3 orgs. Where's the active tenant carried?"* | Claim INSIDE the session cookie, not a parallel cookie. |
| *"Tenant admin unenrolls the user. Which sessions die — and not?"* | Tenant-scoped revocation; doesn't nuke other-tenant sessions. |
| *"Sliding or fixed expiry? Does it depend on how they logged in?"* | Fixed-window for IdP-enforced max-lifetime; sliding for native. |
| *"Store is down. Do validations fail open or closed?"* | Per-token-type policy + blast-radius reasoning, not one binary. |
| *"User switches accounts. Does the old session silently rebind?"* | No-silent-rebind: account switch issues a fresh session, never reuses. |
| *"Cost per month at your validation QPS. Dominator?"* | L6 marker; L5s often skip. Store-memory or cache fleet usually dominates. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

Pick **2–3**. For each: phrasing, L5 vs L6 shape, anti-signal, packet quote.

### Deep dive A — Token design: stateless vs. stateful, and the hybrid

**Phrasing.** *"Walk me through validating a single request end to end. How
many network calls? Now I need that exact session dead within 5 seconds —
what changes about your answer?"*

**Strong L5 answer.** Names the trade-off cleanly. Either: (a) **stateful** —
opaque session ID in a `__Host-` cookie, looked up in Redis on each request;
revocation = delete the row, instant; cost = one cache hit (~1ms) per request.
Or (b) **stateless** — signed JWT, validated by signature locally, zero RPC;
revocation = hard, so make tokens short-lived (5–15 min) and accept a
revocation lag equal to the TTL. A competent L5 *picks the hybrid*: short
stateless **access token** (5–15 min, validated locally) + long-lived
stateful **refresh/session record** in the store (rotated on refresh,
revocable instantly). Revocation latency is then bounded by access-token TTL.

**Strong L6 answer.** All of the above, plus the move that earns the level:
the hybrid's revocation lag (= access-token TTL) is *still too slow* for
"compromised account, kill now," so the validate path checks **one cheap,
cacheable freshness signal** — the **per-user epoch** (deep dive B). The
access token carries the epoch it was issued under; validate compares it to
the current epoch (cached locally, refreshed every ~1s). This collapses the
trade-off:
- normal validate is local + signature-only (zero blocking RPC, ~50µs),
- revoke-all is one integer write (epoch bump),
- propagation is bounded by the epoch-cache refresh interval (~1s), not the
  token TTL.

Explicitly states the **CAP commit**: validation is **AP** (you serve from a
locally-cached epoch / signature check; you tolerate up to ~1s of staleness on
revocation rather than block every request on a strongly-consistent read).
Names what flips it: a billing/admin action that *must* see the latest
revocation does a synchronous read-through to the store (CP for that ≤1% of
requests). Commits token sizes: access token ~600–800 bytes (sub, sid, exp,
epoch, aal, tenant claim), well under the 4KB cookie limit; opaque session ID
16–32 bytes.

**Anti-signal.** "Signed JWT, short TTL, done" with no revocation mechanism;
or stateful lookup on every request with no cache tier and no fallback when
the store is down. → Packet: *"Did not produce a revocation mechanism beyond
token expiry; when pushed on a 5-second kill, proposed an unbounded blocklist."*

**Packet quote (Hire).**
> *"Committed to a hybrid: short stateless access token validated locally
> plus a stateful refresh record. Recognized the TTL-bounded revocation lag
> and closed it with a cached per-user epoch checked on validate — zero
> blocking RPC on the hot path, O(1) revoke-all, ~1s bounded staleness.
> Stated AP for validate, CP read-through for billing. Unprompted."*

### Deep dive B — Revocation at scale (the hard part)

**Phrasing.** *"User clicks 'log out of all devices' — they have 40 active
sessions across 6 products. Then a security alert fires: 'this account is
compromised, kill everything now.' Walk me through both. What's the data
structure, and what's the propagation path?"*

**Strong L5 answer.** For per-session logout: delete that session row;
next validate misses, returns 401. For log-out-everywhere: query all
sessions for the user and delete them (a secondary index `user_id →
[session_ids]`), or maintain a per-user `sessions` set and clear it. Names
that a flat blocklist of revoked token IDs grows unbounded and rejects it.
Recognizes the propagation problem if validate is cached.

**Strong L6 answer.** The named mechanism: **epoch-bump revocation.**
- Each user has a row with a **monotonic integer `session_epoch`** (start 0).
- Every issued session/token carries the epoch *at issue time* as a claim.
- On validate, the server compares the token's epoch to the current
  `session_epoch` for that user; **reject any token whose epoch is lower.**
- "Log out everywhere" / "kill all sessions" = **one write: `epoch += 1`.**
  O(1) regardless of session count — 40 sessions or 40,000, same cost. Every
  outstanding token is now stale on its next validate. No fan-out, no
  per-session deletes, no growing blocklist.

Why this beats the alternatives, said out loud:
- **vs. blocklist** (O(revoked tokens), unbounded, hot-path set lookup):
  epoch is O(1) write, O(1) integer compare, bounded storage (one int/user).
- **vs. delete-all-rows** (O(sessions) write, racy with in-flight issuance,
  needs a secondary index): epoch is a single atomic increment.

Propagation & staleness: the current epoch per user is **cached at the
validate tier** (local LRU, ~1s TTL, or pushed via a pub-sub invalidation
stream). So a bump propagates in ≤1s worst case — that's the revocation SLA,
and it's an explicit **bounded-staleness CAP commit**. For the rare
"must-be-instant" path (e.g. an admin revoking their own elevated session),
validate does a synchronous epoch read-through.

The L6 also distinguishes **revocation granularities**, each O(1) or O(small):
- **Single session:** delete the one session row (or per-session tombstone),
  not an epoch bump.
- **All sessions for a user:** epoch bump.
- **Tenant-scoped:** a *per-(user, tenant)* epoch (or a tenant membership
  version checked against the session's tenant claim) — so unenrolling a user
  from org A kills only their org-A sessions, not org-B (deep dive C).

Edge cases the L6 volunteers: clock-free (epoch is an integer, not a
timestamp — no skew issues); refresh rotation bumps nothing (it's not a
revocation); password reset and "compromised" both bump the epoch.

**Anti-signal.** Proposes a revoked-token blocklist and, when asked how big
it gets, says "we'll expire entries with the token TTL" without seeing that
it's still a hot-path lookup over a growing set, or that it gives per-token
not per-user revocation. → Packet: *"Revocation design was an unbounded
blocklist with a hot-path set membership check; did not arrive at an O(1)
per-user mechanism even when prompted."*

**Packet quote (Strong Hire).**
> *"Proposed epoch-bump revocation unprompted: monotonic per-user integer
> carried in the token, rejected on any lower epoch, so 'log out everywhere'
> is a single O(1) write independent of session count. Cached the epoch at
> the validate tier with ~1s bounded-staleness, stated as an explicit AP
> commit, with synchronous read-through for the must-be-instant path.
> Generalized to per-(user,tenant) epochs for tenant-scoped revocation."*

### Deep dive C — Multi-device + step-up (AAL) + tenant-scoped session

**Phrasing.** *"Same user on a laptop and a phone. On the laptop they step up
to AAL2 to change banking details. On the phone they switch their active org.
Now an admin revokes. Walk me through what state lives where, and what each
revocation kills."*

**Strong L5 answer.** Sessions are keyed per device: `session_id` is unique
per login, store row holds `user_id`, `device_id`, `created_at`,
`last_seen`, `expires_at`. A "your devices" list = query sessions by user.
Revoke-one deletes one row; revoke-all clears them. Step-up: re-prompt for
MFA, set a flag on the session. Recognizes one human = many independent
sessions.

**Strong L6 answer.** All of the above, plus the three subtle pieces:

1. **Step-up (AAL2) state in a secondary cookie, cleared on revoke.** The
   base session proves AAL1 (you're logged in). A sensitive action requires
   AAL2; rather than mutate the long-lived session, issue a **short-lived
   secondary cookie / elevated claim** (e.g. 5–15 min, per NIST 800-63B's
   ≤1-hour reauth-for-AAL2 inactivity guidance) that asserts "this session
   reached AAL2 at time T." It is **cleared on any revoke** and expires fast,
   so an elevated window can't be replayed. AAL is a property of the
   *session*, not the authenticator — so it lives in session state, scoped
   tightly.
2. **Tenant carried as a claim INSIDE the existing session cookie — never a
   separate cookie.** The active org is a signed `tenant_id` claim in the one
   session token. A parallel `active_tenant` cookie can desync from the
   session on logout/switch and become a privilege-confusion bug (you're
   "in" org B with org A's auth context). One cookie, signed, atomic.
3. **Tenant-scoped revocation on unenrollment.** When a tenant admin
   unenrolls the user from org A, you must kill the user's *org-A* sessions
   without touching org-B. Mechanism: a **per-(user, tenant) epoch** (or a
   tenant-membership version stamped into the session's tenant claim);
   unenroll bumps that, and validates whose tenant claim is org-A-with-stale-
   version are rejected. Org-B sessions, carrying a different tenant claim,
   are untouched.
4. **No-silent-rebind on account switch.** When a user switches accounts (or
   tenants in a way that crosses an identity boundary), you **issue a fresh
   session** — you never silently rebind the existing session to the new
   identity. Silent rebind is how a stale elevated/AAL2 claim or a trusted-
   device bypass leaks across an identity boundary.
5. **Trusted-device bypass and its revocation.** "Remember this device" skips
   MFA on future logins via a long-lived **device-trust token** (separate
   from the session, bound to `device_id`, independently revocable). It is its
   own lifecycle: revoking sessions does *not* revoke device trust, and
   revoking device trust (e.g. "this laptop was stolen") forces MFA next login
   but doesn't kill the current session unless you also bump the epoch. The L6
   names that these are *two* revocation switches and the security team needs
   both.
6. **Fixed-window vs. sliding-window by login type.** Native logins get a
   **sliding window** (idle timeout extends on activity, capped by an absolute
   timeout — OWASP's "both" recommendation). IdP-enforced logins (an
   enterprise admin set a max session lifetime / SSO policy) get a **fixed
   window with no auto-refresh** — the session dies at the IdP-mandated wall
   clock regardless of activity, because auto-refreshing would silently
   override the tenant's policy.

**Anti-signal.** Tenant in a second cookie; or AAL2 baked permanently into the
long-lived session so the elevated window never closes; or one session blob
per user so you can't revoke a single device. → Packet: *"Carried active
tenant in a parallel cookie, did not see the desync/privilege-confusion risk;
treated step-up as a permanent session flag with no expiry."*

**Packet quote (Hire L6).**
> *"Per-device session rows; active tenant as a signed claim inside the one
> session cookie (explicitly rejected a parallel cookie for desync risk);
> AAL2 step-up in a short-lived secondary cookie cleared on revoke;
> per-(user,tenant) epoch so unenrollment kills only that tenant's sessions;
> fresh session on account switch (no silent rebind). Volunteered the
> fixed-vs-sliding window split for IdP-enforced vs native. Unprompted."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **No revocation mechanism beyond expiry.** "Tokens are short-lived" is not
  a revocation story when security needs a 5-second kill. One prompt; if they
  still can't produce a mechanism, down-level.
- **Unbounded blocklist.** Revoked-token set that grows forever *and* sits on
  the hot path. The classic worst-of-both-worlds.
- **Stateful lookup with no cache / no fallback.** Central store does 1M
  reads/sec and a regional blip logs out the platform.
- **Tenant in a second cookie.** Desync = privilege confusion. Quotable mistake.
- **Step-up as a permanent flag.** AAL2 that never expires = an elevated
  session that can be replayed for hours.
- **Sliding window over IdP policy.** Auto-refreshing an enterprise-capped
  session silently overrides the admin's max-lifetime.
- **Silent rebind on account switch.** Reusing a session across an identity
  boundary leaks elevated/trusted state.
- **No cookie hygiene.** Missing `HttpOnly` / `Secure` / `SameSite` /
  `__Host-` — at L6 this is table stakes, not a footnote.
- **No cost math.** "We'd use Spanner for sessions" with no $/QPS at 1M
  validations/sec.

### Interviewer-side (your own traps)

- **Letting them dwell on JWT-vs-session as a religious debate.** It's a
  5-minute commit. By minute 30 force the revocation scenario — that's where
  the signal is.
- **Leading them to epoch-bump.** Tempting because it's the elegant answer.
  Don't. If they get there alone, that's the L6 finding; if you hand it to
  them, the packet won't write convincingly.
- **Not driving to the "kill now" scenario.** Mandatory. If unprompted by
  minute 40, push.
- **Over-rewarding "we'll use Redis."** Redis is not a signal. "Redis because
  validate is read-heavy and we need ≤1ms p99 on a cached epoch, with Cluster
  for the store and a local LRU tier" *is*.
- **Eating their 3-minute question window.** Still scoring on Googleyness.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it.
Numbers explicit, trade-offs committed.

### 6.1 Functional requirements (committed scope)

v1: **issue** a session (given an upstream identity attestation); **validate**
a session on every authenticated request; **refresh** (rotate) a session;
**revoke one** session (single device logout); **revoke all** for a user (log
out everywhere / password reset / compromise); **list devices** (a user's
active sessions); **step-up** to AAL2 for sensitive actions; carry an **active
tenant** for multi-org users; **tenant-scoped revocation** on unenrollment.

**Out of scope v1, said out loud:** the login/credential check and IdP
federation (that's the auth service — question 6); authorization/RBAC
(we carry an identity + tenant, not a permission matrix); the consent UI.

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| Peak validations/sec | **1M/sec** (global) | Validate is on every authenticated request across the suite. This is the number that shapes everything. |
| Issuances/sec | **~1k/sec** | Logins + refreshes. **Read:write ≈ 1000:1** — this is a read-scaling + freshness problem, not a write problem. |
| Validation p99 (hot path) | **≤1ms** server-side, zero blocking RPC in the common case | It's in front of every request; budget is tiny. |
| Revocation propagation SLA | **≤1s** for "kill now"; ≤ access-token TTL otherwise | The bounded-staleness commit. Drives the cached-epoch design. |
| Session-store size | **~200M concurrent sessions × ~1KB = ~200GB** hot | Per-device rows; fits a sharded in-memory store with replication. |
| Token / cookie size | Access token **~600–800 B**; opaque session ID **16–32 B** | Under the ~4KB cookie limit; claims kept lean. |
| Availability — validate | **99.99%** | If validate is down, the whole platform is down. Higher bar than issue. |
| Availability — issue | **99.9%** | Login can tolerate a brief blip; users retry. |
| Durability | Sessions are **soft state** (re-login recovers); the **epoch table is durable** (Spanner/RDBMS) | Losing a session = re-login; losing an epoch = failing to revoke = a security incident. |

### 6.3 Capacity estimation (worked)

- **Store size.** 200M concurrent sessions × ~1KB (user_id, device_id,
  timestamps, tenant, aal, epoch-at-issue, metadata) = **~200GB**, ×3
  replication = ~600GB. Trivially sharded in-memory.
- **Validate QPS, naive stateful.** 1M/sec central reads, hot-keyed by
  popular users → needs sharding *and* a client-side cache tier. Untenable
  on one primary.
- **Validate QPS, hybrid + cached epoch.** Signature check is local (zero
  RPC). Epoch is cached per-user at the validate tier (local LRU, ~1s TTL).
  Steady-state RPC to the store ≈ epoch-cache misses ≈ (active users /
  refresh interval). At ~50M active users / 1s ≈ negligible per node after
  batching. **The hot path makes ~0 blocking calls.**
- **Epoch table.** One int (plus per-tenant epochs) per user. 1B users ×
  ~100B = ~100GB durable, low write QPS (only on revoke), high read QPS
  served from cache. Spanner-sized comfortably; writes are cheap.
- **Cookie/egress.** 1M/sec × ~800B token echoed in headers — header
  overhead, not a storage cost.

**Numbers that changed a design choice:**
- 1000:1 read:write → validate must be local; revocation must be a *cached
  signal*, not a blocking read.
- ≤1ms p99 → no synchronous store call on the common validate path.
- ≤1s revocation SLA → epoch cache TTL = 1s (or pub-sub push for faster).
- 200GB hot → in-memory store (Redis-Cluster-shaped), not a disk DB.

### 6.4 API design

```
POST   /v1/sessions            { identity_attestation, device_info, tenant?, aal }
                               (called by the auth service after login)
                               → 201 { session_cookie (signed), refresh_token }
GET    /v1/sessions/validate   Cookie: __Host-sid=...     (hot path)
                               → 200 { user_id, tenant_id, aal, epoch } | 401
POST   /v1/sessions/refresh    { refresh_token }          (rotates; checks epoch)
                               → 200 { new access token } | 401 (revoked)
DELETE /v1/sessions/:sid       (single-device logout)
POST   /v1/users/:uid/revoke-all   (epoch += 1; log out everywhere)
POST   /v1/users/:uid/step-up      { aal2_proof } → sets short-lived elevated cookie
GET    /v1/users/:uid/sessions     (the "your devices" list)
POST   /v1/users/:uid/tenants/:tid/unenroll  (per-(user,tenant) epoch += 1)
```

Validate is the only hot-path call and it is designed to make zero blocking
network calls in the common case (local signature + locally-cached epoch).

### 6.5 Data model

- **`sessions`** (in-memory, sharded by `hash(user_id)`, 3× replication, TTL):
  row key `session_id`; columns `user_id`, `device_id`, `tenant_id`,
  `aal`, `epoch_at_issue`, `created_at`, `last_seen`, `expires_at`,
  `login_type` (native | idp_enforced). TTL = absolute timeout.
- **`user_epoch`** (durable, Spanner/RDBMS): row key `user_id`, column
  `session_epoch` (monotonic int). Read-heavy → cached at validate tier.
- **`user_tenant_epoch`** (durable): row key `(user_id, tenant_id)`, column
  `epoch`. Bumped on unenrollment for tenant-scoped revocation.
- **`device_trust`** (durable): `(user_id, device_id) → trust_token, expiry`.
  Independent lifecycle; revoking sessions ≠ revoking device trust.

**The access token (signed JWT-shaped) carries:** `sub` (user_id), `sid`
(session_id), `tid` (tenant_id claim — *inside* this token, not a second
cookie), `aal`, `epoch` (the user_epoch at issue), `tenant_epoch`, `exp`
(5–15 min). Signed with a rotating key (KMS); rotation = a system-wide
revocation backstop.

**Why in-memory store + durable epoch:** sessions are soft state (re-login
recovers), so we optimize them for read speed and accept that a store loss
just forces re-login. The epoch table is the *security-critical durable
truth* — losing it means failing to revoke, so it lives in a durable,
strongly-consistent store. **Why not Spanner for sessions:** at 1M
validations/sec the Paxos write cost and per-read latency are unjustified for
soft state; we'd pay 5–10× for consistency we don't need on this path. Spanner
*does* hold the epoch table, where its low write QPS and strong consistency
earn their keep.

### 6.6 High-level architecture

```
        ┌──────────────────────────────────────────────────────┐
        │  Client (browser / app)                               │
        │  __Host-sid cookie (signed access token, ~800B)       │
        │  + short-lived AAL2 cookie (when elevated)            │
        └───────────────────────┬──────────────────────────────┘
                                 │  every authenticated request
                       ┌─────────▼──────────┐
                       │  Edge / API Gateway │   <── validate happens HERE
                       │  (stateless)        │       (local, zero blocking RPC)
                       │  ├ verify signature │
                       │  ├ epoch >= current?├──┐ local LRU epoch cache (~1s TTL)
                       │  └ aal / tenant ok? │  │
                       └─────────┬───────────┘  │ miss / refresh
                                 │ valid          ▼
                                 │        ┌───────────────────┐
                                 │        │  Epoch Cache Tier  │
                                 │        │  (pub-sub fed)     │
                                 │        └─────────┬──────────┘
              issue / refresh    │                  │ on miss
              (cold path, ~1k/s) │        ┌─────────▼──────────┐
        ┌──────────────────┐     │        │  user_epoch (Spanner│
        │  Session Service │◄────┘        │  durable, strong)   │
        │  ├ create row    │              │  user_tenant_epoch  │
        │  ├ rotate refresh│              └─────────┬──────────┘
        │  └ revoke (bump) ├──────────────────────► │ bump epoch
        └────────┬─────────┘   revoke-all = 1 write │
                 │                                   │ pub-sub invalidation
        ┌────────▼─────────┐                ┌────────▼──────────┐
        │  Session Store   │                │  Revocation Stream │
        │  (Redis-Cluster  │                │  (push bumps to    │
        │  shaped, ~200GB, │                │   epoch cache tier)│
        │  3× repl, TTL)   │                └────────────────────┘
        └──────────────────┘
```

The design's whole point: **validate is local**, **revoke is one durable
write**, and the **pub-sub revocation stream** closes the gap between them
to ≤1s.

### 6.7 Token design — the hybrid, defended

**Decision: short stateless access token + stateful refresh/session record +
cached per-user epoch on validate.**

- **Access token** (5–15 min, signed): validated locally — signature +
  `exp` + `epoch >= current_epoch` + `tenant_epoch` + `aal` sufficient for
  the route. **Zero blocking RPC** in the common case.
- **Refresh / session record** (stateful, in store): rotated on each refresh
  (rotation detects token theft — a reused old refresh token = revoke the
  family). Long-lived, instantly revocable by deleting the row.
- **Epoch check** is what makes the short TTL *not* the revocation floor:
  a bump invalidates every outstanding token in ≤1s regardless of TTL.

**CAP commit, stated:** validate is **AP** — it serves from a locally-cached
epoch and tolerates ≤1s revocation staleness rather than block on a strongly
consistent read. The ≤1% of requests that must see the absolute latest
revocation (admin self-revoke, high-value money movement) do a synchronous
read-through to Spanner (**CP** for that slice). *This is the trade-off the
whole question is about, and it's named.*

### 6.8 Revocation at scale (epoch-bump)

The mechanism, in full (see deep dive B):
- per-user monotonic `session_epoch`; token carries epoch at issue; validate
  rejects any lower epoch.
- **revoke-all = `epoch += 1`** — O(1), independent of session count.
- **single-device revoke** = delete the one session row (no bump).
- **tenant-scoped revoke** = bump `user_tenant_epoch[(user, tenant)]`.
- bumps pushed via pub-sub to the validate tier's epoch cache → ≤1s.
- **rejected: the blocklist** (O(revoked) growth + hot-path set lookup +
  only per-token granularity).

### 6.9 Multi-device, step-up, tenant (see deep dive C)

- Per-device session rows; "your devices" = query by user.
- AAL2 step-up in a **short-lived secondary cookie**, cleared on revoke.
- Active tenant = a **signed claim inside the one session cookie**.
- **No silent rebind** on account switch — always a fresh session.
- **Trusted-device** bypass = a separate, independently-revocable token.
- **Fixed window** (no auto-refresh) for IdP-enforced logins; **sliding
  window** (idle + absolute cap) for native.

### 6.10 Multi-region

CAP commits, said out loud: **validate AP, epoch table CP-ish (strong within
region, async cross-region), sessions AP.**

- **Validate:** active-active; signature check is region-independent; epoch
  cache is regional, fed by a global revocation stream. A revoke in region A
  propagates to region B's epoch cache in pub-sub time (typically <2s
  cross-region) — so the ≤1s SLA is per-region; cross-region revocation
  staleness is bounded and *stated*.
- **Epoch table:** Spanner (globally strong) so a bump is never lost. The
  read path is cached regionally; the *write* is globally consistent because
  a missed revocation is a security incident.
- **Sessions:** issued in the user's home region; replicated async. A session
  created in EU may not be visible in US for a few seconds — acceptable, the
  user is in one region at a time.

### 6.11 Cost (back-of-envelope, monthly)

Public-cloud pricing as a proxy at the 6.2 numbers:

| Component | Notes | $/mo |
|---|---|---|
| Session store (in-memory, ~600GB w/ repl) | ~50 nodes for 200GB hot + replication | ~$60k |
| Epoch cache / validate fleet | ~stateless Borg, ~500 cores | ~$15k |
| Epoch table (Spanner) | low write QPS, modest size | ~$10k |
| Revocation pub-sub stream | bumps only, tiny volume | <$2k |
| **Total** | | **~$87k/mo** |

vs. a **Spanner-for-every-session** equivalent at ~$600k–$900k/mo (paying
strong consistency on 1M reads/sec we don't need). The ~7–10× delta is the
whole reason sessions are soft state in an in-memory store while only the
epoch is durable+strong. **Dominator:** the in-memory store fleet.

### 6.12 Failure modes & blast radius

| Failure | Effect | Mitigation / policy |
|---|---|---|
| Session store region down | Validates for sessions only in that store fail | Validate is signature+epoch local → **stateless tokens keep validating** (fail-open for read paths); only refresh/issue needs the store |
| Epoch table / Spanner down | Can't *write* new revocations; reads served from cache | **Fail-closed on the revoke path** (a revoke must not silently no-op); validate keeps using last-known epoch |
| Epoch cache stale / pub-sub lag | Revocation slower than 1s | Bounded by cache TTL; the must-be-instant slice does synchronous read-through |
| Signing key compromised | All tokens forgeable | KMS key rotation = system-wide revocation backstop; short TTL limits the window |
| Validate fleet overload | p99 climbs | Stateless → autoscale horizontally; no shared bottleneck on the common path |

**Fail-open vs fail-closed, per path:** *validate* fails open (a session-store
blip must not log out the platform — the signature+cached-epoch check still
works); the *revoke* path fails closed (a revocation must never silently
succeed-as-noop, because that's a security hole). This split is the L6 commit.

**SLO/error budget.** 99.99% validate → 4.32 min/mo. Page at 10× burn. Issue
SLO (99.9%) separate so login incidents don't burn the validate budget.

### 6.13 Evolution at 10× (10M validations/sec)

- **Validate:** unchanged in shape — it's stateless and local; autoscale the
  fleet linearly. The whole architecture exists so this number scales cheaply.
- **Session store:** add shards linearly; `hash(user_id)` keeps distribution
  even.
- **Epoch cache:** larger per-node LRU; pub-sub fan-out widens. The named seam:
  if revocation volume grows, shorten cache TTL or move fully to push.
- **Epoch table:** read QPS is cache-absorbed; write QPS (revokes) is low even
  at 10×. Spanner unchanged.
- **Cost:** ~linearly to ~$700k/mo — still <2× a Spanner-from-day-1 design at
  *1×* scale.

**What does not change:** the token shape, the epoch mechanism, the validate
contract, the AP/CP split. The seams named at v1 are the seams at 10×.

### 6.14 What I'd own vs. delegate

I'd personally own the **token/claims contract** and the **epoch revocation
semantics** (they're the security-critical invariants the whole platform
depends on). I'd delegate the **session store operation** to the team that
already runs our in-memory KV fleet, and the **pub-sub revocation stream** to
the messaging-infra team. The **device-trust and step-up flows** are a natural
handoff to the auth/identity team that owns MFA.

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence. Right is the level call.

| Evidence | Call |
|---|---|
| No revocation SLA after two prompts; "highly scalable session store" with no numbers; validate path undefined. | **Strong No Hire** |
| "Signed JWT, short TTL, done." When pushed on a 5-second kill, proposed an ever-growing revoked-token blocklist with a hot-path set lookup and didn't see the unbounded growth. | **No Hire** |
| Stateful session lookup on every request, single central store, no cache tier; when asked about store outage, "everyone gets logged out." Saw the trade-off but only one side of it. | **Lean No Hire** |
| Committed to 1M validations/sec, ≤1ms p99, 1000:1 read:write by minute 10. Named the stateless-vs-stateful trade-off and picked the hybrid (short access token + stateful refresh) with a defended TTL. Cookie hygiene correct. Recognized the blocklist grows unbounded and rejected it. Didn't reach an O(1) revoke-all even when prompted. | **Hire L5** |
| All of L5-Hire, **plus**: arrived at a bounded revocation mechanism (per-user version / cached signal) when prompted; stated a bounded-staleness commit; handled multi-device with per-device rows; correct fail-open/fail-closed instinct on store outage; some cost reasoning. | **Hire L5 / Lean L6** |
| All of the above **unprompted**, **plus**: proposed **epoch-bump revocation** (monotonic per-user int, reject lower epoch, O(1) revoke-all) before being asked how to revoke at scale. Stated the **AP-validate / CP-read-through** CAP commit explicitly with a ≤1s staleness number. Carried tenant as a claim **inside** the session and rejected a second cookie with the desync reason. AAL2 in a short-lived secondary cookie cleared on revoke. Surfaced $/mo with the dominator. Named the fixed-vs-sliding window split for IdP vs native. | **Hire L6** |
| Everything in L6, **plus**: generalized epoch to **per-(user,tenant)** for tenant-scoped unenrollment without nuking other tenants' sessions; called out **no-silent-rebind** on account switch and trusted-device as a *separate* revocation switch; defended the in-memory-store-but-durable-epoch split against my "why not Spanner for everything" pushback with a 7–10× cost argument; named what they'd own (claims contract, epoch semantics) vs. delegate (store ops, pub-sub); closed with a self-aware retro. | **Strong Hire L6** |

---

## Sources used in preparing this guide

- OWASP — *Session Management Cheat Sheet* (cookie flags, absolute + idle
  timeout, server-side enforcement):
  cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- NIST SP 800-63B (rev 4) — *Digital Identity Guidelines: Authentication &
  Authenticator Assurance Levels* (AAL2, step-up, ≤24h reauth / ≤1h
  inactivity, AAL is a session property):
  pages.nist.gov/800-63-4/sp800-63b.html and .../sp800-63b/aal/
- OneUptime — *How to Handle JWT Revocation* (blocklist vs versioning vs
  short-TTL+refresh; logout-everywhere via version bump):
  oneuptime.com/blog/post/2026-02-02-jwt-revocation/view
- Descope — *Stateless Authentication / How to Invalidate a JWT After Logout*
  (stateful-vs-stateless trade-off, revocation lag):
  descope.com/learn/post/stateless-authentication,
  descope.com/blog/post/jwt-logout-risks-mitigations
- Clerk — *The future of authentication is both stateful and stateless*
  (the hybrid pattern: short stateless access token + revocable server record):
  clerk.com/blog/future-of-auth-stateless-and-stateful
- WorkOS — *Session management best practices* (sliding vs absolute, refresh
  rotation, theft detection): workos.com/blog/session-management-best-practices
- Redis — *Session management* solutions + community patterns (TTL, Cluster,
  multi-device keying): redis.io/solutions/session-management/
- DZone — *Scalable JWT Token Revocation in Spring Boot* (token-version /
  user-epoch approach as the scalable alternative to per-token blocklists):
  dzone.com/articles/scalable-jwt-token-revocation-in-spring-boot

---

*End of guide. Related:* `06-sso-auth-service.md` *(the auth service that
attests identity and calls this one to issue sessions) and* `09-multi-tenant-saas.md`
*(tenant isolation, where the per-(user,tenant) epoch and tenant-claim-in-cookie
patterns recur).*
