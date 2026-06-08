# Question 11: Data-Residency Routing & Live Region Migration for a Global SSO (geo-partitioned multi-region + live migration)

> Interviewer's guide for the 1-hour Google L5/L6 system-design round.
> Anchor problem for the **geo-partitioned multi-region + live-migration**
> archetype. The framing is a real-world-derived scenario: a company runs a
> single-region SSO in the US; to comply with EU GDPR data-residency rules,
> EU users' data (credentials, PII, sessions) must *live* in the EU. The
> system becomes geo-partitioned with a per-user `home_region ∈ {US, EU}`.
> The calibration value is *not* whether the candidate can spell "GDPR" — it
> is whether they can hold one cruel tension for an hour: **to route an
> unauthenticated login you need a global identity→region lookup, but
> globally replicating EU PII to the US is exactly the residency violation
> you are being paid to prevent.** The strong answer designs a
> *privacy-preserving global routing directory*. The candidate who replicates
> the full user table everywhere has missed the entire question.
>
> Builds directly on `06-sso-auth-service.md` (session authority,
> attestation handoff, fail-closed) and `10-session-management.md`
> (epoch-bump revocation, the cookie as a signed claim carrier). Reuse that
> vocabulary; do not re-derive it.

---

## 1. Why this question (interviewer's framing)

This *looks* like "add a second region for latency." A prepared L4 will draw
two cells, a global load balancer, and `home_region` on the user row, and
stop. That is a clean answer to a different question. The real prompt has
three problems stacked on top of each other, and the hardest one is invisible
until you try to route a login:

- **Routing an *authenticated* request is easy** — the session cookie is
  present and can carry a region *hint*; you read it at the edge and send the
  request to the cell that owns the session. (Deep dive A.)
- **Routing an *unauthenticated* request is the trap.** Login and register
  arrive with no session — identity is at most an email. Login must reach the
  region that owns *that email's account*. So you need a global lookup:
  email → home_region. But the obvious implementation — replicate the user
  directory everywhere — **puts EU users' raw emails in the US**, which is the
  residency violation you are enforcing. This is the crux of the whole
  question. (Deep dive B.)
- **Migration is the second trap.** You have to move existing users between
  regions *live* — and there's a giant backfill: the US region today holds
  millions of users, many of whom are really EU and will declare so. Moving a
  live account without data loss or **split-brain** (both regions think they
  own the user) is a per-user distributed transaction. (Deep dive C.)

**The L6 crux, stated plainly.** The separator on this question is whether the
candidate sees that *the global routing directory must not contain PII*. The
strong move: store a **pseudonymous key → region** mapping — `hash_HMAC(
normalized_email) → {US|EU}`, or an opaque routing token — never the raw
email, name, or credential. The directory is allowed to be global because it
holds no personal data (or holds it under a data-minimization argument you can
defend to a DPO). The candidate who says "we'll just replicate the users
table to both regions for the lookup" has, in one sentence, recreated the
exact violation the project exists to fix. That sentence is packet-quotable as
a No-Hire. The candidate who reaches "global directory, but it's pseudonymous
by construction" — *that* is the Hire-L6 quote.

### Two terms the candidate must not blur

- **Data residency** = where the data physically *sits* (we commit EU PII to
  EU storage). **Data localization** = a harder legal claim that the data may
  *never leave* the jurisdiction even transiently. GDPR is closer to residency
  + transfer-restriction than to strict localization; an L6 names which one
  we're designing for, because it changes whether even a *hashed* identifier
  crossing the border is acceptable.
- **`home_region` is about data residency, not the user's physical location.**
  An EU user traveling in San Francisco still authenticates against the EU
  cell and pays the ~85ms transatlantic tax. Residency follows the *account*,
  not the *request origin*. Candidates who route by request geo-IP have
  misunderstood the requirement and built a latency optimizer, not a
  compliance system.

### What "Hire" looks like at each level

**L5 Hire.** Commits to numbers by minute 12 (DAU, logins/sec, validations/
sec, EU/US split, US↔EU RTT). Draws two regional cells with per-region session
+ user stores and `home_region` on the user. Routes authenticated requests via
a cookie hint read at the edge. Recognizes that login needs a global lookup
and proposes one. Describes a migration as "copy the data, flip the pointer."
Handles "what if the hint is stale after migration" when asked.

**L6 Hire.** All of the above, *plus*: **sees the PII-in-the-directory trap
unprompted** and designs the directory pseudonymous-by-construction (hashed
key → region, no raw email); treats the directory write as the **global
serialization point** for email uniqueness so no globally-strong store sits on
the login hot path; designs migration as an **idempotent, resumable,
rollback-safe per-user state machine** whose commit point is the atomic
directory flip, with a redirect tombstone in the source and **epoch-bump
session revocation** (from `10-session-management.md`) to force re-login;
defaults undeclared backfill users to US but **names the GDPR risk of relying
on that default**; states the CAP commitment per path (directory reads AP and
locally-cached; the directory flip and email-uniqueness CP); and volunteers
the third-region (APAC) and directory-outage failure stories before being
asked.

### Classic downlevel traps

1. **Replicate the user table globally for the login lookup.** The modal
   failure and the one that matters most. It "works," it's simple, and it
   ships EU PII to the US. If the candidate proposes it and doesn't catch it
   after one prompt ("what's in that replicated table?"), it's packet-fatal at
   L6 and a serious ding at L5 — the question is *literally about not doing
   this*.
2. **Route by request geo-IP / Accept-Language.** Confuses physical location
   with residency. An EU user in the US gets routed to US, and now you've
   either split their data or served them from the wrong cell. Residency is a
   property of the account.
3. **Put a globally-strong store (Spanner-class) on the login hot path** to
   answer "which region owns this email." Correct on consistency, wrong on
   latency and cost — every login now eats a cross-region quorum read. The
   directory should be locally-readable with bounded staleness; only the
   *write* (registration, migration flip) needs global serialization.
4. **Migration as "copy then switch" with no state machine.** No idempotency,
   no resume-on-crash, no rollback, no split-brain guard. The first prod crash
   mid-migration leaves a user owned by both regions or neither. "It's a
   one-time copy" is the tell that they haven't operated a live migration.
5. **Trust the cookie region hint as authoritative.** The hint is a
   performance optimization. After a migration the hint says US but the owner
   is now EU. If the hint is the source of truth, the user hits a dead/
   read-only account. The owning region (via the directory) is authoritative;
   the hint is a guess you verify.

---

## 2. The 60-minute plan

`0–5 Intro · 5–15 Requirements & scope · 15–25 Capacity + high-level
design · 25–45 Deep dives · 45–55 Evolution / curveball · 55–60 Wrap`.

### 0–5 min — Intro

**Say:** *"I'm <name>, L7 on <unrelated infra team>. 60-second intro from you,
then: you run a single-region SSO in the US — it stores sessions, validates
logins, issues sessions, and handles registration, all in the US. To comply
with EU GDPR data-residency rules, EU users' data — credentials, PII, sessions
— now has to live in the EU. Residency is self-declared: the user says US or
EU and you believe them. Design the geo-partitioned system and the migration
to get there. Drive it however you like; I'll interject."*

**Listen for:** do they restate the three sub-problems (routing authenticated,
routing unauthenticated, migrating)? Do they ask whether `home_region` follows
the *account* or the *request*? That question is the highest-value early
signal on this question. **Push back when:** they start drawing cells before
asking what "residency" actually constrains. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** little. If asked "what data is in scope for residency?" → *"PII,
credentials, and sessions for EU users live in the EU. You tell me what that
forces."* If asked "do we re-validate the user's declared region?" → *"No —
self-declared and trusted for v1; flag it if you think that's a risk."* If
asked "how many existing users?" → *"Hundreds of millions, all currently in
US, and a meaningful fraction are really EU."*

**Listen for:**
- Functional commit: route authenticated requests to the owning cell; route
  login to the cell owning the email; register/provision in the declared
  region; migrate a user between regions live; backfill the existing US
  population. Bonus for explicit cuts (no new product features, no change to
  the *auth protocol* — that's `06`/`07` — no GDPR DSAR tooling beyond
  delete-propagation in v1).
- The **PII-in-directory question surfaced here** unprompted: "the login
  lookup needs to be global, but it can't carry EU PII." If they say this in
  scoping, note it — it's the strongest possible early signal.
- Numbers: DAU, logins/sec, validations/sec (read-heavy), EU/US split,
  directory record size + total size, directory lookup p99, US↔EU RTT,
  migration throughput, session/cookie size, backfill population.

**Push back when:** "we'll just add a region" with no residency reasoning →
*"What specifically is not allowed to be in the US after this?"* · they treat
residency as request-routing → *"An EU user is physically in Texas right now.
Which cell authenticates them, and why?"* · 10 functional reqs →
*"Smallest useful v1? Is the migration in v1 or later?"*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip math → *"What does the EU/US split and
the RTT tell you about where the login hot path can afford to go?"*

**Listen for:**
- Worked numbers: logins/sec (write-ish, cold), validations/sec (read, hot),
  directory size (one small record per user → fits in memory, globally
  replicable *because* it's tiny and PII-free), directory lookup p99
  (single-digit ms, served locally), US↔EU RTT ~80–90ms as the tax on any
  cross-region hop.
- Box diagram: two regional cells (each = auth service + session store + user/
  credential store), a **global routing directory** (pseudonymous key →
  region), and **edge/anycast routing** that reads the cookie hint and the
  directory.
- The directory framed as a *force*: it's the one global component, and the
  whole design hinges on it being PII-free so it's *allowed* to be global.

**Push back when:** reflexive "replicate the users table" → *"What columns are
in that replica, and which jurisdiction are they now sitting in?"* · reflexive
"Spanner for the directory" → *"What's the per-login latency if every login
does a cross-region strong read? You said RTT is ~85ms."*

### 25–45 min — Deep dives (the diagnostic zone)

**Three mandatory** (A, B, C). B is the crux; do not let them skip it.

1. **Routing authenticated requests** (A) — *"A logged-in EU user makes a
   request from the US. The cookie's here. Walk me through how the request
   reaches the right cell — and what happens when the hint is stale after a
   migration."*
2. **Routing unauthenticated requests: login + register** (B, the crux) —
   *"Now they're logged out and typing their email into the login box. No
   session. How does the request reach the cell that owns their account —
   without the EU user's email ever living in the US? And how do you stop two
   regions from both registering the same email?"*
3. **Migration + the backfill** (C) — *"Move one existing US user to the EU,
   live, no data loss, no split-brain. Then: you have 300M existing US users
   and ~25% are really EU. Migrate them."*

**Listen for at L6:** pseudonymous directory (hashed key → region); directory
write as the uniqueness serialization point; migration state machine with an
atomic flip as the commit point + redirect tombstone + epoch-bump revocation;
backfill default-to-US with the named GDPR risk; CAP commit per path.

**Push back hard** on PII in the directory (*"a US engineer queries the
directory — can they see a single EU user's email? If yes, you've shipped the
violation"*), on stale-hint trust (*"the hint says US, the user moved to EU
last night — where does this request land?"*), and on migration with no
rollback (*"the copy is half done and the box crashes — who owns the user
now?"*).

### 45–55 min — Evolution / curveball

Pick **one** (the directory-outage one is near-mandatory):

- *"The global routing directory has a region-wide outage for 10 minutes. Walk
  me through what happens to logins, minute by minute. Fail open to the
  last-known hint, or fail closed?"*
- *"Add a third region — APAC. What changes in the directory, the routing, and
  the migration machine? What does NOT change?"*
- *"A user declares EU at 2pm while holding an active US session — and legal
  has placed a hold on their US data. Now what?"*
- *"Right-to-be-forgotten: a migrated EU user requests erasure. Where does the
  delete have to land, including the tombstone and the directory?"*

**Listen for:** seam identification vs. redesign; fail-open/closed reasoned
per path with blast radius; the APAC case adding a *region value*, not a
redesign; RTBF propagating to the source tombstone *and* the directory.

### 55–60 min — Wrap

**Say:** *"Time. What would you do with 15 more minutes? Then — questions for
me?"* **Still scoring:** self-aware retro ("I didn't cover directory key
rotation, or rebalancing if EU outgrows US") and the shape of their questions.

---

## 3. Probing prompts (the kit)

Pre-loaded; each hunts one signal. Drop verbatim, then use silence.

| Prompt | Signal hunted |
|---|---|
| *"Does `home_region` follow the account or the request? EU user in Texas — which cell?"* | Residency-vs-location. Account-bound = correct; geo-IP routing = misunderstanding. |
| *"Commit to numbers: DAU, logins/sec, validations/sec, EU/US split, US↔EU RTT."* | Unprompted numbers; RTT and split are load-bearing on the login path. |
| *"Login arrives with just an email, no session. How do you find the owning region?"* | Forces the global-lookup problem into the open. |
| *"What's stored in that global lookup — exactly which columns?"* | **The crux.** Raw email = violation; hashed key/opaque token = L6. |
| *"A US-region engineer queries the directory. Can they recover a single EU user's email?"* | Data-minimization as a property, not a promise. |
| *"Register: two people hit US and EU with the same email at the same instant. Who wins?"* | Global uniqueness; the directory write as serialization point. |
| *"Do you put a globally-strong store on the login hot path? What's the per-login latency then?"* | CP-on-hot-path trap; AP-read + CP-write split. |
| *"Authenticated request, cookie present. Where's the region read, and is the hint trusted?"* | Edge hint as optimization, owner as authority. |
| *"The hint says US; the account migrated to EU last night. Where does the request land?"* | Stale-hint handling; redirect/re-route, don't trust blindly. |
| *"Migrate one user, live. The copy is half done and the process crashes. Who owns them?"* | Idempotent, resumable, split-brain-safe state machine. |
| *"What is the exact commit point of a migration — the instant ownership changes?"* | The atomic directory flip; everything else is before/after it. |
| *"After the flip, the user has 3 live US sessions. How are they invalidated?"* | Epoch-bump revocation (`10-session-management.md`); force re-login. |
| *"300M existing US users, ~25% really EU. What's the default region, and what's the risk?"* | Backfill default-to-US + the named GDPR exposure of relying on it. |
| *"Directory region-wide outage for 10 min. Logins — fail open to last hint, or closed?"* | Fail-open/closed per path with blast radius. |
| *"Add APAC. What changes vs. stays the same?"* | Seam identification; region as a value, not a rewrite. |
| *"RTBF on a migrated EU user — where does the delete land?"* | Erasure across cells, tombstone, and the directory. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

All three are mandatory. **B is the crux** — steer there and do not let them
hand-wave the PII question.

### Deep dive A: Routing authenticated requests (cookie hint vs. authoritative owner)

**Phrasing.** *"A logged-in EU user is physically in the US and makes a
request. The session cookie is present. Walk me through how the request
reaches the cell that owns the session — and then: that user migrated from US
to EU last night, so their cookie's hint still says US. Where does this request
land, and is that a problem?"*

**Strong L5 answer.** The session cookie carries a region hint — a small
cleartext prefix (e.g. `eu.<opaque-sid>` or a `region=EU` segment) that the
edge / global LB can read *without* decrypting anything. Edge routing (GFE /
anycast) reads the hint and forwards to that region's cell, where the session
store validates the opaque session ID. Inside the signed session payload
there's also a region claim, so even if the cleartext prefix is tampered with,
the owning cell verifies against the signed claim. Names that validation is
the hot, read-heavy path (~1000:1 vs. logins) and stays region-local — no
cross-region hop in the common case. Recognizes the stale-hint case exists
when prompted: if the hint sends the request to US but the session isn't there,
US returns a redirect to EU.

**Strong L6 answer.** All of the above, *plus* the boundary stated crisply:
**the hint is a performance optimization; the owning cell is authoritative.**

- **Hint is cleartext-readable at the edge, claim is signed inside.** The edge
  must route *without* trusting anything secret, so the region lives as a
  cleartext routing prefix the LB reads in O(1). The *authoritative* region is
  the signed claim inside the session (and ultimately the directory). The edge
  hint can be wrong (stale, spoofed); the design must never break when it is.
- **Stale-hint-after-migration, handled by construction.** When a user
  migrates US→EU, the old US cookie's hint still says US. Two clean options,
  and the L6 picks and defends: (a) **epoch-bump the session at migration** so
  the old US cookie is *invalid everywhere* — the next request is a fresh login
  that routes correctly and re-issues a cookie hinted EU; or (b) leave a
  **redirect tombstone** in US (deep dive C) so a request that lands on US gets
  a `307` re-route to EU plus a `Set-Cookie` that rewrites the hint to EU.
  Both make the *first* post-migration request pay one extra hop (~85ms once),
  then it's local forever. The L6 names this as a deliberate, bounded cost, not
  a bug.
- **Never trust the hint for authorization.** A spoofed `region=EU` prefix just
  routes the request to EU, where the EU cell either has the session (fine) or
  doesn't (401 / redirect). The prefix is a *routing hint*, never a *trust*
  signal — same discipline as not trusting IdP claims pass-through in `06`.
- **Validation stays local, sized for the read skew.** At ~1000:1 read:write,
  the design's job is to keep validation a region-local O(1) check (signature +
  cached epoch, per `10-session-management.md`), so the cross-region machinery
  sits entirely off the hot path.

**Anti-signal.** "We read the cookie's region and route there, done" — with the
hint treated as authoritative and no stale-hint story. → Packet: *"Treated the
cookie region hint as the source of truth; after a migration the user would
hit a dead/wrong cell. Did not separate the cleartext routing hint from the
authoritative signed claim."*

**Packet quote (Hire).**
> *"Session cookie carries a cleartext region hint the edge reads in O(1) for
> routing, plus a signed region claim inside; stated unprompted that the hint
> is an optimization and the owning cell is authoritative. Handled the
> stale-hint-after-migration case via epoch-bump + redirect tombstone — first
> post-migration request pays one ~85ms hop, then local. Refused to treat the
> hint as a trust signal."*

### Deep dive B: Routing unauthenticated requests — login + register (THE CRUX)

**Phrasing.** *"Now the user is logged out, typing their email into the login
box. There is no session — identity is at most an email. The request has to
reach the cell that owns that account. How? And the hard constraint: an EU
user's email is PII and must not live in the US. So whatever global lookup you
build cannot contain EU emails. Now also tell me: at register time, how do you
guarantee one email can't be registered in both regions?"*

**Strong L5 answer.** A **global routing directory**: a lookup from email →
home_region, replicated so any region can read it. Login flow: user submits
email → look up region → if it's the local region, proceed; if it's the other
region, **redirect** the browser (or reverse-proxy) to that cell, which does
the actual credential check and session issue. Register: user declares region →
provision the account in that cell → write the directory entry. Recognizes the
login hot-path latency matters and tries to keep the lookup fast. For
uniqueness, "the directory is the place we check before creating an account."

This is a *reasonable* answer that **walks straight into the trap**: a global
`email → region` table is a global table of EU emails, sitting (replicated) in
the US. The interviewer's one job here is to ask *"what's in that table?"* and
watch whether the candidate catches it.

**Strong L6 answer.** All of the above, *plus the move that is the entire
question*: **the directory is pseudonymous by construction.**

- **Hashed/opaque key → region, never raw PII.** The directory stores
  `key = HMAC-SHA256(normalize(email), secret) → {US|EU}` (plus a small
  version/lock field for migration; see C). It does **not** store the email,
  name, or any credential. Login flow: the edge / a stateless front door
  computes the same `key` from the submitted email locally, looks up the region
  (a single-digit-ms read against a locally-replicated copy), and routes there.
  The owning cell — and *only* the owning cell — holds the real email +
  credential and does the actual authentication. A US engineer dumping the
  directory sees a pile of opaque hashes and region tags: **no EU PII has
  crossed the border.** This is the data-minimization argument you make to the
  DPO, and it's why the directory is *allowed* to be the one global component.
  - Why HMAC-with-secret, not bare SHA-256: bare hashes of emails are
    trivially reversible by dictionary/rainbow attack (the email space is
    small and guessable). An HMAC under a secret held only inside the secure
    front-door service means a directory leak doesn't leak the email set. The
    L6 names this; bare-SHA-256 is a weaker but arguable answer.
- **The directory write is the global serialization point for email
  uniqueness.** You cannot enforce a global unique constraint on `email` when
  the email lives in two different regional databases — there is no shared
  ACID scope. So you make the **directory** the one place email identity is
  serialized: registering an email is a **conditional write to the directory**
  (`INSERT key IF NOT EXISTS → region`). The directory is the *only* component
  that needs global strong-consistency on writes, and writes are rare
  (registrations + migrations, not validations), so it's affordable. Crucially:
  the regional cells **provision the account only after** winning the directory
  write. Concurrent US+EU registrations of the same email → exactly one wins
  the conditional directory write; the loser's provisioning is rejected/rolled
  back. No globally-strong store on the *login* hot path — only on the *register/
  migrate* cold path.
- **The hot-path latency math, stated.** Validations (authenticated, deep dive
  A) are region-local and never touch the directory. *Logins* (unauthenticated)
  do one directory read — which is why the directory must be **locally
  readable** (replicated read replica per region, AP, bounded staleness),
  single-digit-ms p99, *not* a cross-region strong read. If a login's directory
  read had to cross the Atlantic at ~85ms RTT, every cold login would eat that;
  unacceptable. So: **directory reads are AP and local; the directory write
  (register/migrate) is CP and globally serialized.** That split is the whole
  consistency story.
- **Register provisions in the *declared* region.** The user picks US or EU
  (self-declared, trusted for v1). Provision the credential + PII in that
  cell; write `key → declared_region` to the directory (winning the uniqueness
  race). The L6 flags the self-declaration risk: a user who lies (declares US
  but is EU) has their PII in the wrong jurisdiction — a compliance gap we
  accept for v1 but name, and which migration (C) exists to fix when they
  re-declare.
- **Region-discovery fallback when the directory is missing the key.** A login
  whose key isn't in the directory (new/unknown email, or directory replica
  lag) needs a deterministic fallback. Options the L6 weighs: (a) default to a
  **discovery probe** — ask each region "do you own this email?" via a PII-free
  internal call (the email is hashed in transit; only the owning cell can
  confirm) — bounded to N regions, cheap at N=2; (b) default-route to the
  historical home (US) and let it redirect. The L6 picks one and bounds its
  cost.

**Anti-signal.** "Replicate the users table to both regions so login can look
up the region" — and, after the *"what's in that table?"* prompt, doesn't see
that it's EU PII in the US. → Packet: *"Built the global login lookup by
replicating the full user directory — including EU emails — to the US,
recreating the exact residency violation the project exists to fix. Did not
reach a pseudonymous directory even when prompted on its contents."*

**Packet quote (Strong Hire).**
> *"Designed the global routing directory pseudonymous-by-construction:
> `HMAC(email) → region`, no raw PII, so it's allowed to be global and a US
> dump leaks no EU emails. Made the directory write the single global
> serialization point for email uniqueness (conditional INSERT), keeping every
> globally-strong operation on the rare register/migrate path; login does one
> AP local directory read at single-digit ms, never a cross-region strong
> read. Stated the AP-read / CP-write split explicitly and bounded the
> directory-miss fallback."*

### Deep dive C: Account migration + the backfill (state machine, split-brain, throughput)

**Phrasing.** *"Move one existing US user to the EU, live — no data loss, no
split-brain where both cells think they own them. Walk me through the exact
states and the commit point. It must be idempotent and survive a crash
mid-migration. Then: you have 300M existing US users, ~25% are really EU.
Migrate the population."*

**Strong L5 answer.** Per-user migration: freeze writes on the source (mark
the US account read-only), copy the PII + credentials to EU, update
`home_region` to EU, delete or tombstone the US copy, tell the user to log in
again. Recognizes you can't let both cells accept writes at once. For the
backfill: batch-migrate users, throttle to avoid overload, do it off-peak.
Competent but missing the rigor: what's the *atomic* commit point, what
happens on a crash between "copy" and "flip," how do you roll back, and how do
old sessions die.

**Strong L6 answer.** A per-user **migration state machine** with a single
atomic commit point, idempotent and resumable:

```
        ┌──────────────┐   migrate(user, src→dst) requested
        │ RESIDENT(src)│
        └──────┬───────┘
               │  acquire migration lock in directory entry
               │  (version++, state=MIGRATING, owner still=src)
               ▼
        ┌──────────────┐   src account set READ-ONLY / frozen
        │   MIGRATING   │   (logins still served by src, no writes)
        │   (src frozen)│
        └──────┬───────┘
               │  copy PII + credentials src→dst
               │  (idempotent upsert keyed by user_id; re-runnable)
               ▼
        ┌──────────────┐   verify dst copy (checksum / row count)
        │  COPIED       │   dst account exists but NOT yet authoritative
        └──────┬───────┘
               │  ===== COMMIT POINT =====
               │  atomic directory flip: key → dst
               │  (compare-and-set on version; single global write)
               ▼
        ┌──────────────┐   src becomes a REDIRECT TOMBSTONE
        │ RESIDENT(dst) │   (src no longer owns; returns 307→dst)
        │  + src tomb   │   epoch-bump revokes ALL old src sessions
        └──────┬───────┘   → user forced to re-login, routes to dst
               │  async: after retention window, purge src PII
               ▼
        ┌──────────────┐
        │  src PURGED   │   (RTBF-clean; tombstone may remain for routing)
        └──────────────┘

  CRASH at any state → resume is safe: the directory entry's
  (state, version, owner) is the single source of truth.
  ROLLBACK before the flip → set state=RESIDENT(src), unfreeze, delete
  the partial dst copy. After the flip → roll *forward* only (dst owns).
```

The load-bearing details an L6 states:

- **The commit point is the atomic directory flip — and nothing else.** Before
  the flip, `src` owns (the dst copy is inert). After the flip, `dst` owns.
  There is no instant where both own, because ownership is *defined* by the
  single directory entry and the flip is a compare-and-set on the version. That
  CAS is the **split-brain guard**: a stale migrator (e.g. a retried/duplicate
  job) trying to flip an entry whose version moved on fails the CAS and aborts.
- **Idempotent + resumable.** Every step keys off `user_id` and is a re-runnable
  upsert; the directory entry's `(state, version, owner)` is the resume
  pointer. A crash in COPIED → re-run the copy (upsert, no harm) and retry the
  flip. A crash after the flip → the entry already says `dst`, so resume just
  finishes the source-purge. No step assumes it ran exactly once.
- **Src frozen during MIGRATING prevents lost writes.** Between freeze and
  flip the source is read-only (logins still work, but no profile/credential
  writes), so nothing is written to src that the copy would miss. The freeze
  window is short (one user's data is small). For the rare write that arrives
  mid-migration, reject with a retryable error; the client retries post-flip
  against dst.
- **Epoch-bump revocation at the flip forces clean re-login.** The user's old
  sessions point at the src cell. At the flip we **bump the user's session
  epoch** (`10-session-management.md`) so every outstanding src session is
  invalid on next validation; the next request is a fresh login that consults
  the (now-flipped) directory and lands on dst. This is cleaner than *live
  session migration* (copying live session state cross-region and rewriting
  cookies), which is racy and rarely worth it — the L6 justifies forcing
  re-login as the simpler, safer choice and notes the UX cost (one re-login)
  is acceptable for a rare, per-user event.
- **Redirect tombstone in src.** After the flip, src keeps a tiny tombstone
  (`key → moved to dst`) so any straggler request (stale hint, in-flight
  redirect) gets a `307` to dst instead of a 404 or, worse, a resurrected
  account. The tombstone is PII-free (just the routing fact).

**The bulk backfill (300M US users, ~25% really EU):**

- **Default undeclared existing users to US — and name the GDPR risk.** Status
  quo: every existing user is in US today, so absent a declaration they stay
  US. This is operationally necessary but the L6 says out loud: *relying on
  this default means EU users whose data is currently in the US are
  non-compliant until they migrate* — a known gap, time-boxed, with a
  remediation plan, not silently accepted. This is exactly the "name the
  compliance risk" signal.
- **EU-declaration is the migration trigger.** The natural, user-driven path:
  when an existing user declares (or re-declares) EU — in settings, or prompted
  at login — that fires the per-user state machine above. This is the **long
  tail**: organic, low-throughput, self-healing.
- **Optionally a bulk EU-migration wave** for users we can *strongly* infer are
  EU (e.g. verified EU billing address, an EU legal entity) — but inference is
  not declaration, so the L6 flags that bulk-migrating on inference has its own
  legal risk (you're asserting residency the user didn't). Safer: prompt those
  users to declare, then migrate the ones who do.
- **Throughput & rollback for the wave.** One user's data is small (KBs). At a
  migration budget of, say, **2k users/sec** (conservative, to bound load on
  both cells and the directory's CP write path), 25% of 300M = 75M users
  migrate in ~75M / 2k ≈ **~10.4 hours** of pure throughput — realistically
  spread over days/weeks off-peak with the long tail trailing. Each user is an
  independent state machine, so the wave is **resumable and rollback-safe per
  user**: a bad batch rolls back individually (pre-flip) or rolls forward (post-
  flip); there's no all-or-nothing cutover. Rate-limit the directory CP writes
  so the migration wave can't starve live registrations.

**Anti-signal.** "Copy the data, update home_region, delete the old one" with
no atomic commit point, no resume-on-crash, no rollback, no split-brain guard,
and no session-revocation story. → Packet: *"Migration was an unordered
copy-then-switch with no defined commit point; a crash mid-migration would
leave the user owned by both regions or neither. No idempotency, no rollback,
no session invalidation — would not survive contact with production."*

**Packet quote (Strong Hire).**
> *"Per-user migration as an idempotent, resumable state machine whose single
> commit point is an atomic compare-and-set directory flip — the CAS *is* the
> split-brain guard, since ownership is defined by the one directory entry.
> Src frozen read-only during copy to prevent lost writes; epoch-bump at the
> flip invalidates all old-region sessions and forces a clean re-login (chose
> this over racy live-session migration, with the cost named); redirect
> tombstone for stragglers. Backfill defaults undeclared users to US and
> *named the GDPR exposure of that default*, made EU-declaration the trigger,
> sized the wave (~75M users, ~2k/s, rate-limited against live registrations),
> and kept rollback per-user."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **PII in the global directory.** The defining failure. A global `email →
  region` table is EU PII in the US. If they don't catch it after one prompt,
  it's packet-fatal at L6.
- **Routing by request geo-IP.** Residency follows the account, not the
  request. EU user in the US must still hit the EU cell.
- **Globally-strong store on the login hot path.** Correct consistency, wrong
  latency/cost — every login eats a cross-region quorum read.
- **Cookie hint treated as authoritative.** The hint is a guess; the owning
  cell (directory) is the truth. Stale hints after migration must redirect, not
  break.
- **Migration with no commit point / no rollback / no resume.** "Copy then
  switch" without a state machine is a split-brain generator.
- **No session invalidation at the flip.** Old-region sessions stay live →
  the user can keep writing to the dead region. Epoch-bump is the fix.
- **Silent default-to-US with no risk named.** Defaulting undeclared users to
  US is fine; *not naming that it leaves EU users non-compliant* is the L6
  miss.
- **Bulk-migrating on inferred (not declared) residency** without flagging the
  legal risk of asserting a residency the user didn't.
- **No CAP commitment.** "It's consistent" — where, on which path, at what
  staleness? Directory reads AP + local, directory writes CP + global.

### Interviewer-side (your own traps)

- **Letting them dwell on the two-cell diagram.** Two regional cells is the
  easy 10 minutes. By minute 28 force the unauthenticated-login lookup — that's
  where the signal is.
- **Leading them to the pseudonymous directory.** This is the answer; if you
  hand it over, the packet won't write convincingly. Use *"what's in that
  table?"* and let them get there.
- **Accepting "migrate the user" without the commit point.** The level-up is
  the *atomic flip as the single point ownership changes* and the split-brain
  CAS. Push until they name it or visibly can't.
- **Forgetting the backfill.** One-user migration is half the dive; the 300M
  backfill (default, trigger, throughput, rollback) is where org-scale judgment
  shows. Don't run out of clock before it.
- **Eating the candidate's question window.** Still scoring Googleyness.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it. Numbers
explicit, trade-offs committed.

### 6.1 Functional requirements (committed scope)

v1: **route authenticated requests** to the cell owning the session (via a
cookie region hint, verified against the owning cell); **route login**
(unauthenticated, email-only) to the cell owning that email's account;
**register** a new user in their self-declared region with a **globally-unique
email** guarantee; **migrate** an existing user between regions live, with no
data loss or split-brain; **backfill** the existing US population, with
EU-declaration as the migration trigger; **revoke** old-region sessions at
migration (force clean re-login).

**Out of scope v1, said out loud:** the auth protocol itself (OIDC/SAML/code
flow — that's `06`/`07`); the session token + revocation *internals* (that's
`10` — I reuse epoch-bump as a primitive, I don't re-derive it); verifying the
user's declared region (self-declared and trusted for v1); full GDPR DSAR
tooling beyond delete-propagation; a third region (designed as a seam, not
built).

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| DAU | **300M** | Large consumer + enterprise SSO. |
| Logins/sec (cold, unauth) | **~5k peak** | Most users log in ~once/day; 5× peak concentration. This path hits the directory. |
| Validations/sec (hot, auth) | **~5M peak** | Every request validates a session. ~1000:1 vs logins. Region-local; never touches the directory. |
| EU / US split | **~25% EU / ~75% US** (post-migration steady state) | Drives backfill size and per-cell capacity. |
| Directory record size | **~40 B** (`32 B HMAC key + 1 B region + version/lock`) | PII-free by construction. |
| Total directory size | **300M × ~40 B ≈ 12 GB** (×3 repl ≈ 36 GB) | Tiny → fits in memory, globally replicable cheaply. *Being small + PII-free is what lets it be global.* |
| Directory lookup p99 | **< 5 ms** (local read replica per region) | On the login cold path; must be local, never a cross-region strong read. |
| US↔EU RTT | **~80–90 ms** | The tax on any cross-region hop. Keep it off the hot path; pay it once on first post-migration request. |
| Migration throughput | **~2k users/sec** (rate-limited) | Bounded to protect the directory CP-write path and both cells. |
| Session / cookie size | **< 1 KB** (`user_id, region claim, epoch, sid, exp`) | Rides every request; region hint is a small cleartext prefix on top. |
| Backfill population | **~75M** (25% of 300M existing US users) | EU users currently mis-placed in US. |
| Availability — validation | **99.99%** | Region-local; a region down affects only that region's users. |
| Availability — directory | **99.99%** | Global SPOF for *new logins*; existing sessions survive an outage. |

### 6.3 Capacity estimation (worked)

- **Directory.** 300M users × ~40 B = **~12 GB**, ×3 replication ≈ 36 GB.
  In-memory, globally replicated read replicas. This smallness is *the* enabler:
  a 12 GB PII-free table is cheap to put everywhere; a multi-TB PII users-table
  is not (and would be illegal in the US anyway).
- **Login load on the directory.** 5k logins/sec × 1 read each = 5k reads/sec
  to a *local* replica — trivial; served from memory at < 5ms p99. Directory
  *writes* = registrations + migrations ≈ low hundreds/sec steady state (plus
  the bounded ~2k/sec migration wave) — the only globally-serialized writes.
- **Validation load.** 5M/sec, entirely region-local (deep dive A) — never
  touches the directory. This is why the directory's global-ness is affordable:
  the 1000:1-dominant path doesn't use it.
- **Backfill.** 75M users × ~2 KB each (PII + credential) = ~150 GB total to
  copy, over the wave. At 2k users/sec → ~10.4 h of pure throughput; spread
  over days off-peak. Each user ~2 KB copy is sub-second; the rate limit is
  about the CP directory-write contention, not bandwidth.

**Numbers that changed a design choice:**
- **~85ms US↔EU RTT + 5k logins/sec** → the directory read on the login path
  must be *local* (AP, replicated), never a cross-region strong read; a strong
  read would add 85ms to every cold login.
- **1000:1 validation:login** → validation stays region-local and off the
  directory entirely; the global component only serves the cold 0.1%.
- **12 GB PII-free directory** → it's small and legal enough to replicate
  globally; if it held PII it could neither be global (residency) nor cheap.
- **75M backfill** → needs a per-user, resumable, rate-limited machine, not a
  big-bang cutover.

### 6.4 API design

```
# Edge / front-door (PII-free routing)
POST /v1/route/login        { email }            (front door, before auth)
                            → 200 { region } | redirect to owning cell
                            (computes HMAC(email) locally, reads directory)

# Within a cell (the real auth — see 06/07)
POST /v1/login              { email, credentials }   → session (region-hinted cookie)
POST /v1/register           { email, credentials, declared_region }
                            → 201 (only after winning the directory uniqueness write)

# Directory (global, PII-free; CP writes, AP reads)
GET  /v1/directory/:key     → { region, version, state }     (local replica read)
PUT  /v1/directory/:key     { region } IF NOT EXISTS          (register: uniqueness)
CAS  /v1/directory/:key     { region, expected_version }      (migrate: the flip)

# Migration control plane
POST /v1/migrate            { user_id, src, dst }   → drives the state machine
GET  /v1/migrate/:user_id   → { state, version }    (resume pointer)
```

`route/login` is the only globally-relevant hot-path call, and it is a single
local directory read keyed by the HMAC of the email computed in the front door.

### 6.5 Data model

- **Directory (global, PII-free):** `key = HMAC-SHA256(normalize(email),
  secret)` → `{ home_region ∈ {US,EU}, version (monotonic int), state ∈
  {RESIDENT, MIGRATING, COPIED}, owner }`. The *only* global store. Conditional
  INSERT enforces email uniqueness; CAS on `version` is the migration commit.
  **No email, name, or credential here.**
- **Per-cell `users` (regional, holds PII):** `user_id` (PK), `email`,
  `credential_ref`, profile/PII, `home_region` (= this cell), `session_epoch`
  (from `10`). Lives *only* in the owning region.
- **Per-cell `sessions` (regional):** `session_id` → `{ user_id, region,
  epoch_at_issue, device, expires_at }`. Region-local; never replicated cross-
  region.
- **Per-cell `tombstones` (regional, PII-free):** `key → moved_to_region`. Left
  in the source after a migration so stragglers get a `307`, not a 404.

The secret for the HMAC lives only inside the secure front-door / directory-
write service (KMS-managed, rotatable — rotation is a directory rebuild, a
named v2 concern).

### 6.6 High-level architecture

```
   Authenticated request (5M/s, HOT)        Unauthenticated login (5k/s, COLD)
   cookie present, region-hinted            email only, no session
            │                                        │
            ▼                                        ▼
   ┌───────────────────────────────────────────────────────────────┐
   │            Edge / GFE / Anycast  +  PII-free Front Door         │
   │  - auth req: read cleartext region hint → route to owning cell  │
   │  - login: HMAC(email) → read GLOBAL DIRECTORY → route to owner  │
   └───────┬───────────────────────────────────────┬───────────────┘
           │ route to owner                          │ route to owner
           │                                         │
  ┌────────▼─────────────────┐          ┌────────────▼──────────────┐
  │      US CELL             │          │        EU CELL             │
  │  ┌────────────────────┐  │          │  ┌──────────────────────┐  │
  │  │ Auth svc (06/07)   │  │          │  │ Auth svc (06/07)     │  │
  │  │ users + PII (US)   │  │          │  │ users + PII (EU)     │  │
  │  │ sessions (US)      │  │          │  │ sessions (EU)        │  │
  │  │ session_epoch (10) │  │          │  │ session_epoch (10)   │  │
  │  │ tombstones         │  │          │  │ tombstones           │  │
  │  └────────────────────┘  │          │  └──────────────────────┘  │
  └──────────┬───────────────┘          └──────────────┬─────────────┘
             │  register: PUT IF NOT EXISTS             │
             │  migrate:  CAS(version) = the flip       │
             ▼                                          ▼
  ┌───────────────────────────────────────────────────────────────┐
  │       GLOBAL ROUTING DIRECTORY  (PII-free, ~12 GB)             │
  │   HMAC(email) → { region, version, state }                     │
  │   AP local read replicas per region  (login hot path, <5ms)    │
  │   CP global write quorum (register uniqueness + migration flip)│
  └───────────────────────────────────────────────────────────────┘

  Key invariant: the directory holds NO PII, so it is allowed to be global.
  Validations (5M/s) never touch it — they're region-local. Only the cold
  login path (5k/s) reads it; only register/migrate write it.
```

### 6.7 The three routing/migration mechanisms

These are deep dives A, B, and C in §4, in full — the golden answer's spine.
In a live round you'd narrate them here in this order: (A) authenticated
routing via cookie hint, owner authoritative, stale-hint redirect; (B) the
crux — PII-free hashed directory for the login lookup, conditional-write as the
uniqueness serialization point, AP-read/CP-write; (C) the per-user migration
state machine with the atomic CAS flip as the commit point, epoch-bump
revocation, redirect tombstones, and the rate-limited backfill that defaults to
US while naming the GDPR exposure. Do not re-derive them — §4 is the script.

### 6.8 Multi-region / consistency commitments

CAP commits, said out loud:

- **Directory reads: AP.** Local replica per region, bounded staleness. A login
  serves from the local copy; if a just-registered user's key hasn't replicated
  yet, the discovery-probe fallback covers the gap. We choose availability +
  locality over strong reads because a cross-region strong read would put 85ms
  on every cold login.
- **Directory writes: CP.** Register (uniqueness) and migrate (the flip) are
  globally serialized — `INSERT IF NOT EXISTS` and CAS-on-version need a single
  global agreement (a Spanner-class store, or a designated global write
  coordinator). These are rare (hundreds/sec) so the CP cost is affordable, and
  it's the *only* globally-strong operation in the system.
- **Per-cell stores: region-local, not replicated cross-region.** PII +
  sessions live only in the owning region — that's the residency requirement,
  not just a perf choice. A US cell failure affects only US users; EU is
  unaffected (and vice-versa). This is the blast-radius win of geo-partitioning:
  no single store holds everyone.
- **The migration flip is the one cross-region transaction**, and it's
  per-user and CAS-guarded, so it never needs a distributed 2PC across the bulk
  data — only the 40-byte directory entry is transacted.

### 6.9 Cost (back-of-envelope, monthly)

| Component | Notes | $/mo |
|---|---|---|
| Two regional cells (auth + users + sessions) | ~5M validations/s split across 2 cells, region-local | ~$120k |
| Global directory — read replicas | ~12 GB in-mem, replicated per region, 5k reads/s | ~$15k |
| Global directory — CP write tier | Spanner-class for uniqueness + flips, low QPS | ~$20k |
| Front-door HMAC + routing fleet | stateless, computes HMAC + 1 directory read per login | ~$10k |
| Migration control plane (during backfill) | transient; rate-limited workers | ~$10k (one-time-ish) |
| **Total** | | **~$165k/mo** steady (+ transient backfill) |

**Dominator:** the two regional cells (the validation fleet). The directory —
the cleverest part — is *cheap* precisely because it's tiny and PII-free
(~$35k/mo all-in). The design spends its complexity budget keeping the global
component small and off the hot path. A naive "globally-strong users table"
alternative would cost multiples more (paying global consistency on every
login + replicating multi-TB PII) **and be illegal** — so cost and compliance
point the same way.

### 6.10 Failure modes & blast radius

| Failure | Blast radius | Behavior |
|---|---|---|
| One cell (e.g. US) down | That region's users only | EU users entirely unaffected (geo-partition win). US validations fail locally; existing EU sessions fine. No global outage. |
| Global directory read-replica (one region) down | New logins in that region | Fail over to another region's replica (PII-free, safe to read cross-region); existing sessions survive (validation never touches the directory). |
| Global directory write tier down | Registrations + migrations pause | **Fail closed on writes** (a uniqueness or flip write must not silently no-op → split-brain risk). Logins (reads) keep working from replicas. |
| Directory region-wide outage (10 min) | All new logins | **Fail open to last-known hint for *authenticated* refresh** (existing sessions validate locally, unaffected); for *cold logins* with no hint, fail closed or default-route-to-US-then-redirect — bounded, explicit. |
| Migration crash mid-flight | One user | Resume from the directory entry's `(state,version)`; pre-flip rollback or post-flip roll-forward. CAS prevents a duplicate flip. |
| Stale cookie hint after migration | One user, one request | `307` from src tombstone + epoch-bump invalidates old session; first request pays one ~85ms hop. |
| HMAC secret leak | Directory keys become email-guessable | Rotate the secret = rebuild the directory (offline, keyed re-hash); short-term, directory still holds no plaintext. |

**Fail-open vs fail-closed, per path:** directory *reads* (login routing) fail
open to a sibling replica or last-known hint — availability matters and the
data's PII-free; directory *writes* (uniqueness, flips) fail closed — a missed
write means split-brain or duplicate emails, a correctness/security hole. This
split is the L6 commit.

### 6.11 Evolution / curveballs

- **Add a 3rd region (APAC).** `home_region` becomes an enum of 3, not a
  boolean — the directory's value field already holds a region, so it's a
  *value change, not a schema/redesign*. The discovery-probe fallback grows
  from N=2 to N=3 (still cheap). The migration machine is region-agnostic
  (`src→dst` for any pair). What does **not** change: the directory stays
  PII-free; validation stays region-local; the flip stays the commit point. The
  named seam: the directory's CP-write tier must now agree across 3 regions —
  pick a topology (one global write region vs. a global Spanner instance) and
  accept its latency for the rare write.
- **Directory region-wide outage.** See 6.10. The honest answer is *per path*:
  authenticated traffic is unaffected (validation is local); cold logins
  degrade — fail open to last-known hint where one exists, else default-route
  with redirect, bounded and stated. Never fail open on *writes*.
- **User declares EU mid-session with an active US session + a legal hold.**
  The migration is *blocked* while a legal hold pins the US data (you may not
  move or delete data under hold). The L6 names this: residency change and
  legal hold conflict; legal hold wins; the user's migration is queued until
  the hold lifts, and meanwhile they're served from US with the gap documented.
  This is the "name the compliance reality" signal.
- **Migrate millions.** The backfill (6.9): per-user machine, ~2k/s, rate-
  limited against live registrations, resumable, rollback per-user. Not a
  big-bang.
- **Right-to-be-forgotten at scale.** A migrated EU user's erasure must land in
  the **EU cell (the real PII)**, the **directory** (delete the key — and
  decide whether to keep a PII-free tombstone for routing or fully remove), and
  any **src tombstone** left from a prior migration. RTBF is a fan-out delete
  across exactly the places that hold a trace; because PII lives in *one* cell
  by construction, the fan-out is small and auditable — another payoff of
  geo-partitioning over global replication.

### 6.12 What I'd own vs. delegate

I'd personally own the **directory contract** (the HMAC keying, the AP-read/
CP-write split, the uniqueness-via-conditional-write invariant) and the
**migration state machine + commit point**, because they're the
correctness/compliance-load-bearing core — get the commit point wrong and you
get split-brain; get the directory contents wrong and you ship the violation.
I'd delegate the **per-cell auth services** to the teams that already run them
(`06`/`07`/`10` are their world — I consume epoch-bump as a primitive), the
**directory's storage operation** to the team that runs our globally-replicated
KV / Spanner, and the **backfill control plane** to a migrations team behind a
clean per-user-state-machine contract. The clean seam between me and them is
the directory entry: a 40-byte, PII-free, version-stamped fact.

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence. Right is the level call.

| Evidence | Call |
|---|---|
| No numbers after two prompts; routed by request geo-IP; proposed replicating the full users table globally and didn't see the PII problem when asked "what's in that table?". | **Strong No Hire** |
| Drew two cells and `home_region`, but the global login lookup was a replicated users table (EU emails in US); after the prompt, patched it with "we'll encrypt it" without grasping that a US-readable email-keyed table is the violation. Migration was "copy then switch." | **No Hire** |
| Two cells, cookie-hint routing for authenticated requests, a global `email→region` directory for login. Recognized PII concern only when pushed and gestured at "hash it" without HMAC/uniqueness reasoning. Migration had a vague freeze-copy-switch with no commit point. | **Lean No Hire** |
| Numbers by min 12 (300M DAU, 5k logins/s, 5M validations/s, 25/75 split, ~85ms RTT). Two regional cells with region-local PII + sessions. Authenticated routing via cookie hint, verified against the owning cell, with a stale-hint redirect when asked. Global directory for login; **caught the PII problem after one prompt** and moved to a hashed key. Migration as freeze→copy→flip→re-login with a recognizable commit point. Didn't fully reach HMAC-vs-bare-hash, the uniqueness-write-as-serialization-point, or the named backfill GDPR risk. | **Hire L5** |
| All of L5-Hire, **plus**: designed the directory **pseudonymous-by-construction unprompted** (hashed key → region, no PII, "a US dump leaks no EU emails"); kept the directory off the validation hot path; stated the AP-read/CP-write split; migration was an idempotent resumable state machine with the atomic flip as commit point and epoch-bump revocation. Some backfill reasoning. | **Hire L5 / Lean L6** |
| All of the above, **plus**: HMAC-with-secret (not bare SHA-256) with the dictionary-attack reason; made the **directory write the single global serialization point for email uniqueness** (conditional INSERT) so no strong store sits on the login hot path; CAS-on-version as the explicit **split-brain guard**; chose forced re-login over live session migration with the cost named; redirect tombstones; **defaulted backfill to US and named the GDPR exposure of relying on it**; sized the wave (~75M, ~2k/s, rate-limited); per-path fail-open/closed; APAC as a value change not a redesign; $/mo with the cells as dominator and "the directory is cheap *because* it's tiny + PII-free". | **Hire L6** |
| Everything in L6, **plus**: named what they'd own (directory contract + migration commit point) vs. delegate (per-cell auth, directory storage, backfill plane) and *why the 40-byte PII-free directory entry is the clean seam*; handled the legal-hold-blocks-migration conflict; mapped RTBF fan-out across cell + directory + tombstone and noted geo-partitioning makes erasure smaller/auditable than global replication; defended the AP-read/CP-write split against "why not Spanner everywhere" pushback with the 85ms-per-login and residency-illegality arguments; closed with a self-aware retro (HMAC key rotation = directory rebuild; rebalancing if EU outgrows US). | **Strong Hire L6** |

---

## Sources

- WorkOS — *Why authentication doesn't need to stay local: the new data
  residency pattern* (UUID-only global index; PII in a regional vault; auth
  routing without replicating PII — the core crux):
  https://workos.com/blog/data-residency-for-enterprise-saas
- Atlassian — *Understand data residency* / *Pin data in your region*
  (residency as pinning in-scope data to a location; move-and-pin model):
  https://support.atlassian.com/security-and-access-policies/docs/understand-data-residency/
- InfoQ — *Understanding Architectures for Multi-Region Data Residency*
  (silo-per-region, routing, where the global layer can/can't sit):
  https://www.infoq.com/articles/understanding-architectures-multiregion-data-residency/
- AWS Samples — *multi-region-data-residency* (reference multi-region app with
  per-region data residency and a routing layer):
  https://github.com/aws-samples/multi-region-data-residency
- DZone — *How to Geo-Partition Data in Distributed SQL* (row-level placement /
  pinning partitions to geographies for GDPR):
  https://dzone.com/articles/how-to-geo-partition-data-in-distributed-sql
- alhena.ai — *GDPR Compliance Through Multi-Region Architecture: An
  Engineering Deep Dive* (EU compute + data in EU, backup-crossing-border as a
  violation):
  https://alhena.ai/blog/gleen-ai-support-gdpr-compute-and-data-in-eu/
- Scale Computing — *Data Sovereignty vs. Data Residency vs. Data Localization*
  (the three-term distinction the candidate must not blur):
  https://www.scalecomputing.com/resources/data-sovereignty-data-residency-and-data-localization
- Kiteworks — *Understand and Adhere to GDPR Data Residency Requirements* +
  *Data Sovereignty and GDPR* (residency stipulation; RTBF across replicas):
  https://www.kiteworks.com/gdpr-compliance/understand-and-adhere-to-gdpr-data-residency-requirements/
- Agile Brand Guide / 5x5 Data — *Hashed Email (HEM)* best practices
  (SHA-256 vs HMAC-SHA-256 with secret/salt; pseudonymous match key without
  transmitting raw PII):
  https://agilebrandguide.com/wiki/data/hashed-email-hem/
- Medium (Aditya Yadav) — *How to Enforce Global Uniqueness in a Partitioned
  Table* + DEV (YugabyteDB) — *Global Unique Constraint on a partitioned table*
  (side-table / global-serialization approach to cross-partition email
  uniqueness):
  https://medium.com/@dev-aditya/how-to-enforce-global-uniqueness-in-a-partitioned-table-50feb54a578e ,
  https://dev.to/yugabyte/global-unique-constraint-on-a-partitioned-table-in-postgresql-and-yugabytedb-4nh6
- DataStax — *Phases of the Zero Downtime Migration process* + DEV (Ari Ghosh)
  — *Zero-Downtime Database Migration: The Complete Engineering Guide*
  (freeze/dual-write/validate/cutover phases, CDC, resumable cohorts):
  https://docs.datastax.com/en/data-migration/introduction.html ,
  https://dev.to/ari-ghosh/zero-downtime-database-migration-the-definitive-guide-5672
- Microsoft Entra — *Microsoft Entra ID and data residency* (per-tenant
  geographic data-storage location selection at provisioning):
  https://learn.microsoft.com/en-us/entra/fundamentals/data-residency
- Hello Interview — system-design delivery framework & Google L6 guide
  (calibration): https://www.hellointerview.com/guides/google/l6

---

*End of guide. Related:* `06-sso-auth-service.md` *(session authority,
attestation handoff, fail-closed — the per-cell auth this question routes
between) and* `10-session-management.md` *(epoch-bump revocation and the signed
cookie claim — reused here as the migration's session-invalidation primitive
and the authenticated-routing hint carrier).*
