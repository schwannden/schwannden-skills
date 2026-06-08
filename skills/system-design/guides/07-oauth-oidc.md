# Question 7: OAuth 2.0 / OpenID Connect Authorization-Code Flow

> Interviewer's guide for the 1-hour Google L5/L6 system-design round.
> Anchor problem for the **protocol-security / browser-redirect-flow**
> archetype. The flow is canonical (RFC 6749, RFC 7636 PKCE, OpenID Connect
> Core, and the 2025 security BCP RFC 9700) — so the calibration value is
> *not* whether the candidate can recite "authorize → code → token." It is
> whether they can walk the three-party browser-redirect dance end to end,
> name the attacks each parameter stops, and reason about it as a
> security-critical *platform* serving thousands of clients. This is the
> most security-heavy question in the rotation; the L6 separator is depth
> on the attacks and the precise mechanisms that defeat them.

---

## 1. Why this question (interviewer's framing)

OAuth looks like a protocol-recall question, and a prepared L4 will treat
it as one: "the client redirects to `/authorize`, gets a code back,
exchanges it at `/token`, done." That recital is table stakes. It is **not
the question being asked.** The question is: *the browser is a hostile,
shared, attacker-reachable channel sitting between three parties who don't
trust each other — what do you put on the wire, what do you keep off it,
and what breaks when an attacker controls one leg of the dance?*

That forces explicit reasoning on five axes:

- **Why the code flow at all.** The authorization code exists so the
  high-value token never rides the front channel (the browser
  redirect). The candidate who can't articulate *front channel vs back
  channel* doesn't understand the protocol's whole reason for being.
- **The `state` parameter is doing double duty.** It is the login-CSRF
  defense (binds the callback to *this* browser's outbound request via a
  cookie) *and* a cross-flow binding token (binds the handoff response to
  the session that initiated it). Most candidates know one of these uses.
  The L6 separator is naming both and walking the attack each stops.
- **PKCE and the code-injection attack.** A stolen or injected code is
  worthless without the `code_verifier`. The candidate must walk the
  injection attack and show *exactly* where PKCE breaks it.
- **The code store is a security-critical, single-use, short-TTL
  artifact.** Opaque, high-entropy, ~30–60s TTL, atomic single-use
  redemption (GETDEL). "Store the code in a table" without the
  single-use-under-concurrency story is an L5 ceiling.
- **Token design, refresh, revocation at scale.** ID token vs access
  token (who is the audience?), JWT-vs-opaque and the
  validation-vs-revocation trade-off, refresh-token rotation with reuse
  detection. This is where the protocol meets real operations.

### What "Hire" looks like at each level

**L5 Hire.** Walks authorize → code → token cleanly, with the redirect
hops correct. Knows `state` defends CSRF and PKCE defends code injection,
and can sketch *how* for at least one of them. Commits to a short code TTL
and single-use codes. Distinguishes ID token (authentication, audience =
client) from access token (authorization, audience = resource server).
Names exact `redirect_uri` matching. Handles "what if the code leaks?"
calmly.

**L6 Hire.** All of the above, plus: **drives the room** (narrates the
budget, picks the deep dives). Explains the front-channel/back-channel
split as the *design principle* the whole flow exists to serve, and keeps
PII off the front channel as a consequence. Names `state`'s **double
duty** unprompted and walks the cross-tenant code-injection attack end to
end, showing precisely where the cookie↔URL binding breaks it. Commits to
**atomic single-use redemption (GETDEL)** as the replay guard and reasons
about the race. Picks JWT-vs-opaque per token *with the revocation cost
named*, designs refresh rotation with reuse detection, and gives
authorize/redemption QPS and code-store sizing. States the threat model
out loud and reasons about blast radius (one leaked code → one session;
one leaked signing key → every token).

### Classic downlevel traps

1. **Confusing the implicit flow with the code flow** — putting the access
   token in the redirect fragment "to save a round trip." The implicit
   flow is deprecated by RFC 9700 precisely because it leaks tokens to the
   front channel. Proposing it in 2026 is close to disqualifying.
2. **`state` as "just a nonce" or "just CSRF."** Naming one use and
   missing that it's bound to a *cookie* (not just remembered
   server-side) is the modal L5 miss. Missing the binding entirely is
   lower.
3. **PKCE described as "an extra hash" with no attack.** If they can't
   walk *what* it stops (injection of an attacker-obtained code), they're
   performing knowledge.
4. **Wildcard / prefix `redirect_uri` matching.** "We allow
   `https://client.com/*`" — that's an open-redirect-to-code-exfiltration
   hole. Exact-match is the BCP requirement.
5. **Using the ID token to call APIs**, or the access token to identify
   the user. Wrong audience for each — a real-world account-confusion bug.
6. **JWT everything with no revocation story.** "It's stateless, just
   verify the signature" — then a logged-out/compromised token is valid
   until expiry. At L6, silence on revocation is a finding.

---

## 2. The 60-minute plan

`0–5 Intro · 5–15 Requirements & scope · 15–25 Capacity + high-level
design · 25–45 Deep dives · 45–55 Evolution / curveball · 55–60 Wrap`

### 0–5 min — Intro

**Say:** *"I'm <name>, L7 on an unrelated infra team. 60-second intro,
then: design the OAuth 2.0 / OpenID Connect authorization-code flow — the
protocol itself, as a platform that issues tokens to thousands of
relying-party apps. Think 'Sign in with <us>'. Drive it however you want;
I'll interject."*

**Listen for:** do they restate the three parties (resource owner /
user-agent, client / relying party, authorization server) and the
front-channel/back-channel distinction, or jump to drawing endpoints?
**Push back when:** they whiteboard endpoints before naming the trust
model. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** almost nothing. If asked "which grant?" → *"You tell me which one
and why."* If asked "do we support refresh / OIDC?" → *"What would you
commit to for v1, and what would you cut?"*

**Listen for:**
- Functional commit: authorization-code grant with **PKCE**; OIDC layer
  (ID token + UserInfo); refresh tokens; token revocation; `redirect_uri`
  registration. Bonus for explicitly cutting implicit / ROPC / device flow
  from v1.
- Non-functionals **with numbers**: authorize QPS, token-redemption QPS,
  code TTL, access/refresh token TTL, token-validation p99, revocation
  propagation SLA.
- A stated **threat model**: this is the rare question where "what's the
  attacker's capability" *is* the requirements conversation.

**Push back when:**
- "Secure" with no threat model → *"Secure against whom, doing what?"*
- They pick implicit flow → *"Where does the token live during the
  redirect? Who can read a URL fragment?"*
- 8 grant types → *"Smallest useful v1. Which one grant?"*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip math, *"Before we draw — what's the
QPS split between authorize, redeem, and validate? That changes the
storage."*

**Listen for:**
- The split: **validation** dwarfs **redemption** dwarfs **authorize**
  (validation is per-API-call; authorize/redeem are per-login). This
  ratio drives the JWT-vs-opaque decision.
- Code-store sizing from authorize QPS × code TTL.
- Box diagram: User-agent ⇄ Authorization Server (`/authorize`,
  `/token`, JWKS, UserInfo, `/revoke`) ⇄ Client backend; the code store
  and the session/consent store called out as separate stateful pieces.

**Push back when:**
- All endpoints drawn as one box → *"Which of these is on the hot path of
  every API call vs. once per login?"*
- Reflexive "put it all in one database" → *"What's the read pattern on
  the code store vs. the token store? They're nothing alike."*

### 25–45 min — Deep dives

The diagnostic phase. **Two are mandatory; the third is dealer's choice.**

1. **The authorization-code round trip end to end** (mandatory) — every
   hop, what's on each wire, front vs back channel.
2. **`state` + PKCE and the attacks they stop** (mandatory) — login-CSRF
   and cross-tenant code injection, walked as attacks.
3. **Token design / refresh / revocation** (dealer's choice, but push here
   if they volunteered the first two fast).

**Say:** *"An attacker starts an OAuth flow on their own account, captures
their own authorization code, and gets your logged-in victim's browser to
redeem it against the client. Walk me through the next few hops. Where
does it break — and if it doesn't, what did you forget?"*

**Listen for:** structured attack-walks (name attacker capability, trace
each hop, show the exact check that fails the attack), the `state`
cookie↔URL binding, PKCE verifier check, single-use code redemption.
For L6: blast-radius framing, and keeping claims off the front channel.

**Push back when:** hand-waving → *"Say the actual check. What field, on
which server, compared against what?"* Textbook-but-undefended → *"You
said PKCE stops this. Show me the request where it fails the attacker."*

### 45–55 min — Evolution / curveball

Pick **one**:
- *"Your token-signing key is suspected compromised. Walk me through the
  next hour."* (key rotation, JWKS `kid`, denylist, refresh reuse.)
- *"A confused-deputy / mix-up attack: the user authenticated at the wrong
  authorization server. How does the client know?"* (`iss` in the
  response; per-AS `redirect_uri`.)
- *"10× the relying-party apps overnight, many low-trust. What changes?"*
  (per-client PKCE-required, exact-match registration review, consent.)

**Listen for:** do they name the seam to change, or redesign? L5 picks one
well; L6 picks one fluently and gestures at the others.

### 55–60 min — Wrap

**Say:** *"Time. What would you do differently with 15 more minutes?
Then — questions for me?"*

**Still scoring:** self-aware retro ("I didn't get to consent-screen
phishing / dynamic client registration") and the quality of their
questions.

---

## 3. Probing prompts (the kit)

Pre-loaded, with the signal each one hunts.

| Prompt | Signal hunted |
|---|---|
| *"Why a code at all? Why not return the token directly?"* | Front-channel/back-channel split — the protocol's whole reason for being. |
| *"Where does the access token live during the redirect?"* | Trap for implicit-flow thinking. Token must never touch the browser URL. |
| *"What's in the `/authorize` request? Name every parameter."* | `client_id`, `redirect_uri`, `response_type`, `scope`, `state`, `code_challenge`, `nonce` (OIDC). Completeness. |
| *"What does `state` defend against? Be specific."* | Login-CSRF *and* cross-flow binding. Naming one only = partial. |
| *"`state` lives where between request and callback — server, cookie, both?"* | The cookie↔URL binding. "Server-side map" alone misses login-CSRF. |
| *"Walk me through PKCE. What attack does it stop that `state` doesn't?"* | Code injection of an attacker-obtained code; verifier↔challenge binding. |
| *"Code TTL? Single-use? What enforces single-use under a double-redeem race?"* | Atomic GETDEL / conditional-delete. Replay guard under concurrency. |
| *"An attacker injects their own code into the victim's session. Trace it."* | The marquee attack. `state` + PKCE both have to fire. |
| *"How do you validate `redirect_uri`? Exact match or pattern?"* | Exact-match BCP; open-redirect-to-exfiltration awareness. |
| *"ID token vs access token — who's the audience for each?"* | Authentication vs authorization; client vs resource server. |
| *"JWT or opaque access token? What did revocation cost you?"* | The validation-vs-revocation trade-off, named. |
| *"Token leaks. How fast can you kill it, and what's still valid?"* | Revocation propagation; denylist vs short-TTL+rotation. |
| *"Refresh token gets stolen and replayed. What happens?"* | Rotation + reuse detection → revoke the family. |
| *"Signing key compromised. Walk me through the hour."* | `kid`-based rotation, JWKS, blast radius (every token). |
| *"What QPS hits `/authorize` vs `/token` vs token validation?"* | The ratio that drives JWT-vs-opaque. |
| *"What claims ride the browser redirect URL?"* | PII-free front channel. The answer should be: *none of value.* |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

I steer toward **two of three**, depending on what the candidate
self-selected. The first two are the security spine.

### Deep dive A: the authorization-code round trip end to end

**Phrasing.** *"Walk me through every hop from 'user clicks Sign in' to
'client holds an access token.' Tell me which channel each message is on
and what's on the wire. Then tell me what would change if I told you the
browser is fully attacker-observable."*

**Strong L5 answer.** The five hops, correct: (1) client redirects the
browser to `/authorize` with `client_id`, `redirect_uri`, `response_type=
code`, `scope`, `state`, `code_challenge`; (2) AS authenticates the user
and gets consent; (3) AS redirects back to `redirect_uri` with `code` and
`state`; (4) client's **backend** POSTs to `/token` with `code`,
`redirect_uri`, `client_id`, client secret, and `code_verifier`; (5) AS
returns access token (+ ID token + refresh token). Names that step 4 is
server-to-server. Knows the code is short-lived and single-use.

**Strong L6 answer.** All of the above, plus:
- **Names the front-channel/back-channel split as the design principle.**
  Steps 1–3 are the *front channel* — they ride the browser redirect,
  which is logged in history, leaks via `Referer`, sits in proxies, and is
  fully attacker-observable. So the front channel carries only a
  *one-time, opaque, low-value* artifact: the code. The *back channel*
  (step 4) is a direct TLS server-to-server call the browser never sees —
  that's where the high-value tokens flow. "The code exists so the token
  never rides the browser."
- **PII-free browser hop, stated as a rule.** No identity claims, no
  email, no tokens on the URL, fragment, or anything a `Referer` header
  could carry. The browser only ever holds the opaque code and `state`.
  Any user identity is redeemed **server-to-server**. This is the same
  discipline behind a broker handing a relying party an opaque one-time
  handoff code rather than raw IdP claims through the browser.
- **The code is opaque and high-entropy** (≥128 bits), not a JWT, not
  guessable, carries no embedded claims — so even if observed, it reveals
  nothing and is useless without the back-channel exchange + PKCE verifier.
- Confidential vs public client: confidential clients add a client secret
  in step 4; public clients (SPAs, mobile) can't keep a secret, so **PKCE
  is mandatory** for them (RFC 9700) and recommended for everyone.

**Anti-signal.** "We could skip the code and return the token in the
redirect to save a round trip" (implicit flow), or putting any claim/PII
on the redirect URL. → Packet: *"Proposed returning the token on the front
channel; did not grasp that the code exists precisely to keep tokens off
the attacker-observable browser channel."*

**Packet quote (Hire).**
> *"Articulated the front-channel/back-channel split as the reason the
> code grant exists — opaque single-use code on the browser hop, tokens
> only on the server-to-server back channel, zero PII on the redirect URL.
> Unprompted."*

### Deep dive B: `state` + PKCE and the attacks they stop

**Phrasing.** *"You return a `code` and a `state` on the callback, and the
client sends a `code_verifier` at redemption. I'm an attacker. Walk me
through (1) a login-CSRF attack and (2) a code-injection attack, and show
me the exact check that fails me in each."*

**Strong L5 answer.** *Login-CSRF:* `state` is a random value the client
generates per flow, remembers, and checks on callback; if it doesn't match,
reject — so an attacker can't forge a callback that logs the victim into
the attacker's account. *Code injection / PKCE:* the client hashes a
random `code_verifier` into a `code_challenge` sent at `/authorize`, and
sends the raw `code_verifier` at `/token`; the AS recomputes the hash and
must match — so a code stolen by an attacker can't be redeemed without the
verifier. Correct, mechanical.

**Strong L6 answer.** All of the above, plus the precise bindings:

- **`state` does double duty.** (1) *Login-CSRF defense via cookie↔URL
  binding:* the client doesn't just remember `state` server-side — it
  binds `state` to **this browser** by also storing it (or a hash of it)
  in a cookie scoped to the client. On callback it requires
  `state_in_URL == state_in_cookie`. A server-side-only map is forgeable
  across browsers; the cookie binding is what proves *this* browser
  initiated *this* flow. (2) *Cross-flow binding:* `state` ties the
  handoff response (the callback) back to the specific browser session
  that started the flow — so a response generated for one session can't be
  replayed into another. This is the same pattern as a broker binding its
  one-time handoff code to the originating session so it can't be
  cross-injected.

- **The cross-tenant code-injection attack, walked end to end.** The
  attacker's capability: they can start a legitimate flow on *their own*
  account and obtain a *valid* authorization code (no theft needed —
  it's their code). Goal: get the **victim's** browser to redeem the
  attacker's code at the client, so the victim's client session ends up
  bound to the *attacker's* identity (account confusion / data written
  into the attacker's account, or session-fixation in reverse).
  1. Attacker authenticates, captures their own valid `code_A`.
  2. Attacker crafts a callback URL to the client's `redirect_uri`
     carrying `code_A` and tricks the victim's browser into following it.
  3. **Where `state` breaks it:** the victim's browser never initiated a
     flow, so it has **no matching `state` cookie**. `state_in_URL`
     (attacker-supplied or absent) ≠ `state_in_cookie` (absent/different)
     → client rejects the callback before redemption. The cross-flow
     binding means the attacker can't mint a `state` that matches the
     *victim's* browser, because they don't control the victim's cookie.
  4. **Where PKCE breaks it (defense in depth):** even if `state` were
     somehow bypassed, the attacker's `code_A` was issued against the
     *attacker's* `code_challenge`. The victim's client redeems with the
     *victim's flow's* `code_verifier`, which doesn't hash to the
     attacker's challenge → AS rejects at `/token`. The code is bound to
     the verifier of the flow that requested it.

  Two independent mechanisms must both fail for the attack to land — that
  is the defense-in-depth posture RFC 9700 is built around.

- **Exact-match `redirect_uri` (open-redirect defense).** The AS validates
  `redirect_uri` against the client's pre-registered values by **exact
  string match**, never prefix/wildcard. If you allow
  `https://client.com/*` and the client has an open redirect anywhere on
  that origin, the attacker chains it: AS sends the code to the registered
  origin, the open redirect bounces it (with the code in the URL) to the
  attacker. Same discipline applies to a `return_to` / post-login
  landing-page parameter: **allowlist it**, never reflect an arbitrary
  URL, or you've built an open redirect that also leaks the code via
  `Referer`. URL hosts should be pinned to a known namespace, not taken
  from the request payload.

**Anti-signal.** "`state` is just a CSRF nonce we check server-side" (misses
the cookie binding), or "PKCE is just an extra hash" (no attack), or
allowing wildcard `redirect_uri`. → Packet: *"Described `state` as a
server-side nonce only; did not identify the cookie↔URL binding or that
`state` also provides cross-flow binding; could not walk the code-injection
attack to the failing check."*

**Packet quote (Hire).**
> *"Walked the cross-tenant code-injection attack to the exact failing
> check: victim's browser has no matching `state` cookie, so the
> cookie↔URL binding rejects the forged callback; PKCE verifier mismatch
> is the defense-in-depth backstop. Named exact-match `redirect_uri` and
> `return_to` allowlisting as the open-redirect defense. Unprompted."*

### Deep dive C: token design, refresh, and revocation

**Phrasing.** *"You've issued an access token, an ID token, and a refresh
token. For each: who's the audience, how does the recipient validate it,
and how do I revoke it when an account is compromised?"*

**Strong L5 answer.** *ID token:* a signed JWT, **audience = the client**,
answers "who is the user and how did they authenticate" (`sub`, `iss`,
`aud`, `exp`, `iat`, `nonce`, identity claims). Used for login, never to
call APIs. *Access token:* presented to the resource server, **audience =
the API**, carries scopes — answers "what can the bearer do." *Refresh
token:* long-lived, used at `/token` to mint new access tokens; opaque;
stored server-side. Revocation: short access-token TTL plus a `/revoke`
endpoint for refresh tokens.

**Strong L6 answer.** All of the above, plus the trade-offs and the
numbers:

- **JWT vs opaque, per token, with the cost named.** *Access token = JWT*
  (self-validating: the resource server verifies the signature against a
  cached JWKS, **zero network hop per call** — essential because
  validation QPS dwarfs everything). The cost: **a JWT is valid until it
  expires; you cannot un-issue it.** You buy back revocability with a
  *short TTL* (5–15 min) so a compromised token self-expires fast, plus a
  small **denylist** checked on validation for emergency same-second kills.
  *Refresh token = opaque*, stored server-side, so it is **immediately
  revocable** by deletion — the right choice for the long-lived,
  high-value credential.
- **`kid` in the JWT header** points at the signing key in JWKS, so key
  rotation is seamless: publish the new key, sign with it, keep the old in
  JWKS until all old tokens expire, then drop it. Signing-key compromise →
  rotate `kid`, but blast radius is *every outstanding token* — so the
  short access-token TTL is what bounds the damage window.
- **Refresh-token rotation with reuse detection.** Every refresh redemption
  issues a *new* refresh token and invalidates the old one. If an old
  (already-rotated) refresh token is ever presented again, that's a
  reuse signal → the token was cloned → **revoke the entire token family**
  (all descendants of that refresh chain) and force re-auth. This turns a
  stolen refresh token from "silent persistent access" into "one use, then
  the whole session dies and the legitimate user notices."
- **Revocation at scale** ties to session epochs: a per-user monotonic
  epoch lets "log out everywhere" be O(1) — bump the epoch, reject any
  token/refresh carrying a lower epoch. The denylist stays small because
  most revocation is expressed as an epoch bump, not per-token entries.

**Anti-signal.** "Everything's a JWT, it's stateless" with no revocation
path, or "the API can accept the ID token." → Packet: *"Proposed JWT for
all tokens with no revocation story; a compromised token would be valid
until expiry with no kill switch; also conflated ID-token and access-token
audiences."*

**Packet quote (Hire).**
> *"Chose JWT access tokens (zero-hop validation at the dominant QPS) with
> short TTL + denylist, opaque refresh tokens (immediately revocable),
> refresh rotation with reuse-detection revoking the whole family, and
> `kid`-based key rotation. Named the validation-vs-revocation trade-off
> explicitly per token."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **Implicit-flow thinking.** Returning the token on the redirect to
  "save a hop." Deprecated by RFC 9700; leaks tokens to the front channel.
- **`state` as a server-side-only nonce.** Misses the cookie↔URL binding
  that actually defends login-CSRF, and misses the cross-flow binding role.
- **PKCE with no attack.** "It's a hash for extra security" — performing
  knowledge. Must walk code injection to the failing check.
- **Wildcard `redirect_uri`.** Open-redirect-to-code-exfiltration hole.
- **PII / claims on the front channel.** Identity must be redeemed
  server-to-server; nothing of value rides the browser URL/fragment.
- **Code store without single-use-under-race.** "Mark it used" with a
  read-then-write is a TOCTOU double-redeem bug; needs atomic GETDEL.
- **JWT-everything, no revocation.** Compromised token valid until expiry.
- **ID token used to call APIs** (or access token used to identify the
  user). Wrong audience; a real account-confusion class of bug.
- **No threat model.** This question *is* a threat-modeling exercise;
  designing only the happy path is the down-level signal.

### Interviewer-side (your own)

- **Letting them recite the five hops and stop.** The recital is table
  stakes. By minute 25, force an attack: *"Now I'm the attacker."*
- **Not driving to code injection.** It's the marquee scenario. If
  unprompted by minute 40, push — otherwise no signal lands in the packet.
- **Leading them to PKCE / `state` bindings.** Tempting because it's the
  right answer. If you hand it over, the packet can't claim it. Stay quiet.
- **Over-rewarding "we'd use OAuth library X."** Naming a product is not a
  signal. "Library X *because* it enforces PKCE and exact-match
  `redirect_uri` for us" is.
- **Eating the candidate's 3-min question window.** Still scoring on
  Googleyness during their questions.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it.
Numbers explicit, trade-offs committed.

### 6.1 Functional requirements (committed scope)

v1: **authorization-code grant with PKCE** (the only browser grant we
ship); the **OIDC layer** on top (ID token + UserInfo endpoint + `nonce`);
**refresh tokens** with rotation; **token revocation** (`/revoke` +
introspection); **client registration** with exact-match `redirect_uri`s;
a **consent** step (scopes the user approves).

**Out of scope v1, said out loud:** implicit flow and ROPC (deprecated by
RFC 9700 — do not ship), device-authorization grant (TV/CLI — separate
flow), dynamic client registration, token exchange / delegation, and
front-channel logout. Naming these as *deliberate cuts* is the signal.

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| Authorize QPS | **~20k QPS** peak | One per login attempt. Bursty (Monday mornings, app launches). |
| Token-redemption QPS | **~15k QPS** peak | One per successful login; slightly below authorize (abandons, errors). |
| Token-validation QPS | **~2M QPS** | Per *API call*, not per login — ~100× redemption. This ratio decides JWT-vs-opaque. |
| Authorization **code TTL** | **30–60s** | Long enough for the browser to bounce back + the client backend to redeem; short enough that a leaked code is near-useless. RFC 9700: as short as practical. |
| Code single-use | **enforced atomically** | One redemption, ever. GETDEL. |
| **Access token TTL** | **5–15 min** | Short, because JWTs can't be un-issued; bounds the compromise window. |
| **Refresh token TTL** | **30–90 days**, sliding, rotated each use | Long-lived but rotated + reuse-detected. |
| ID token TTL | **same as the login event** (~5–15 min); not refreshed | It attests an authentication, not a long session. |
| Token-validation p99 | **<5ms** server-side | Hot path of every API call; must be a local signature check. |
| Revocation propagation | **<10s** for "log out everywhere"; **<60s** for denylist fan-out | Epoch bump + denylist push. |
| Availability — authorize/token | **99.99%** | If login is down, every relying party is down. |

### 6.3 Capacity estimation (worked)

- **Code store size.** 20k authorize/s × 60s TTL = **~1.2M codes resident**
  at peak. Each entry ~300 B (opaque code key + `client_id`,
  `redirect_uri`, `code_challenge`, `user_sub`, `scope`, `nonce`, `exp`) →
  **~360 MB**. Trivially fits an in-memory store (Redis-shaped) with TTL
  eviction. The code store is **small, write-once, read-once, expire-fast**
  — a perfect TTL-cache workload, *not* a relational table.
- **Validation hop matters most.** At 2M validation QPS, any
  per-validation network call to the AS is a non-starter — a 1ms hop ×
  2M/s is 2M in-flight RPCs and makes the AS a hard dependency on every API
  call. **Therefore access tokens are self-validating JWTs**; resource
  servers verify against a cached JWKS, zero hop. *(This is the number that
  changed the design.)*
- **Refresh / token store.** Refresh tokens are opaque and stored: say
  500M active sessions × ~200 B = **~100 GB**, sharded by `user_sub`.
  Read on refresh (~low QPS) and on revocation.
- **JWKS / denylist.** JWKS is a handful of keys, cached everywhere with a
  short refresh. Denylist is small by design (epoch bumps express most
  revocation); even 1M emergency entries × 64 B = 64 MB, replicated to
  every validator.

**Numbers that changed a design choice:**
- 2M validation QPS ⇒ JWT access tokens (zero-hop validation), not opaque.
- 1.2M resident codes, 60s TTL ⇒ in-memory TTL store, not a DB table.
- Revocation expressed mostly as epoch bumps ⇒ denylist stays tiny.

### 6.4 API design

```
GET  /authorize
       ?response_type=code
       &client_id=...
       &redirect_uri=...            (exact-match against registration)
       &scope=openid profile email
       &state=<opaque, bound to a browser cookie>
       &code_challenge=<BASE64URL(SHA256(code_verifier))>
       &code_challenge_method=S256
       &nonce=<OIDC replay guard, echoed into the ID token>
   → 302 to redirect_uri?code=<opaque>&state=<echoed>&iss=<AS id>

POST /token                         (back channel, server-to-server)
       grant_type=authorization_code
       &code=<opaque single-use>
       &redirect_uri=...            (must match the /authorize value)
       &client_id=...  (+ client_secret for confidential clients)
       &code_verifier=<raw PKCE verifier>
   → 200 { access_token (JWT), id_token (JWT), refresh_token (opaque),
            token_type: Bearer, expires_in }

POST /token  grant_type=refresh_token  &refresh_token=...
   → 200 { new access_token, ROTATED refresh_token }   (old one invalidated)

GET  /userinfo        Authorization: Bearer <access_token>   → claims
POST /revoke          token=<refresh or access>              → 200
GET  /.well-known/jwks.json    → signing keys (kid-addressed)
GET  /.well-known/openid-configuration   → metadata, incl. code_challenge_methods_supported
```

### 6.5 Data model

- **Code store** (in-memory, TTL): key = opaque code (≥128-bit random),
  value = `{client_id, redirect_uri, code_challenge, code_challenge_method,
  user_sub, scope, nonce, auth_time, exp}`. TTL 60s. Single-use via atomic
  GETDEL.
- **Session / consent store**: `user_sub → {epoch, granted_scopes per
  client, auth_time, AAL}`. Drives consent skip + epoch revocation.
- **Refresh-token store** (durable, sharded by `user_sub`): `refresh_id →
  {user_sub, client_id, family_id, parent_id, scope, epoch, exp,
  rotated_at}`. The `family_id`/`parent_id` chain powers reuse detection.
- **Client registry**: `client_id → {type (public/confidential), secret
  hash, exact redirect_uris[], allowed scopes, PKCE-required flag}`.
- **JWKS**: active + retiring signing keys, `kid`-addressed.
- **Denylist** (replicated to validators): `{jti or (user_sub,epoch)}` with
  TTL = max token lifetime.

### 6.6 High-level architecture

```
        ┌────────────────────────── FRONT CHANNEL (browser, hostile) ──────────────────────────┐
        │                                                                                       │
   ┌────▼─────┐   1. 302 to /authorize (client_id, redirect_uri,        ┌──────────────────────┐
   │  User    │      state[+cookie], code_challenge, scope, nonce)      │  Authorization       │
   │  Agent   │ ───────────────────────────────────────────────────►   │  Server (AS)         │
   │ (browser)│                                                         │                      │
   │          │   2. authenticate user + consent screen                 │  /authorize          │
   │          │ ◄───────────────────────────────────────────────────   │  /token              │
   │          │   3. 302 back: redirect_uri?code&state&iss              │  /userinfo           │
   └────┬─────┘                                                         │  /revoke   JWKS      │
        │ 3'. browser delivers code + state to client callback          └───────┬──────────────┘
        │                                                                       │
   ┌────▼───────────────┐                                                       │
   │  Relying-Party     │   4. POST /token  code + code_verifier (+secret)      │
   │  (Client) BACKEND  │ ──────────── BACK CHANNEL (server-to-server TLS) ───► │
   │                    │ ◄──────────── access_token(JWT)+id_token+refresh ──── │
   └────┬───────────────┘                                                       │
        │ holds tokens server-side; sets its own session cookie                 │
        ▼                                                       ┌───────────────▼───────────────┐
   ┌────────────────┐   Bearer access_token (JWT)              │  Code Store (in-mem, 60s TTL,  │
   │ Resource Server│ ──── verify sig vs cached JWKS ────►      │  GETDEL single-use)            │
   │  (the API)     │      ZERO hop to AS per call             ├────────────────────────────────┤
   │  ~2M QPS       │      check denylist/epoch (local)        │  Refresh store (durable, sharded│
   └────────────────┘                                          │  by user_sub, family chain)    │
                                                               │  Session/consent store (epoch) │
   KEY: front channel carries only the opaque code + state.    │  Client registry · JWKS · denyl.│
        Tokens & all PII flow only on the back channel.        └────────────────────────────────┘
```

### 6.7 The authorization-code round trip (the protocol core)

1. **Client → browser → `/authorize`** (front channel). Client generates a
   `code_verifier`, derives `code_challenge = S256(verifier)`, a random
   `state` (also stored in a client cookie), and a `nonce`. Redirects the
   browser with all the front-channel params. **No secret, no token, no PII
   here.**
2. **AS authenticates the user + consent** (skipped if already granted for
   this client/scope).
3. **AS → browser → client callback** (front channel): `redirect_uri?code=
   <opaque>&state=<echo>&iss=<AS>`. The code is opaque, high-entropy,
   single-use, 60s TTL, and bound to `code_challenge` + `user_sub` +
   `client_id` + `redirect_uri` in the code store.
4. **Client backend → `/token`** (back channel, server-to-server): sends
   `code`, `redirect_uri` (must match step 1), `client_id` (+secret for
   confidential), and the raw `code_verifier`. AS: GETDEL the code
   (atomic single-use), verify `S256(code_verifier) == stored
   code_challenge`, verify `redirect_uri`/`client_id` match → mint tokens.
5. **AS → client backend**: access token (JWT), ID token (JWT, with
   `nonce` echoed), refresh token (opaque). The client sets *its own*
   session cookie; the user's identity was learned **server-to-server**,
   never via the browser URL.

### 6.8 `state` (double duty) + PKCE + redirect_uri — the security spine

See deep dive B for the full attack walks. The committed mechanisms:

- **`state` = login-CSRF defense (cookie↔URL binding) AND cross-flow
  binding.** Stored in a browser cookie *and* echoed in the URL; callback
  requires both to match. No matching cookie ⇒ this browser didn't start
  this flow ⇒ reject. Blocks login-CSRF and forged-callback injection.
- **PKCE** (`S256`, mandatory for public clients, recommended for all):
  binds the code to the verifier of the flow that requested it. An injected
  or stolen code can't be redeemed without the matching verifier. Defense
  in depth behind `state`.
- **`nonce`** (OIDC): random, sent at `/authorize`, echoed into the ID
  token; the client checks it matches → ID-token replay guard.
- **Exact-match `redirect_uri`** + **`return_to` allowlisting**: never
  prefix/wildcard; hosts pinned to a known namespace, never taken from the
  request payload. Closes the open-redirect → code-exfiltration chain.
- **`iss` in the authorization response** (RFC 9700): defends the *mix-up*
  attack — the client confirms the response came from the AS it sent the
  user to, not an attacker-controlled AS.

### 6.9 Code store — single-use under concurrency

The replay guard is **atomic single-use redemption**. The store is an
in-memory KV with TTL. Redemption is **GETDEL** (get-and-delete in one
atomic op): the first `/token` call that touches a code gets the value
*and* removes it in the same operation; any concurrent or replayed
redemption sees nothing and is rejected. This defeats the double-redeem
race a naive read-check-then-mark-used would leave open (TOCTOU). Combined
with the 60s TTL, a leaked code is single-use *and* short-lived *and*
useless without the PKCE verifier — three independent guards.

### 6.10 Token design, refresh, revocation

- **Access token = JWT**, audience = resource server, short TTL (5–15 min),
  verified locally against cached JWKS (zero hop at 2M QPS). `kid` header
  for seamless key rotation.
- **ID token = JWT**, audience = the client, carries identity + `nonce` +
  `auth_time`; used for login only, never to call APIs.
- **Refresh token = opaque**, durable, immediately revocable by deletion;
  **rotated on every use** with **reuse detection** — replay of a rotated
  token revokes the whole family and forces re-auth.
- **Revocation at scale = epoch bump.** Per-user monotonic epoch in the
  session store; tokens carry the epoch at issue; validators reject any
  lower epoch (O(1) "log out everywhere"). A small replicated denylist
  handles same-second emergency single-token kills. Most revocation is an
  epoch bump, so the denylist stays tiny.

### 6.11 Multi-region / consistency commitments

CAP commits, said out loud:

- **Token validation: AP, fully local.** JWKS + denylist + epoch are
  replicated read-mostly state; validators never make a synchronous
  cross-region call. A few-second replication lag on the denylist is
  acceptable because the short access-token TTL is the real bound on a
  compromised token.
- **Code store: regionally affined, CP within region.** A code is created
  and redeemed within seconds; pin both the `/authorize` and `/token` legs
  to the same region (sticky by `client_id` or edge routing). No need for
  global replication of a 60s artifact — cross-region code replication
  would add latency and a replay surface for zero benefit.
- **Refresh / session store: CP on the write path** (sharded by `user_sub`,
  consensus-replicated). Refresh redemption and revocation must be
  linearizable per user, or reuse detection has races. Low QPS, so the
  cost is affordable.
- **Authorize/consent: regional, eventually consistent consent state.** A
  newly granted consent propagating in a few seconds is fine.

### 6.12 Cost (back-of-envelope, monthly)

| Component | Notes | $/mo |
|---|---|---|
| AS compute (authorize + token) | ~35k combined QPS, signing-heavy | ~$40k |
| Code store (in-mem, ~400 MB + headroom, multi-region) | tiny footprint, TTL-evicted | <$5k |
| Refresh/session store (sharded, ~100 GB, consensus) | low QPS, durability matters | ~$25k |
| JWKS/denylist distribution | replicated to all validators | <$5k |
| Token validation | **borne by the resource servers, not the AS** | ~$0 to AS |
| **Total (AS side)** | | **~$75k/mo** |

The dominator-avoidance story is the point: pushing validation to JWT
verification at the resource servers keeps the **2M-QPS** load *off* the
authorization server entirely. An opaque-token design with introspection
would put 2M QPS of introspection calls on the AS — easily **10×+** the
cost and a hard availability coupling. The JWT choice is a cost decision as
much as a latency one.

### 6.13 Failure modes & blast radius

| Failure | Blast radius / behavior | Mitigation |
|---|---|---|
| Authorization Server down | No new logins anywhere; existing sessions keep working (JWTs validate locally) | Multi-region active-active; JWT design means API traffic is unaffected |
| Code store region loss | In-flight logins in that region fail (re-login fixes it); 60s of codes lost | Regional affinity; codes are cheap to recreate by re-auth |
| Signing key compromised | **Every outstanding access/ID token is forgeable** — the worst case | Rotate `kid` immediately; short access TTL bounds the window; force refresh-token re-issue; old key dropped from JWKS after max TTL |
| One authorization code leaked | One session, one user — and useless without the PKCE verifier + single-use | Opaque + GETDEL + 60s TTL + PKCE |
| Refresh token stolen | Persistent access **until first reuse** | Rotation + reuse detection → revoke family on replay |
| Denylist propagation lag | A revoked token may validate for up to the lag (~seconds) | Short access TTL is the backstop; epoch checks are local |
| Client open-redirect | Code exfiltration **if** wildcard `redirect_uri` allowed | Exact-match registration forbids it structurally |

**SLO/error budget.** Authorize/token 99.99% → 4.32 min/mo. Validation is a
separate SLO owned by resource servers (it depends only on JWKS freshness,
not the AS hot path).

### 6.14 Evolution at 10×

10× relying-party apps (many low-trust) and 10× QPS:

- **Validation:** unchanged in shape — JWT verification scales with the
  resource servers, not the AS. The seam that *doesn't* move.
- **Code store:** scale memory linearly; still regional, still 60s TTL.
- **Low-trust clients:** enforce **PKCE-required** and exact-match
  `redirect_uri` per client at registration; tighten consent; rate-limit
  per `client_id`. The registry is the control point.
- **Revocation fan-out:** if the denylist grows, lean harder on epochs and
  shorten access TTL rather than growing the list.
- **Key management:** more frequent `kid` rotation; the JWKS mechanism
  already supports it — no redesign.
- **Org seams:** the **client registry / consent** plane is a natural team
  handoff (an identity-platform team owns clients, scopes, consent); the
  **token/crypto** plane (signing, JWKS, rotation) is a second; the
  **resource-server SDK** that does local validation is a third. I'd own
  the token/crypto and the code-flow protocol personally; delegate the
  registry UX and the per-language validation SDKs.

**What does not change:** the protocol (code grant + PKCE + OIDC), the
front/back-channel split, the token shapes. The seams I named at v1 — the
client registry, the denylist-vs-epoch revocation knobs, regional code
affinity — are the seams at 10×.

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence. Right is the call.

| Evidence | Call |
|---|---|
| Proposed implicit flow / token-in-redirect "to save a hop"; no threat model after two prompts. | **Strong No Hire** |
| Walked authorize→code→token but couldn't say why the code exists; described `state` and PKCE as generic "security," couldn't tie either to an attack. | **No Hire** |
| Five hops correct; `state` = "CSRF nonce checked server-side" only (missed cookie binding); PKCE named without an attack; allowed wildcard `redirect_uri`. | **Lean No Hire** |
| Clean end-to-end flow; front/back-channel split named; `state` and PKCE each tied to *one* attack with a roughly-correct check; short single-use code; ID-vs-access audience right; exact-match `redirect_uri`. Did not surface the cookie↔URL binding or the double-redeem race even when prompted. | **Hire L5** |
| All of the above, **unprompted**, plus: front-channel/back-channel framed as the reason the code grant exists; PII-free browser hop stated as a rule; atomic GETDEL single-use with the TOCTOU race named; JWT access + opaque refresh with the revocation cost named; gave authorize/redeem/validate QPS split. | **Hire L5 / Lean L6** |
| All of L5-Hire-plus, **plus**: named `state`'s **double duty** (cookie↔URL login-CSRF defense AND cross-flow binding) unprompted; walked the cross-tenant code-injection attack to the exact failing check, with PKCE as defense-in-depth; `return_to`/`redirect_uri` allowlisting as open-redirect defense; refresh rotation with reuse-detection revoking the family; `kid` key rotation with "every token" blast radius; 2M-validation-QPS number drove the JWT choice; epoch-bump revocation. Narrated the budget. | **Hire L6** |
| Everything in L6, **plus**: stated CAP commitments per store (AP local validation, CP refresh/session, regional code affinity) with the latency/replay reasoning; surfaced the cost dominator (validation off the AS = 10×+ saving vs introspection); named what they'd delegate vs own (token/crypto + protocol owned; registry UX + validation SDKs delegated); defended a choice against pushback quantitatively; closed with a self-aware retro (e.g. mix-up `iss`, consent-screen phishing). | **Strong Hire L6** |

---

## Sources

- **RFC 6749 — The OAuth 2.0 Authorization Framework** (the base
  protocol, authorization-code grant): https://datatracker.ietf.org/doc/html/rfc6749
- **RFC 7636 — Proof Key for Code Exchange (PKCE)**:
  https://datatracker.ietf.org/doc/html/rfc7636 · overview: https://oauth.net/2/pkce/
- **RFC 9700 — Best Current Practice for OAuth 2.0 Security** (Jan 2025;
  PKCE mandatory for public clients, exact-match `redirect_uri`, `iss` in
  response, implicit/ROPC deprecation): https://datatracker.ietf.org/doc/rfc9700/
  · readable summary: https://workos.com/blog/oauth-best-practices
- **OpenID Connect Core** — ID token, `nonce`, UserInfo:
  https://openid.net/specs/openid-connect-core-1_0.html
- **ID Tokens vs Access Tokens** (audience and purpose):
  https://oauth.net/id-tokens-vs-access-tokens/ ·
  https://auth0.com/blog/id-token-access-token-what-is-the-difference/
- **OAuth security best practices — PKCE & state**:
  https://www.authgear.com/post/oauth2-security-best-practices-pkce-state/
- **Defending OAuth: common attacks (open redirect, code exfiltration,
  mix-up)** — WorkOS: https://workos.com/blog/oauth-common-attacks-and-how-to-prevent-them
- **Redirect URI validation / exact match** — oauth.com:
  https://www.oauth.com/oauth2-servers/redirect-uris/redirect-uri-validation/
- **Opaque vs JWT access tokens; refresh-token rotation & reuse
  detection** — Ory: https://www.ory.com/docs/oauth2-oidc/jwt-access-token ·
  Okta refresh-token rotation: https://developer.okta.com/docs/guides/refresh-tokens/main/

---

*End of guide. Related:* `06-sso-auth-service.md` *(the federated-identity
platform this protocol plugs into) and* `10-session-management.md` *(the
session/epoch revocation machinery referenced in §6.10).*
