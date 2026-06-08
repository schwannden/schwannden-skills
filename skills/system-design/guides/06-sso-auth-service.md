# Question 6: Single Sign-On / Authentication Service (federated identity / auth platform)

> Interviewer's guide for the 1-hour Google L5/L6 system-design round.
> Anchor problem for the **federated-identity / auth-platform** archetype.
> Frame it around something the candidate knows: Okta, "Sign in with
> Google," or enterprise SSO where a tenant brings its own IdP. The
> question is canonical, so the calibration value is *not* whether they
> can spell OIDC — it's whether they understand **who the authority is**,
> what is delegated vs. owned, and what happens when the thing you
> delegated to falls over. Auth is the one system where a wrong
> availability/consistency call is also a *security* call, and that fusion
> is exactly the L5/L6 separator.

---

## 1. Why this question (interviewer's framing)

SSO *looks* like a protocol-recall question. A prepared L4 will draw the
OIDC redirect dance, name SAML, say "JWT," and stop. The redirect flow is
table stakes — it is **not the question being asked**. The real question
is: *you are a platform that lets thousands of tenants log their users in,
sometimes against their own corporate IdP — what are you the authority
for, what do you delegate, and what is the blast radius when a delegated
dependency or your own session store fails?*

That forces explicit reasoning on five axes that all have a clean L5
answer that is *wrong at platform scale*:

- **Session authority vs. authentication delegation.** The single most
  load-bearing idea on the page. A federated IdP *authenticates* the user
  (proves who they are). But the SSO service stays the **session
  authority** — it mints its *own* identity and session after the IdP
  attests, and never passes raw IdP claims downstream. Conflating these is
  the modal downlevel.
- **Issue-cheap, revoke-hard.** Minting a session is trivial. Killing one
  *everywhere, fast* is the hard distributed-systems problem, and it is a
  security SLA, not a nicety.
- **The native fast-path vs. the federated slow-path.** ~99% of logins are
  native (your own password/passkey) and want an O(1), zero-external-call
  validation. The ~1% federated logins ride a redirect to someone else's
  server you don't control. One design must serve both without taxing the
  common case.
- **Multi-tenant delegation routing.** Tenant A authenticates against
  Okta, Tenant B against Entra, Tenant C natively. Where does the "which
  IdP?" decision live, and is that routing itself an attack surface?
- **Fail-open vs. fail-closed — but for auth.** When the IdP or broker is
  down, do you let users in? For authentication the answer is almost
  always **fail-closed**, and saying so crisply (and knowing the cost) is
  an L6 tell.

### What "Hire" looks like at each level

**L5 Hire.** Draws the OIDC authorization-code flow correctly. Commits to
logins/sec and session-lookup p99 by minute 12. Separates the IdP (proves
identity) from their own session cookie. Picks stateful vs. stateless
tokens and defends it. Names revocation as a problem and proposes a
mechanism. Handles "the IdP is down" calmly when asked.

**L6 Hire.** All of the above, *plus*: states the **session-authority vs.
delegation** split unprompted and refuses to pass raw IdP claims through
("I re-issue my own identity after attestation"); volunteers an O(1)
revocation primitive ("epoch / version bump → log-out-everywhere without
enumerating sessions"); designs the **~99% native fast-path** as a
zero-external-call O(1) lookup explicitly so federation never taxes it;
commits to **fail-closed for federated users** with the blast radius
named; treats **opt-in consent on account-linking as a security
primitive**, not UX; and pushes tenant-specific enforcement *to the
tenant* rather than building a central routing engine that becomes a
config-injection surface.

### Classic downlevel traps

1. **Pass-through IdP claims.** Trusting the IdP's `email` claim to *be*
   the identity, or forwarding the raw IdP token to downstream services.
   This is the account-takeover vulnerability and the clearest "designed
   the feature, not the service" signal. Packet-fatal at L6.
2. **Stateless JWT with no revocation answer.** "We use JWTs, they're
   self-validating" — then no story for "log this user out *now*." A
   15-minute-lived stolen token is a 15-minute breach.
3. **"We'll fail open if the IdP is down."** For *authentication* this is
   letting unauthenticated users in. Almost always wrong; saying it
   without flinching is a red flag.
4. **A central routing engine that takes hosts/URLs from config or
   payload.** "We look up the tenant's IdP URL and redirect there" — if
   that URL is attacker-controllable, it's an open-redirect / SSRF.
5. **One session model for both native and federated.** Either you tax the
   99% native path with federation machinery, or you give federated
   sessions native-session lifetimes (so a fired employee keeps a live
   session after the corporate IdP disabled them).

---

## 2. The 60-minute plan

`0–5 Intro · 5–15 Requirements & scope · 15–25 Capacity + high-level
design · 25–45 Deep dives · 45–55 Evolution / curveball · 55–60 Wrap`.

### 0–5 min — Intro

**Say:** *"I'm <name>, L7 on <unrelated infra team>. 60-second intro from
you, then: design a single sign-on / authentication service. Think Okta,
or 'Sign in with Google,' or enterprise SSO where a customer brings their
own identity provider. Drive it however you like; I'll interject."*

**Listen for:** do they ask *who the users are* (consumers? enterprise
tenants? both?) — auth scope is meaningless without it. **Push back when:**
they start drawing the OIDC dance before scoping. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** little. If asked "consumer or enterprise?" → *"Both — a platform
that serves your own users natively and lets enterprise tenants federate
to their IdP."* If asked "which protocols?" → *"You tell me what you'd
support and what you'd cut."*

**Listen for:**
- Functional commit: login (native + federated), session issuance,
  validation, logout (single + global), token/cookie for downstream
  services, account linking. Bonus for *explicit cuts* (no authorization /
  RBAC, no user-profile CRUD, no MFA-enrollment UX in v1).
- The **authority question surfaced here**: "who proves identity vs. who
  owns the session?" If they raise it unprompted in scoping, note it — it's
  the highest-value early signal on this question.
- Numbers: logins/sec, validations/sec (read-heavy, ~100–1000× logins),
  session-lookup p99, % native vs. federated, revocation-propagation SLA.

**Push back when:** "secure and scalable" with no number → *"Quantify.
Logins/sec? Validations/sec? Revocation SLA?"* · 10 functional reqs →
*"Smallest useful v1?"* · they treat authn and authz as one thing →
*"Are you authenticating or authorizing? Pick one to own today."*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip math → *"What does the read:write
ratio tell us about how to store sessions?"*

**Listen for:**
- Worked numbers: logins/sec (write), validations/sec (read, the dominant
  load), session store size, token size. The **read:write skew (~1000:1)**
  should drive the session-validation design.
- The native-vs-federated split surfaced as a *design force*: ~99% native
  → the validation path must not pay for the 1% federated machinery.
- Box diagram: clients → edge/GFE → Auth Service (login + token endpoints)
  → Session Store → (Federation Broker → tenant IdPs) on the side; native
  credential store separate.

**Push back when:** reflexive "JWT everywhere" → *"How do you revoke one
before it expires?"* · reflexive "Redis for sessions" → *"What's the QPS
to it, and what happens when it's down — do users get logged out or let
in?"*

### 25–45 min — Deep dives

The diagnostic phase. **Two mandatory**, one chosen:

1. **The auth flow & session authority** (mandatory) — *"Walk me through a
   federated login end to end. When the IdP sends back claims, what
   exactly do you do with them? What does the downstream service see?"*
2. **Session issuance + revocation at scale** (mandatory) — *"A laptop is
   stolen. The user clicks 'log out everywhere.' Walk me through the next
   500ms across every service that trusts this session."*
3. **Multi-tenant IdP delegation & enforcement routing** (chosen if not
   volunteered) — *"Tenant A is on Okta, B on Entra, C is native. Where
   does the 'which IdP' decision live, and how is that not an SSRF?"*

**Listen for at L6:** re-issue-own-identity stated as a security boundary;
O(1) revocation (epoch/version bump); the native O(1) side-table lookup;
fail-closed-for-federated with named blast radius; consent-on-link as
anti-hijack.

**Push back hard** on pass-through claims (*"so if I'm a tenant admin and I
set someone's email to ceo@victim.com, what happens?"*), on un-revocable
JWTs (*"15-minute window on a stolen token — acceptable?"*), and on a
central routing engine that eats config URLs (*"where does that host come
from — can a tenant put `http://169.254.169.254` in it?"*).

### 45–55 min — Evolution / curveball

Pick **one**:
- *"Your federation broker has a region-wide outage for 10 minutes. Minute
  by minute — who can log in, who can't, who gets logged out?"* (the
  mandatory-ish failure scenario)
- *"Now support 50M enterprise seats across 10k tenants. What changes?"*
- *"A tenant offboards an employee in their IdP at 2pm. The employee has a
  live session in your product. When are they out, and who decided?"*

**Listen for:** seam identification vs. redesign; the fail-closed-vs-open
call made *per user class* (native users unaffected by broker outage;
federated users fail closed); session-revoke-on-unenrollment.

### 55–60 min — Wrap

**Say:** *"Time. What would you do with 15 more minutes? Then — questions
for me?"* **Still scoring:** self-aware retro ("I didn't cover MFA step-up
or device trust"), and the shape of their questions.

---

## 3. Probing prompts (the kit)

Pre-loaded; each hunts one signal. Drop verbatim, then use silence.

| Prompt | Signal hunted |
|---|---|
| *"Consumer logins, enterprise SSO, or both? How does that change the design?"* | Scope discipline; auth design is meaningless without the user model. |
| *"Commit to numbers: logins/sec, validations/sec, session-lookup p99, revocation SLA."* | Unprompted numbers; the read:write skew is load-bearing. |
| *"When the IdP returns claims, what *exactly* becomes the user's identity in your system?"* | The authority question. Pass-through = downlevel; re-issue-own = L6. |
| *"Does a downstream service ever see the raw IdP token? Why not?"* | Attestation handoff as a security boundary. |
| *"Tenant admin sets a user's email to ceo@bigcorp.com. What happens at login?"* | Email-claim trust trap; the account-takeover vector. |
| *"Stateful session store or stateless JWT? What did you give up?"* | Validation-vs-revocation trade-off, defended. |
| *"User clicks 'log out everywhere.' How, without enumerating every session?"* | O(1) revocation primitive (epoch/version bump). |
| *"99% of your logins are native. Does that path ever call an external system?"* | The zero-external-call fast path; not taxing the common case. |
| *"Validation is ~1000× logins. Where does that read land, and what's its p99?"* | Read-path design; O(1) side-table lookup. |
| *"The federation broker is down. Who can log in? Who gets logged out?"* | Fail-closed-for-federated with blast radius. |
| *"Tenant A→Okta, B→Entra, C→native. Where does that routing live?"* | Delegation model; central engine vs. tenant-owned enforcement. |
| *"Where does the tenant's IdP URL come from — config, payload, or a pinned namespace?"* | SSRF/open-redirect awareness on the routing surface. |
| *"Two accounts, same email, one native one Google. Do you auto-merge?"* | Consent-as-anti-hijack vs. naive email-linking. |
| *"Tenant offboards a user in their IdP at 2pm. When is the live product session dead?"* | Session-revoke-on-unenrollment; fixed vs. sliding window. |
| *"How fresh is a revocation? If I revoke now, when does service N reject the token?"* | Revocation-propagation SLA, quantified. |
| *"Cost per month at your scale — what's the dominator?"* | L6 marker; session-store read QPS or broker calls. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

Steer to the **two mandatory** dives (A, B) and pick C if not volunteered.

### Deep dive A: Auth flow & session authority (attestation handoff)

**Phrasing.** *"Walk me through a federated login end to end. The user's
corporate IdP authenticates them and sends back claims. What exactly do
you do with those claims, and what does a downstream service that trusts
your session ever see?"*

**Strong L5 answer.** Draws the OIDC authorization-code flow correctly:
client → Auth Service `/authorize`; the service recognizes the tenant is
federated, redirects the browser to the tenant's IdP with `state` + a
`redirect_uri`; IdP authenticates, redirects back with a `code`; the
service redeems the `code` **server-to-server** for an ID token, validates
the signature against the IdP's JWKS, checks `iss`/`aud`/`exp`/`nonce`,
maps the IdP user to a local account, then **issues its own session
cookie**. Names that the IdP proves identity but the service owns the
session. Correct, clean, L5.

**Strong L6 answer.** All of the above, *plus* the framing as a **security
boundary**, stated out loud:

- **"I re-issue my own identity; I never pass IdP claims through."** The
  IdP's job ends at *attestation* — "this person is bob@tenant.com,
  verified." The Auth Service maps that to a stable internal subject
  (`user_id`), and *that* — not the IdP's `sub` or `email` — is what
  every downstream sees, inside a token the Auth Service signed. Reasons:
  (a) downstream services trust *one* issuer (us), not N tenant IdPs with
  N key sets; (b) IdP claims are *tenant-controlled* and a tenant admin
  who can set `email=ceo@victim.com` must not thereby become the CEO; (c)
  we can revoke our own token without depending on the IdP.
- **Email-claim trust trap, named unprompted.** "Identical email string
  does not mean same person — a tenant can mint unverified emails. I link
  on the tenant-scoped IdP subject (`iss`+`sub`), never on a bare email,
  and I require the IdP to assert the email is verified before I'll even
  surface it."
- **The browser hop is PII-free.** Claims never ride a URL fragment or
  Referer; the `code` is opaque and single-use, redeemed server-to-server.
  (Full protocol depth is Question 7; here it's a one-liner.)
- **Consent as the anti-hijack primitive.** When a login wants to *link*
  an external identity to an existing account, it is **opt-in, explicit,
  on an authenticated session** — never automatic on matching email.
  "Link-on-login behind a consent step is the cheap hurdle that stops
  silent account takeover."

**Anti-signal.** "We forward the IdP's JWT to the services" or "we trust
the email claim to find the user." → Packet: *"Conflated the IdP with the
session authority; would forward tenant-controlled claims downstream —
an account-takeover vector. Did not see re-issue-own-identity as a
boundary."*

**Packet quote (Hire).**
> *"Stated unprompted that the IdP only attests; the service re-issues its
> own identity and signs its own token, so downstream trusts one issuer.
> Linked on tenant-scoped IdP subject, never bare email; flagged the
> tenant-admin email-spoof vector and gated account-linking behind opt-in
> consent. Browser hop PII-free, code redeemed server-to-server."*

### Deep dive B: Session issuance + revocation at scale

**Phrasing.** *"A laptop is stolen. The user clicks 'log out everywhere.'
Walk me through the next 500ms across every service that trusts this
session. Now: how is that not an O(number-of-sessions) operation?"*

**Strong L5 answer.** Stateful sessions: a session record in a fast KV
store (Redis/Bigtable), cookie holds an opaque `session_id`. Validation =
a lookup, sub-ms. Revocation = delete the record; "log out everywhere" =
delete all the user's session rows. Names the trade-off vs. stateless
JWTs: stateful means a store read on every validation (but trivially
revocable); JWTs are self-validating (no read) but you can't kill one
before `exp`. Picks stateful for revocability. Competent L5.

**Strong L6 answer.** All of the above, *plus* the **O(1) revocation
primitive** and the **native fast-path**:

- **Epoch / version bump revocation (the move).** Keep a monotonic integer
  per user — call it the *session epoch* — in a tiny side table keyed by
  `user_id`. Every issued session/token carries the epoch *at issue time*.
  Validation accepts the token only if `token.epoch == current_user_epoch`.
  "Log out everywhere" = **a single atomic `INCR` on the user's epoch** —
  O(1), no enumeration of sessions, and it invalidates every device at
  once. Same primitive powers revoke-on-password-change,
  revoke-on-compromise, and revoke-on-tenant-unenrollment.
- **The ~99% native fast-path, designed explicitly.** For native users the
  validation is: verify the token signature (or opaque-id lookup) **plus
  one O(1) side-table read of the user's current epoch** — *zero external
  calls, no IdP, no broker*. This is the dominant load (validations are
  ~1000× logins) so it must be the cheapest path. The epoch table is tiny
  (one int per user → ~8 GB for 1B users, fits in memory, regionally
  replicated), so the side-table lookup is sub-ms and cacheable with a
  short TTL bounded by the revocation SLA.
- **Revocation-propagation SLA, quantified and defended.** Two honest
  options: (a) **synchronous epoch check on every validation** → revocation
  is *instant* but every request pays the side-table read; (b) **cache the
  epoch with a TTL of T** at each validator → validation is local, but
  revocation takes up to T to propagate. Commit: "epoch cached with
  T = 5–10s for read paths; T = 0 (synchronous) for sensitive paths
  (payments, admin). So 'log out everywhere' is effective in ≤10s
  worst-case, instant on the paths that matter." This is the
  consistency-vs-cost call stated as a number.
- **Hybrid token shape.** Short-lived signed token (≤15 min) carrying
  `user_id` + `epoch` + `session_id` for the cheap local path; the epoch
  check is the revocation backstop so a stolen token dies on the next
  validation after the bump, not after `exp`. Refresh tokens are opaque
  and stored (rotated on use; reuse → revoke the family).
- **Session lifetime split by authority.** *Native* sessions are
  **sliding-window** (renew on activity, cap at N hours). *IdP-enforced
  federated* sessions are **fixed-window, no silent refresh** — they
  expire at the IdP's asserted session lifetime so a tenant's offboarding
  is honored without us having to poll the IdP. Tenant-scoped session is a
  *claim inside the existing cookie*, not a second cookie.

**Anti-signal.** "Log out everywhere = delete all their sessions from
Redis" (O(n), and races issuance) with no epoch/version idea; or "JWTs,
they self-validate" with no revocation answer at all. → Packet: *"No O(1)
revocation primitive; treated logout-everywhere as enumeration. Stateless
tokens with no pre-expiry kill switch — a stolen token is live until
exp."*

**Packet quote (Hire).**
> *"Per-user monotonic epoch in an O(1) side table; logout-everywhere is a
> single atomic increment, no session enumeration. Native validation is
> one signature check + one O(1) epoch read, zero external calls — sized
> for the 1000:1 read skew. Committed to a revocation SLA: ≤10s on cached
> read paths, synchronous (0s) on payment/admin. Sliding window for
> native, fixed window for IdP-enforced sessions."*

### Deep dive C: Multi-tenant IdP delegation & enforcement routing

**Phrasing.** *"Tenant A authenticates against Okta, Tenant B against
Entra, Tenant C is native. A login request arrives. Where does the 'which
IdP do I send this user to' decision live — and how is that decision not
an SSRF or open-redirect?"*

**Strong L5 answer.** A per-tenant config: tenant → IdP type + metadata
(issuer, JWKS URL, client creds). On login, resolve the tenant (from email
domain or a tenant hint), look up its IdP config, redirect accordingly.
Recognizes domain → tenant mapping must be verified (domain-verification
challenge) so one domain maps to exactly one tenant. Reasonable L5.

**Strong L6 answer.** All of the above, *plus* the **no-central-routing-
engine** and **fail-closed** framing:

- **Enforcement owned by the tenant, not a central engine.** The
  dangerous design is a central service that, at request time, reads a
  tenant-supplied URL/host from config or payload and dispatches to it —
  that's a config-injection / SSRF surface (a tenant could point you at
  `http://169.254.169.254/` or an internal host). Instead, the *set of
  supported IdP integrations is a code-level template map* — known
  integration types, with hosts pinned to vetted namespaces. A tenant
  *selects and configures within* a template (their Okta org id, their
  metadata), but **cannot inject an arbitrary host into the dispatch
  path**. Enforcement (the "you must SSO" rule, MFA requirements) belongs
  to the tenant's own policy, evaluated server-side — not a free-form
  central rules engine threading attacker-influenced strings.
- **Tenant resolution is verified, one authoritative tenant per user.**
  Domain → tenant via a verified domain-ownership challenge (DNS TXT);
  one user belongs to exactly one authoritative tenant (PK-enforced) so
  there's no ambiguity about *whose* IdP enforces them. Tenant-level
  config changes are O(1) (flip the tenant record), not a per-member
  fan-out.
- **Fail-closed for federated users (the call, with blast radius).** "If
  Tenant A's IdP — or our broker — is unreachable, Tenant A's federated
  users **cannot log in**. We fail *closed*. For authentication, fail-open
  means letting unauthenticated people in; never acceptable. Blast radius
  is scoped to *that tenant type* via a per-tenant-type circuit breaker —
  Okta being down does not affect Entra tenants or native users. Native
  users (the 99%) are entirely unaffected because their path never touches
  the broker." Then the honest mitigation: *existing* valid sessions keep
  working (we're the session authority, we don't need the IdP to validate
  an already-issued session); only *new* logins for the affected tenant
  fail. Break-glass admin accounts exist out-of-band for the tenant.
- **Broker isolation.** The federation broker (the component that talks
  N protocols to N IdPs) is isolated behind per-tenant-type circuit
  breakers so a slow/failing IdP can't exhaust a shared thread pool and
  brown out the whole broker (bulkhead).

**Anti-signal.** "We store each tenant's IdP redirect URL and redirect the
browser there" with no allowlist/pinning, or "we'd fail open so users
aren't locked out." → Packet: *"Routing took tenant-supplied hosts into
the dispatch path with no pinning — SSRF/open-redirect surface. Proposed
fail-open on IdP outage, i.e. admitting unauthenticated users."*

**Packet quote (Hire).**
> *"IdP routing is a code-level template map with hosts pinned to vetted
> namespaces — tenants configure within a template, can't inject a host;
> no central engine threading attacker-influenced URLs. One authoritative
> tenant per user via verified domain ownership. Fail-closed for federated
> logins on IdP/broker outage, blast radius scoped per-tenant-type via
> circuit breakers; existing sessions survive because we're the session
> authority; native users unaffected."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **Pass-through claims.** Forwarding the IdP token downstream, or
  trusting `email` as the identity. The account-takeover vector; close to
  disqualifying at L6 if unseen after one prompt.
- **Stateless JWT with no revocation story.** Self-validating tokens are
  fine *as an optimization* over a revocation backstop, not *instead of*
  one. No kill switch = a stolen token lives until `exp`.
- **Fail-open on the auth path.** Letting users in when the IdP is down.
  For authentication this is the wrong default; the candidate must reach
  fail-closed on their own.
- **One session model for native + federated.** Either taxes the 99% path
  or gives federated sessions native lifetimes (ignoring IdP offboarding).
- **Routing engine that eats config/payload hosts.** SSRF/open-redirect.
- **Auto-merge accounts on matching email.** Silent account-linking is a
  takeover primitive; consent must gate it.
- **Conflating authn and authz.** Designing RBAC/permissions when the
  question is *authentication*. Scope creep that eats the clock.
- **No revocation SLA number.** "It propagates eventually" — how fast?

### Interviewer-side (your own traps)

- **Letting them recite the OIDC dance for 15 minutes.** The redirect flow
  is a 5-minute conversation (and it's Question 7's territory). At minute
  10 redirect: *"Flow's correct. What becomes the identity?"*
- **Not driving to revocation.** "Issue a session" is easy; the signal is
  in *kill it fast*. If unprompted by minute 35, push the stolen-laptop
  scenario.
- **Leading them to epoch-bump or re-issue-own.** These are the answers; if
  you hand them over, the packet won't write convincingly. Use the
  stolen-laptop and email-spoof prompts and let them get there.
- **Accepting "fail closed" without the blast radius.** The level-up is
  *who is affected* — federated only, scoped per tenant type, natives
  untouched, existing sessions survive.
- **Eating the candidate's question window.** Still scoring Googleyness.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it.
Numbers explicit, trade-offs committed.

### 6.1 Functional requirements (committed scope)

v1: **native login** (password/passkey) and **federated login** (tenant
brings an OIDC/SAML IdP); **session issuance** (a cookie/token the user's
browser and downstream services trust); **session validation** (the hot,
read-heavy path); **logout** — single-session *and* global
("log out everywhere"); **a token downstream services can verify** without
calling us on every request; **account linking** (native ↔ external),
opt-in and consented.

**Out of scope v1, said out loud:** authorization / RBAC / permissions
(we *authenticate*, a separate service authorizes); user-profile CRUD;
MFA *enrollment* UX (we support MFA *signal* in the session but the
enrollment flow is its own surface); the OIDC protocol internals (the
`code`/`state`/PKCE mechanics — that's a deep-dive, not the platform).

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| Logins/sec (write) | **~5k peak** | 100M DAU, most log in ~once/day, 5× peak concentration → low thousands/sec. Logins are the cold path. |
| Validations/sec (read) | **~5M peak** | Every request to every product validates a session. ~1000:1 read:write. This dominates the design. |
| % native vs. federated | **~99% native / ~1% federated** | Consumer + the bulk of enterprise daily traffic is already-logged-in native sessions; federated *logins* are a thin slice of the cold path. |
| Session-validation p99 | **<5ms server-side** | It's on the critical path of *every* product request. Must be O(1), local, zero external calls. |
| Login p99 (native) | **<300ms** | Cold path; includes credential check + session mint. |
| Login p99 (federated) | **<2s** | Cold path; includes a redirect round trip to someone else's server. |
| Revocation propagation SLA | **≤10s read paths, 0s (synchronous) sensitive paths** | Security SLA. "Log out everywhere" must be fast and bounded. |
| Availability — validation | **99.99%** | If validation is down, every product is down. Customer-facing number. |
| Availability — login | **99.9%** | Lower bar; a failed login is retryable, and native is decoupled from federated. |
| Token / cookie size | **<1 KB** | Rides every request header; keep claims minimal (`user_id`, `epoch`, `session_id`, `tenant_id`, `aal`). |
| Session store size | **~8 GB epoch side-table for 1B users**; ~hundreds of GB for full session records | Epoch table is one int/user → trivially in-memory and replicated. |

### 6.3 Capacity estimation (worked)

- **Epoch side-table.** 1B users × (8 B user_id + 8 B epoch + overhead) ≈
  **~16–24 GB**. Fits in memory, regionally replicated. This is why the
  O(1) revocation check is cheap.
- **Full session records.** Say 100M concurrent sessions × ~500 B ≈
  **50 GB**, sharded KV. Read-through cache in front.
- **Validation load.** 5M validations/sec. If each were a network read to
  a session store, that's 5M QPS to the store — large but feasible
  sharded. The optimization: validate the *signed token locally*
  (signature + claims) and only consult the **epoch side-table** (cached,
  TTL = revocation SLA) — so steady-state store QPS is dominated by epoch
  reads, mostly served from local cache.
- **Federated logins.** 1% of 5k logins/sec = ~50 federated logins/sec →
  ~50 broker→IdP round trips/sec. Tiny. The broker is *not* a throughput
  problem; it's a *failure-isolation* problem.

**Numbers that changed a design choice:**
- 1000:1 read:write → validation must be O(1) and local; revocation can be
  slightly eventual (≤10s). The skew is *why* epoch-bump beats per-request
  store reads.
- 99% native → the validation path must never touch the broker/IdP; the
  1% federation machinery sits entirely off the hot path.
- 50 federated logins/sec → broker is sized for isolation, not scale.

### 6.4 API design

```
POST /v1/login              { tenant_hint?, credentials? }       (native)
                            → 200 {session} | 401 | 302→IdP (federated tenant)
GET  /v1/authorize          (federated entry; → redirect to tenant IdP)
GET  /v1/callback           ?code=&state=   (IdP redirect back; server
                            redeems code S2S, validates, mints OUR session)
POST /v1/sessions/validate  { token }   → { valid, user_id, tenant_id, aal }
                            (most callers verify the signed token locally;
                             this endpoint is for opaque-token / introspect)
POST /v1/logout             { session_id }            → 204   (single)
POST /v1/logout-all         { user_id }               → 204   (epoch INCR)
POST /v1/accounts/link      { external_idp, ... }     (authed + consent)
POST /v1/tenants/:id/idp    { template_type, config } (admin; template map)
```

`token` is a short-lived signed JWT: `{ user_id, tenant_id, epoch,
session_id, aal, iss=us, exp≤15m }`. Refresh tokens are opaque, stored,
rotated on use.

### 6.5 Data model

- **`users`** — `user_id` (PK, our stable internal subject), `tenant_id`
  (the *one* authoritative tenant, PK-enforced), `credential_ref` (native),
  status. The `user_id` is what downstream sees — never the IdP's `sub`.
- **`user_epoch`** — `user_id` → `epoch` (monotonic int). **The revocation
  side-table.** In-memory, replicated. The whole "log out everywhere"
  story lives here.
- **`identity_links`** — `(tenant_id, idp_issuer, idp_subject)` → `user_id`.
  Federated identities linked on **issuer+subject**, never bare email.
  Linking is consented.
- **`sessions`** — `session_id` → `{ user_id, device, created_at,
  expires_at, window_type (sliding|fixed), aal, refresh_token_hash }`.
- **`tenants`** — `tenant_id`, verified domains, `idp_template_type`
  (enum, code-level), `idp_config` (org id, metadata — *within* a template,
  no free-form hosts), enforcement policy (require_sso, min_aal).

### 6.6 High-level architecture

```
        Native users (99%)                 Federated users (1%)
              │                                    │
              ▼                                    ▼
   ┌─────────────────────────────────────────────────────────┐
   │                   Edge / GFE / L7 LB                      │
   └───────────────┬───────────────────────────┬─────────────┘
                   │                            │
        ┌──────────▼──────────┐      ┌──────────▼───────────┐
        │   Auth Service      │      │   Auth Service        │
        │   (login + token)   │      │   (authorize/callback)│
        │   - native cred chk │      │   - tenant resolve    │
        │   - mint OUR session│      │   - dispatch to IdP    │
        └──────┬───────┬──────┘      └──────────┬───────────┘
               │       │                        │ (S2S code redeem,
   ┌───────────▼──┐ ┌──▼───────────┐            │  validate, then
   │ Credential   │ │  user_epoch  │            ▼  RE-ISSUE OUR id)
   │ Store        │ │  side-table  │   ┌────────────────────────┐
   │ (passwords/  │ │  (O(1), ~16GB│   │   Federation Broker    │
   │  passkeys)   │ │  in-mem repl)│   │  (template map; per-   │
   └──────────────┘ └──────┬───────┘   │  tenant-type circuit   │
                           │           │  breakers / bulkheads) │
        ┌──────────────────▼───────┐   └────────┬───────────────┘
        │   Session Store (sharded │            │ pinned hosts only
        │   KV + read cache)       │            ▼
        └──────────────────────────┘   ┌────────────────────────┐
                                        │  Tenant IdPs           │
   Validation path (5M/s, the hot one): │  Okta / Entra / ...    │
   service → verify signed token locally └────────────────────────┘
        → check user_epoch (cached, TTL = revocation SLA)
        → zero external calls for native; never touches the broker
```

### 6.7 The auth flow & who is the authority (attestation handoff)

**Native (99%):** client → Auth Service → verify credential (password
hash / passkey assertion) → mint **our** signed token `{user_id, epoch,
session_id, aal}` → set cookie. No external calls.

**Federated (1%):** client → `/authorize` → resolve tenant (verified
domain → one authoritative tenant) → broker dispatches to the tenant's
IdP **via the pinned template** (not a config-injected host) → IdP
authenticates → redirects back to `/callback` with an opaque single-use
`code` → Auth Service **redeems the code server-to-server**, validates the
ID token (sig via JWKS, `iss`/`aud`/`exp`/`nonce`) → **maps `(iss,sub)` to
our `user_id`** (consented link if first time) → **mints OUR session**.

The boundary, stated: **the IdP attests; we are the session authority.**
The IdP's claims never leave the callback handler. Downstream services
trust exactly one issuer — us — and see exactly one identity — our
`user_id`. This (a) keeps trust to one key set, (b) makes a
tenant-controlled `email` claim *incapable* of becoming someone else's
identity, and (c) lets us revoke without the IdP.

### 6.8 Session issuance + revocation (the hard part)

- **Issue:** signed token (≤15 min) carrying `epoch` at issue + opaque,
  rotating refresh token (stored; reuse → revoke the family).
- **Validate (hot path):** verify signature locally + read `user_epoch`
  (cached, TTL = revocation SLA). Accept iff `token.epoch ==
  current_epoch`. O(1), no broker, no IdP.
- **Revoke one session:** delete the session record + invalidate its
  refresh family.
- **Log out everywhere:** **one atomic `INCR` on `user_epoch`.** Every
  outstanding token now mismatches on next validation. O(1); no
  enumeration. Same primitive for password-change, compromise,
  tenant-unenrollment.
- **Revocation SLA:** epoch cached with TTL = 5–10s on read paths (so
  global logout is effective ≤10s) and synchronously read (TTL 0) on
  sensitive paths (payments/admin), which pay one extra in-memory read.
- **Lifetime by authority:** native = sliding window (renew on activity,
  cap N hours); IdP-enforced federated = **fixed window, no silent
  refresh** so the tenant's offboarding is honored without polling.
  Tenant-scope and `aal` (step-up level) are *claims inside the one
  cookie*, not separate cookies; `aal` is cleared on revoke.

### 6.9 Multi-tenant delegation & enforcement routing

- **Tenant resolution:** verified domain ownership (DNS TXT) → exactly
  one authoritative tenant per user (PK-enforced). Tenant-level changes
  are O(1), not per-member fan-out.
- **No central routing engine:** supported IdP integrations are a
  **code-level template map**; tenants configure *within* a template
  (their org id, metadata). Hosts are pinned to vetted namespaces —
  **no tenant-supplied host enters the dispatch path** (kills
  SSRF/open-redirect).
- **Enforcement owned by the tenant:** "require SSO," "min AAL2" are the
  tenant's policy, evaluated server-side per the tenant record — not a
  free-form central rules engine.
- **Broker isolation:** per-tenant-type circuit breakers + bulkheads so a
  failing Okta can't brown out Entra or native.

### 6.10 Multi-region / consistency commitments

CAP commits, said out loud:

- **Validation: AP, eventually-consistent revocation.** The epoch
  side-table is replicated to every region; reads are local. A revocation
  `INCR` propagates within the cache TTL (≤10s). We *choose* this
  staleness on read paths because validation must stay local and fast even
  during a region partition. Sensitive paths read synchronously from the
  authoritative epoch (CP for those, accepting the cross-region read).
- **Login: CP on the credential/identity write.** Account creation,
  identity-link, and epoch bumps are serialized (single authoritative
  region or Spanner-class store) — these are low-QPS and must be globally
  agreed (you can't have two regions disagree on whether a user is
  revoked).
- **Session records: AP**, region-local with async replication; a session
  minted in EU is usable in US within replication lag, acceptable on the
  cold login path.

### 6.11 Cost (back-of-envelope, monthly)

| Component | Notes | $/mo |
|---|---|---|
| Validation fleet | ~5M QPS, mostly local token verify + cached epoch read; CPU-bound | ~$40k |
| Epoch side-table + session store | in-mem replicated (~16 GB epoch) + sharded session KV + cache | ~$30k |
| Credential store | passwords/passkeys, low QPS, high durability | ~$10k |
| Federation broker | ~50 logins/sec; sized for isolation not scale | ~$5k |
| Identity write store (CP) | Spanner-class for accounts/links/epoch authority, low QPS | ~$15k |
| **Total** | | **~$100k/mo** |

**Dominator:** the validation fleet (the 5M QPS read path) — which is
*exactly why* the design spends its complexity budget making that path
O(1) and local. If validation synchronously hit a session store at 5M QPS
cross-region, store cost alone would multiply 5–10×.

### 6.12 Failure modes & blast radius

| Failure | Blast radius | Behavior |
|---|---|---|
| Tenant IdP down | That tenant's *new* federated logins only | **Fail closed** (no unauthenticated entry). Existing sessions survive (we're the authority). Circuit breaker isolates per-tenant-type. Break-glass admin out-of-band. |
| Federation broker down | All federated *new* logins | Fail closed; **native users (99%) unaffected** — their path never touches the broker. Existing sessions survive. |
| Epoch side-table region down | Validation in that region | Fail over to replica; if truly unreachable, **fail closed on sensitive paths**, serve from last-known cache on read paths within TTL. |
| Session store shard down | Sessions on that shard | Read-through cache absorbs; new sessions route to healthy shards. |
| Credential store down | New native logins | Fail closed; existing sessions unaffected. |
| Signing key compromise | Catastrophic — any token forgeable | Key rotation + short token TTL bound the window; emergency = bump *all* epochs (global re-auth). |

**SLO/error budget:** 99.99% validation → 4.32 min/mo. Page on epoch-cache
staleness exceeding SLA and on per-tenant-type circuit-breaker trips.

### 6.13 Evolution at 10× (50M seats / 10k tenants / 50M validations/sec)

- **Validation:** scale the fleet ~linearly; epoch table still fits in
  memory (one int/user); the O(1) local design is the reason 10× is a
  knob, not a redesign.
- **Revocation:** epoch-bump is O(1) per user regardless of fleet size —
  unchanged.
- **Federation broker:** more IdP *types* and tenants, but logins/sec
  still tiny; the work is *more circuit-breaker domains*, not throughput.
  The named seam: at thousands of tenant types, the template map graduates
  to a vetted plugin registry (still code-reviewed, still host-pinned).
- **Multi-region:** epoch replication is the seam that gets more expensive;
  if revocation SLA must tighten under partition, move sensitive-path
  epoch reads to a Spanner-class strongly-consistent store for that slice.
- **What does *not* change:** the authority boundary (re-issue-own
  identity), the token shape, the native fast-path, fail-closed.

**Org seams (what I'd delegate vs. own):** I'd own the **authority
boundary and the session/revocation model** personally — they're the
security-load-bearing core. The **federation broker** I'd hand to a team
that already runs protocol integrations (it's N-protocol grunt work behind
a stable contract). The **credential store** (passwords/passkeys/MFA
enrollment) is its own team with its own compliance surface. The clean
contract between them is exactly the attestation handoff.

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence; right is the call.

| Evidence | Call |
|---|---|
| No commit to logins/sec or validations/sec after two prompts; "secure and scalable." Conflated authn with authz. | **Strong No Hire** |
| Drew the OIDC flow but forwarded the IdP's token downstream / trusted the `email` claim as identity; didn't see the takeover vector when prompted. | **No Hire** |
| Stateful sessions, but "log out everywhere = delete all sessions"; no O(1) primitive; stateless-JWT alternative had no revocation answer. | **Lean No Hire** |
| Numbers by min 12 (5k logins/sec, ~5M validations/sec, 1000:1). Correct OIDC flow; separated IdP (proves identity) from own session. Picked stateful sessions for revocability and defended it. Named "fail closed if IdP down" when asked. Handled multi-tenant config cleanly. Did **not** volunteer re-issue-own-identity, epoch-bump, or the native fast-path. | **Hire L5** |
| All of L5, **unprompted**: stated re-issue-own-identity as a boundary; proposed epoch/version-bump for O(1) global logout; designed the 99% native path as zero-external-call O(1); committed to a revocation SLA number; reached fail-closed-for-federated on their own with a basic blast-radius. | **Hire L5 / Lean L6** |
| All of L5-Hire-plus, **plus**: flagged the tenant-admin email-spoof vector and gated account-linking behind opt-in consent unprompted; bounded revocation SLA per path (≤10s read / 0s sensitive); refused a central routing engine and pinned IdP hosts to a template map (SSRF-aware); scoped IdP-outage blast radius per-tenant-type with circuit breakers and noted existing sessions survive + natives unaffected; surfaced $/mo with the validation fleet as dominator; native sliding vs. federated fixed-window lifetimes. | **Hire L6** |
| Everything in L6, **plus**: named what they'd own (authority boundary + revocation model) vs. delegate (broker, credential store) and *why* the attestation handoff is the clean contract; defended the AP-validation / CP-write CAP split against pushback with a quantified staleness argument; closed with a self-aware retro (MFA step-up, device trust, key-compromise drill). | **Strong Hire L6** |

---

## Sources

- Auth0 — *Federated Identity vs. Single Sign-On: Key Differences*:
  https://auth0.com/blog/federated-identity-vs-single-sign-on-key-differences/
- Ping Identity — *SSO vs. Federated Identity Management*:
  https://www.pingidentity.com/en/resources/blog/post/sso-vs-federated-identity-management.html
- WorkOS — *OIDC vs SAML: how a two-decade-old protocol still dominates
  identity federation*:
  https://workos.com/blog/oidc-vs-saml-two-decade-old-protocol-dominates-identity-federation
- Cisco Duo — *SAML vs OAuth vs OIDC: key differences explained*:
  https://duo.com/learn/saml-vs-oauth-vs-oidc
- Ory — *Everything you need to know about secure account linking*
  (email-claim trust, link-on-login, consent as anti-hijack):
  https://www.ory.com/blog/secure-account-linking-iam-sso-oidc-saml
- OneUptime — *Session revocation / logout all devices with Redis*
  (version-counter / set-based revocation at scale):
  https://oneuptime.com/blog/post/2026-03-31-redis-session-revocation-logout-all-devices/view
- OneUptime — *How to handle JWT revocation* (opaque-vs-JWT,
  introspection, blacklist, versioning):
  https://oneuptime.com/blog/post/2026-02-02-jwt-revocation/view
- SkyCloak — *JWT Token Lifecycle Management: expiration, refresh,
  revocation strategies*:
  https://skycloak.io/blog/jwt-token-lifecycle-management-expiration-refresh-revocation-strategies/
- Firebase Authentication — *Manage user sessions* (revocation timestamp /
  epoch-style invalidation, Google's own approach):
  https://firebase.google.com/docs/auth/admin/manage-sessions
- CyberReplay — *When SSO Goes Wrong: misconfiguration mitigation*
  (IdP-down SPOF, break-glass, fail-closed reasoning):
  https://cyberreplay.com/blog/when-sso-goes-wrong-sso-misconfiguration-mitigation/
- Hello Interview — system-design delivery framework & Google L6 guide
  (calibration): https://www.hellointerview.com/guides/google/l6

---

*End of guide. Related:* `07-oauth-oidc.md` *(the protocol round trip in
full — `state`/PKCE/code redemption) and* `10-session-management.md`
*(the distributed session store and revocation, gone deeper).*
