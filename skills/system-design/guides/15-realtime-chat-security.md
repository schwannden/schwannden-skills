# Question 15: Securing a Real-Time Chat / Messaging System (transport security, key exchange, and end-to-end encryption at scale, e.g. Signal / WhatsApp)

> Interviewer's guide + golden answer for the 1-hour Google L5/L6
> system-design round. The anchor problem for the **layered security /
> key exchange / end-to-end encryption on a real-time messaging
> platform** archetype. This is the security pivot on guide 13
> (`13-realtime-chat.md`): the candidate already knows how to scale chat
> — 100M concurrent connections, ~1M msg/sec, fan-out that flips by
> conversation size. *Assume all of that.* This round tests something
> guide 13 deliberately put out of scope: **which cryptographic
> primitive belongs at which layer and why.** Frame it around Signal /
> WhatsApp E2EE. Voice: L7 Senior Staff who has run hundreds of these and
> has internal calibration on what good looks like. The calibration value
> is *not* whether the candidate can say "we use SSL." It's whether they
> can hold the central tension for an hour: **transport security (TLS/WSS)
> protects the bytes to the server, but the server still holds plaintext
> and can read, route, search, and moderate it. End-to-end encryption
> removes the server's ability to read content entirely — which is the
> goal — but breaks every server-side feature that assumed plaintext
> (fan-out logic, server-side search, multi-device sync, push
> notification content, spam detection, backup) and makes group
> messaging and key distribution genuinely hard.** The candidate must
> layer the defenses in the right order, commit to the Signal-style
> design, and defend what E2EE *costs*.

---

## 1. Why this question (interviewer's framing)

A chat-security question *looks* like "add TLS and call it encrypted."
The modal L4 says "we'll use SSL between the client and the server, and
HTTPS for the API," draws a padlock, and stops. That answer is not wrong
— it is *incomplete in exactly the place the question is asking about*,
and it blurs three distinct things into one word. The hard part of
securing chat is that **TLS secures the hop to the server, but the server
still sees every plaintext message** — it can read it, log it, hand it to
a subpoena, or have it stolen in a breach. The product requirement Signal
and WhatsApp commit to is stronger: **the server provably cannot read the
message, and never had the ability to.** Getting there means understanding
key exchange vs. encryption vs. authentication as *separate* things, and
then accepting that end-to-end encryption breaks half the server-side
features you built in guide 13.

Five things this tests that little else in the canon tests as cleanly:

1. **Which primitive lives at which layer.** TCP gives you a connection
   and *no* security. TLS 1.3 gives you a key *agreement* (ephemeral
   Diffie-Hellman), server *authentication* (the certificate), and bulk
   *encryption* (symmetric AEAD) — three different jobs, often conflated.
   WebSocket-over-TLS is **WSS**, not "SSL." The candidate who can't
   separate **key exchange (asymmetric ECDHE) from bulk encryption
   (symmetric AES-GCM/ChaCha20) from authentication (the cert/signature)**
   is telling you they've memorized "use SSL" without understanding it.
2. **Transport security is necessary but not sufficient.** The
   load-bearing realization: even perfect TLS leaves the *server* holding
   plaintext. If the threat model includes the server operator, a breach,
   or a legal compel, transport security does nothing. That gap is the
   entire motivation for end-to-end encryption — and a candidate who never
   names it has missed why the question exists.
3. **E2EE where the gateway can't decrypt — and never could.** The Signal
   Protocol: **X3DH** for asynchronous initial key agreement (Bob can be
   offline), **Double Ratchet** for per-message keys, a **key server that
   only ever stores public material.** The invariant the candidate must
   state: *no server component holds a private key capable of decryption.*
   The server is an **untrusted relay** of ciphertext plus the cleartext
   routing metadata it needs to deliver.
4. **Two security properties most candidates conflate.** **Forward
   secrecy** (compromising a key today does not expose *past* messages)
   and **post-compromise security / self-healing** (compromising a key
   today does not expose *future* messages once the ratchet turns) are
   *distinct*. The L6 names them separately and ties each to a mechanism
   (ephemeral DH / the symmetric ratchet for FS; the DH ratchet for PCS).
   Conflating them is a clean L5/L6 separator.
5. **What E2EE breaks, and the system-design cost.** This is the meat.
   Fan-out *survives* (the server routes opaque blobs by cleartext
   metadata). But server-side search dies (moves client-side), push
   notification content dies (encrypted payload or contentless wakeup),
   content moderation dies (moves to client reporting + sender attribution
   + metadata signals), and backup becomes a user-key-held encrypted blob.
   Group messaging gets genuinely hard (Sender Keys vs. MLS). The L6
   volunteers the breakage *and* the mitigations, with a group-size
   threshold where the strategy flips.

### What "Hire" looks like at each level

**L5 Hire.** Separates the three layers cleanly and unprompted: TLS to the
server (transport), E2EE between clients (content). Distinguishes **key
exchange from bulk encryption from authentication** when walking the TLS
handshake — names ECDHE for the key agreement, AES-GCM/ChaCha20 for the
bulk, the certificate for authentication. Knows **SSL is deprecated, TLS
1.3 is the real thing**, and that WebSocket-over-TLS is WSS. Commits to
the Signal-style design: a **key server storing only public keys**, X3DH
for initial agreement, a symmetric AEAD for the message itself. States the
invariant that **the server can't read messages**. Names at least two
features E2EE breaks (push content, search) and a mitigation for each.
Handles "key server is compromised" with *verification* as the backstop
when prompted.

**L6 Hire.** All of the above, **plus**: *drives the room* (narrates the
budget, pre-ranks the deep dives off the threat model). Names **perfect
forward secrecy from *ephemeral* DH** — a compromised long-term key
doesn't decrypt past sessions — *and* separately names **post-compromise
security / self-healing** from the **Double Ratchet's DH ratchet**, and is
explicit that these are two different properties. States the invariant
**"no server component holds a private key capable of decryption, and
verification is the trust anchor that makes an untrusted server safe"**
before being asked. Volunteers **multi-device as one cryptographic
identity per device** (sender-side fan-out to a signed device list) and
the **Sender Keys → MLS flip** for groups with a committed size threshold.
Walks **what E2EE breaks** (search, push content, moderation, backup,
sealed-sender metadata) with mitigations, unprompted. States **CAP
commitments on the key server** (prekey-pool AP, device-list closer to
CP). Names **prekey exhaustion → signed-prekey fallback** and the FS
trade. Surfaces $/month and the dominator (crypto pushed to clients;
ciphertext fan-out = recipients × devices). Names own-vs-delegate.

### Classic downlevel traps

1. **"We'll use SSL, done."** The modal L4 answer. It (a) uses deprecated
   terminology (SSL, not TLS), (b) conflates key exchange, encryption, and
   authentication into one word, and (c) stops at transport security
   without noticing the server still holds plaintext. When pushed —
   "great, now the server is subpoenaed / breached; what reads the
   messages?" — they have no answer. Packet: *"Stopped at transport TLS;
   conflated the crypto primitives; did not see that the server still holds
   plaintext, and had no end-to-end story even when prompted."*
2. **E2EE with the key on the server.** "We encrypt messages with a key
   the server manages / a KMS." If the server can fetch the decryption
   key, it's not end-to-end — it's encryption-at-rest with extra steps.
   The invariant *no server component holds a decryption-capable private
   key* is missing. One sentence and the packet writes itself.
3. **Conflating forward secrecy with post-compromise security.** "We have
   forward secrecy because we rotate keys." Rotation alone gives you one or
   the other depending on direction; the candidate who can't say which
   property protects *past* vs. *future* messages, and which mechanism
   provides each, is at the L5 ceiling on the crypto axis.
4. **"E2EE just works, nothing changes."** Ignoring that E2EE *breaks*
   server-side search, push-notification content, server-side moderation,
   and server-side backup. A candidate who claims you flip on E2EE and
   keep all of guide 13's features hasn't thought it through. The system-
   design signal is naming the breakage *and* the mitigation.
5. **Pairwise fan-out for a 5,000-member group.** Encrypting the message
   separately to every member (O(n) per message, O(n²) on a key change)
   for a large group is the group-crypto cliff. The Sender Keys → MLS flip
   is the lesson; not knowing a group-scaling answer caps the level.
6. **Trusting the key server blindly.** "We get Bob's public key from the
   server, so we're safe." A malicious key server can hand Alice *its own*
   key (active MITM). Without **out-of-band verification (safety numbers /
   QR)** the untrusted server can read everything. Missing verification as
   the trust anchor is missing the whole point of E2EE.

---

## 2. The 60-minute plan

Minute-by-minute against the canonical budget. For each slice: **Say**
(verbatim lines), **Listen for** (the signal), **Push back when** (trigger
+ line). Two deep dives are **mandatory** (A and B); the third (C) is
forced if not volunteered.

### 0–5 min — Intro & framing

**Say:** *"I'm <name>, L7 on an unrelated infra team. 60-second bios,
then: assume we've built a real-time chat system at WhatsApp scale —
100M live connections, ~1M messages/sec, fan-out that flips by group
size. That part is solved. Today I want you to **secure** it: design the
transport security, the key exchange, and end-to-end encryption such that
the server provably cannot read messages. Think Signal / WhatsApp. Drive
it however you like; I'll interject."*

**Listen for:** do they restate and name the layering ("so there's
transport security to the server, and *separately* end-to-end encryption
between clients — and the hard part is the server can't be trusted with
plaintext"), or do they immediately say "SSL"? Restating + naming the
transport-vs-E2E split is the L6 tell.
**Push back when:** they say "we'll just use SSL/TLS and we're done." →
*"TLS secures the bytes to the server. The server still decrypts and reads
every message. Is that acceptable for your threat model? If not, what
else?"* Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** almost nothing. If asked "what's the threat model?" → *"The
network is hostile (assume MITM attempts), and — critically — **the server
operator is in the threat model**: a breach, a rogue insider, or a legal
compel must not yield readable messages. You tell me what that forces."*
If asked "groups in scope?" → *"Yes — 1:1, small groups, and a large
group of a few thousand. And multi-device: one user, several devices."*
If asked "metadata?" → *"Bonus if you protect it; tell me how far you can
go."*

**Listen for:**
- Tight functional commit: TLS/WSS transport; an **untrusted key server**
  distributing public key material; **X3DH-style asynchronous initial key
  agreement** (recipient may be offline); **per-message keys** with
  forward secrecy *and* post-compromise security; **multi-device**
  (per-device identity); **group E2EE**; **trust establishment**
  (TOFU + safety-number verification); the explicit invariant **the server
  can't decrypt**.
- The breakage list named aloud: push-notification content, server-side
  search, moderation, backup — and a mitigation for each.
- NFRs **with numbers**: TLS handshake RTT, prekey bundle size, one-time-
  prekey pool depth + replenishment, key-server QPS, per-device key-state
  size, double-ratchet state per conversation, group-size flip point,
  ciphertext fan-out multiplier (recipients × devices).

**Push back when:**
- "We use SSL." → *"SSL or TLS? They're not the same word in 2026. And
  which part — the key exchange, the bulk encryption, or the
  authentication — are you describing?"*
- "The server encrypts the messages." → *"If the server holds the key, the
  server can read them. That's not end-to-end. Where does the decryption
  key live such that the server provably can't?"*
- "E2EE, and everything else works the same." → *"You just made the
  message opaque to the server. How does push-notification content work?
  Server-side search? Spam scanning? Pick one and walk me through it."*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip the math, *"Before we draw — what's
the key-server read QPS, given every new conversation fetches a prekey
bundle? And what's your ciphertext fan-out multiplier with multi-device?"*

**Listen for:**
- Worked numbers: key-server reads ≈ new-conversation rate (read-heavy,
  every session start fetches a bundle); one-time-prekey pool depth (e.g.
  ~100/device) and replenishment trigger; prekey bundle size (a few
  hundred bytes); per-device double-ratchet state (~hundreds of bytes to a
  few KB per conversation); **ciphertext fan-out = recipients × devices**.
- **The numbers that decide the architecture:** (1) the key server is a
  *read-heavy, public-material-only* store → it can be AP and cheap, and
  its compromise is bounded by verification; (2) ciphertext fan-out =
  recipients × devices → multi-device multiplies the message copies, and
  this is the cost line that changed from guide 13; (3) prekey-pool depth ×
  replenishment rate → the AP availability target for "Alice can always
  start a conversation."
- The right box diagram: client ⇄ **TLS/WSS gateway** (transport layer) ⇄
  relay; a **separate untrusted key server** (public keys only); the
  **message relay** carries opaque ciphertext + cleartext routing
  metadata; **crypto happens on the clients**, not the server.

**Push back when:**
- 10 boxes with the crypto on a server → *"Which box holds a private key?
  If any server box can decrypt, you don't have E2EE. Show me the box that
  *can't*."*
- "The key server hands out keys, so it's trusted." → *"It stores only
  *public* keys. What stops it from handing Alice *its own* public key and
  MITM-ing the conversation?"* (forces verification.)
- Reflexive "put TLS termination at the edge and we're encrypted" →
  *"For an E2EE app, does it matter where TLS terminates? Reason about the
  two layers independently."*

### 25–45 min — Deep dives (the diagnostic zone)

Two **mandatory** dives:

1. **Layered transport security + the key exchanges.** Ask: *"Walk me
   through bringing up a secure connection from a cold client, in order,
   and name which security step happens at which layer — TCP, TLS, the
   WebSocket upgrade. Then tell me exactly which part is key exchange,
   which is encryption, and which is authentication."* This is where
   ECDHE-vs-AEAD-vs-certificate, PFS-from-ephemeral-DH, WSS-not-SSL, and
   "TLS secures the hop but the server still holds plaintext" must appear.
2. **End-to-end encryption — the gateway can't decrypt.** Ask: *"Now make
   it so the server provably cannot read a message, even though it routes
   it, and Bob is offline when Alice sends the first one. Walk me through
   the key agreement and the per-message keys. What does the server store?
   What stops a malicious key server from reading everything?"* This is
   where X3DH (public-only key server, offline first message), the Double
   Ratchet (FS *and* PCS, named separately), the untrusted-relay invariant,
   and out-of-band verification must surface. If the FS-vs-PCS distinction
   doesn't appear, that's a finding.

Third dive — force if not volunteered — **scalable E2EE: multi-device,
groups, and what E2EE breaks** (*"a 5,000-member group; someone posts;
and separately, how does a push notification show message text if the
server can't read it?"*): almost always worth forcing.

**Listen for at L6:** TCP=no-security → TLS-1.3-1-RTT (ECDHE + cert +
AEAD) → WSS; PFS from ephemeral DH; 0-RTT replay caveat; cert pinning +
mTLS internal; X3DH public-only key server + offline first message;
Double Ratchet symmetric ratchet (FS) + DH ratchet (PCS) named
separately; untrusted-relay invariant; TOFU + safety-number verification;
per-device identity + signed device list; Sender Keys → MLS flip with a
threshold; the breakage list with mitigations; sealed sender.

**Push back hard** on "SSL" (*"deprecated; which of the three jobs?"*),
on "server-managed key" (*"then the server can read it"*), on "forward
secrecy because we rotate" (*"which property protects past messages vs.
future, and which mechanism gives each?"*), on "trust the key server"
(*"malicious key server hands Alice its own key — what stops the MITM?"*),
on "pairwise encrypt to 5,000 members" (*"how many encryptions per
message, and per key change?"*).

### 45–55 min — Evolution / curveball

Pick **one** (mandatory if not already covered):
- *"Your one-time-prekey pool for a popular user is exhausted and they're
  offline. Alice wants to message them now. What happens, and what did you
  just give up?"* (signed-prekey fallback + the FS-of-first-message trade.)
- *"A user links a new device — a new laptop. Walk me through the trust
  problem and how existing contacts learn about the new device key without
  the server being able to inject a rogue one."* (multi-device trust /
  malicious-device-addition.)
- *"The key server has a regional outage for 10 minutes. What still works,
  what doesn't, and does it drop established encrypted sessions?"*
  (control-plane/data-plane split: established Double-Ratchet sessions keep
  going; only *new* conversation setup degrades.)
- *"10× — 1B users, a billion device keys. What breaks first on the
  security side?"* (key-server read QPS + ciphertext fan-out, not crypto
  compute, which is on the clients.)

**Listen for:** seam identification, not redesign. L6 names the 2–3 knobs
(prekey-pool depth, device-list consistency, Sender-Keys→MLS threshold)
and the trade each makes; L5 tends to restart.

### 55–60 min — Wrap

**Say:** *"That's time. What would you do differently with 15 more
minutes? Then — questions for me?"*

**Still scoring:** self-aware retro ("I didn't get to sealed-sender
metadata protection or the encrypted-backup key-recovery flow") and what
they ask. A great closing question I've heard: *"When a safety-number
changes mid-conversation, who owns the UX decision between hard-blocking
the send and warning-and-continue — and how do you keep that from training
users to click through warnings?"* That's someone who's reasoned about the
human end of the trust anchor.

---

## 3. Probing prompts (the kit)

Pre-loaded, with the signal each hunts. Drop verbatim; use silence after.

| # | Prompt | Signal hunted |
|---|---|---|
| 1 | "Walk the connection bring-up in order: TCP, then what, then what — and where does security first appear?" | TCP = no security; TLS does the work; WebSocket-over-TLS = WSS. Layer ordering. |
| 2 | "In the TLS handshake, which part is key exchange, which is encryption, which is authentication?" | ECDHE (key agreement) vs AES-GCM/ChaCha20 (bulk AEAD) vs certificate (authentication). Most candidates blur these. |
| 3 | "SSL or TLS — and does it matter?" | SSL is deprecated; TLS 1.3 is the real thing; "SSL handshake" is loose. |
| 4 | "Where does perfect forward secrecy come from?" | *Ephemeral* DH — a leaked long-term key can't decrypt past sessions. |
| 5 | "TLS terminates at the edge LB. Are the messages now safe?" | Necessary-but-not-sufficient: the server still holds plaintext. Motivates E2EE. |
| 6 | "Make it so the server provably can't read a message. What changes?" | E2EE; the decryption key never reaches any server box. |
| 7 | "Bob is offline. How does Alice send him an encrypted first message?" | X3DH: server distributes Bob's *public* prekey bundle; async agreement. |
| 8 | "What exactly does the key server store, and what can it decrypt?" | Public keys only; *nothing* it can decrypt with. The invariant. |
| 9 | "Forward secrecy and post-compromise security — same thing?" | Two distinct properties (past vs future); two mechanisms (symmetric ratchet / DH ratchet). The L5/L6 separator. |
| 10 | "A malicious key server hands Alice its own public key. What stops the MITM?" | Out-of-band verification (safety numbers / QR); TOFU + key-change warnings. |
| 11 | "One user, three devices. How is the message encrypted?" | Per-device cryptographic identity; sender-side fan-out to a signed device list. |
| 12 | "5,000-member group, one post. How many encryptions, and what on a key change?" | Pairwise = O(n)/msg, O(n²)/change; Sender Keys (O(1)/msg) → MLS (O(log n)/change). |
| 13 | "At what group size do you flip from Sender Keys to MLS, and why?" | A committed threshold (~hundreds to low-thousands) + the key-update-cost reasoning. |
| 14 | "Push notification needs to show 'Mom: dinner?' but the server can't read it. How?" | Encrypted push payload decrypted client-side, or a contentless wakeup. |
| 15 | "Server-side search is gone. Where does search live now?" | Client-side index; the server can't see content. |
| 16 | "No server can scan content. How do you fight spam/abuse?" | Client reporting + sender attribution + metadata signals + rate limits; not content scanning. |
| 17 | "Backups — the server can't hold readable history. How?" | Encrypted backup with a user-held key (or HSM-backed PIN recovery). |
| 18 | "One-time prekeys exhausted, user offline. Alice messages now. What gives?" | Fall back to the signed prekey; weaker FS for the first message — name the trade. |
| 19 | "Does the server learn who messaged whom?" | Sealed sender / metadata minimization; how far you can push it. |
| 20 | "Ciphertext fan-out multiplier and cost dominator?" | recipients × devices; crypto is cheap (on clients), copies multiply. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

Pick **2–3**. For each: phrasing, L5 vs L6 shape, anti-signal, packet
quote. A and B are the mandatory pair; C if there's time or weakness.

### Deep dive A — Layered transport security and the key exchanges

**Phrasing.** *"Walk me through bringing up a secure connection from a
cold client, in order — TCP, then the security layer, then the WebSocket.
Name which step is at which layer. Then be precise: which part is key
exchange, which is bulk encryption, which is authentication — and where
does perfect forward secrecy come from?"*

**Strong L5 answer.** "Three steps in order. (1) **TCP 3-way handshake** —
SYN / SYN-ACK / ACK. That's *just a connection*; there's no security yet.
(2) **TLS 1.3 handshake** on top of that TCP connection: the client and
server do an **ephemeral Diffie-Hellman key agreement (ECDHE)** to derive
a shared symmetric secret, the server presents its **X.509 certificate**
which the client validates against a CA chain (that's the
*authentication* — it proves we're talking to the real server, not a
MITM), and from then on bulk application data is encrypted with a
**symmetric AEAD cipher like AES-GCM or ChaCha20-Poly1305**. TLS 1.3 does
this in **1 round trip**. (3) Then we send an HTTP **WebSocket upgrade
request over that TLS connection** — `Upgrade: websocket` — and because
it's over TLS, the scheme is **wss://**, *WSS*, not plain ws. So three
distinct jobs: ECDHE is the **key exchange**, AES-GCM is the **bulk
encryption**, and the certificate is the **authentication**. They're not
the same thing — 'SSL' as a catch-all blurs them, and SSL itself is
deprecated; TLS 1.3 is what we actually run." Correct, competent, names
the three jobs and WSS. What's missing is PFS-from-ephemeral stated
explicitly, the 0-RTT replay caveat, pinning/mTLS, and the load-bearing
"server still holds plaintext."

**Strong L6 answer.** "Same three steps, but five things I want to be
precise about, because they're where this earns its keep.

*The three jobs are genuinely separate, and most people conflate them.*
**Key exchange** = ECDHE: an *ephemeral* Diffie-Hellman where each side
generates a fresh DH keypair *per session* and they agree on a shared
secret without ever transmitting it. **Bulk encryption** = a symmetric
AEAD (AES-256-GCM or ChaCha20-Poly1305) keyed by that shared secret —
symmetric because it's orders of magnitude faster than asymmetric for the
data stream. **Authentication** = the server's certificate (a CA's
signature binding the public key to the hostname), plus the Finished MAC.
Three jobs, three primitives.

*PFS comes specifically from the* ephemeral *in ECDHE.* Because the DH
keypair is fresh per session and discarded after, **compromising the
server's long-term private key tomorrow does not let an attacker decrypt
the traffic they recorded today** — there's no long-term key that unlocks
past sessions. That's perfect forward secrecy, and it's a property of
*ephemeral* DH, not of TLS generically. TLS 1.3 removed the old static-RSA
key-exchange modes precisely to make PFS mandatory.

*0-RTT is a latency win with a replay caveat I'll commit on.* TLS 1.3
session resumption can send application data in **0-RTT** using a
pre-shared key from a prior session — saves the round trip on reconnect,
which matters at 100M reconnecting clients. But 0-RTT data is
**replayable** (an attacker can resend the captured early-data), so I only
allow 0-RTT for **idempotent, non-state-changing** requests; the first
real `SEND` waits for the 1-RTT handshake to complete. Resumption tickets
get a short lifetime (e.g. hours, not days) so a stolen ticket's window is
bounded.

*Defense in depth: certificate pinning and mTLS.* The CA model has a
weakness — *any* trusted CA can issue a cert for my domain, so a
compromised or coerced CA enables MITM. I **pin** the expected
certificate/public key in the client app to shut that down, and I lean on
**Certificate Transparency** logs to detect misissuance. For
**service-to-service inside** the fleet (gateway ↔ relay ↔ key server) I
use **mTLS** — both sides present certs — so the registration/auth
handshake between internal services is itself a security boundary, not an
open internal network. This is the same shape as SIP-registration-over-TLS:
the registration handshake is where you authenticate the peer.

*The load-bearing point — and the bridge to deep dive B.* All of this
secures the **hop to the server**. The TLS connection terminates *at the
server*, which means **the server decrypts and holds the plaintext
message.** It can read it, log it, route on it, hand it to a subpoena, or
leak it in a breach. So where TLS terminates — edge LB vs. passthrough to
the gateway — is an *operational* decision (it doesn't change the
guarantee, because for an E2EE app the application payload is encrypted
*regardless*). Transport security is **necessary but not sufficient**: if
the threat model includes the server operator, you need a second,
independent layer where the bytes are encrypted *between the clients* and
the server never has the key. That's end-to-end encryption — deep dive B.
The two layers must be reasoned about independently."

**What's different at L6:** the three primitives named and *kept* distinct;
PFS attributed specifically to the *ephemeral* in ECDHE with the recorded-
traffic argument; 0-RTT replay caveat with an idempotency rule and ticket-
lifetime bound; pinning + CT + mTLS as defense-in-depth; and the explicit
"TLS secures the hop, the server still holds plaintext, where it
terminates is operational not security-relevant for an E2EE payload" — the
bridge that motivates the whole rest of the design.

**Anti-signal.** "We use SSL for encryption." Or treating key exchange,
encryption, and authentication as one undifferentiated blob. Or thinking
TLS-at-the-edge means the messages are secure end-to-end. → Packet:
*"Said 'SSL'; conflated key exchange, bulk encryption, and authentication;
believed edge-terminated TLS protected message content from the server.
Stopped at transport security."*

**Packet quote (Hire).**
> *"Walked TCP (no security) → TLS 1.3 1-RTT → WSS in order. Kept the
> three primitives distinct: ECDHE key agreement, AES-GCM/ChaCha20 bulk
> AEAD, certificate authentication. Attributed PFS specifically to
> ephemeral DH (recorded-today, leaked-key-tomorrow can't decrypt). Named
> the 0-RTT replay caveat and restricted it to idempotent requests; added
> cert pinning + CT + internal mTLS. Crucially stated that TLS secures only
> the hop and the server still holds plaintext — making transport security
> necessary-but-not-sufficient and motivating E2EE. Unprompted."*

### Deep dive B — End-to-end encryption: the gateway can't decrypt (and never could)

**Phrasing.** *"Now I want the server to provably *not* be able to read a
message, even though it routes it — and Bob is offline when Alice sends
the first one. Walk me through the initial key agreement and the
per-message keys. What does the key server store? And what stops a
*malicious* key server from reading everything?"*

**Strong L5 answer.** "End-to-end encryption with the **Signal Protocol**.
Each user has a long-term **identity key pair**; the **private key never
leaves the device**. To message someone who's offline, Signal uses
**X3DH — Extended Triple Diffie-Hellman**. The key server holds, for each
user, their **public** identity key, a **signed prekey** (a medium-term
public key signed by the identity key), and a pool of **one-time prekeys**
(single-use public keys). Alice fetches Bob's **prekey bundle** (all
public), does several DH operations combining her keys with Bob's, derives
a shared secret, and can send an encrypted first message **while Bob is
offline** — Bob completes the same agreement when he comes online. The key
server **only ever stores public keys** — nothing it can decrypt with. For
ongoing messages, the **Double Ratchet** derives a fresh key for each
message, so even if one key leaks, it doesn't expose the others. The
server is just a **relay**: it sees ciphertext plus the routing metadata
(who to deliver to, timestamp) but not the content. A malicious key server
is the weak point — it could hand Alice a fake key — so Signal lets users
verify each other's **safety numbers** out of band." Correct and complete
in outline — names X3DH, public-only key server, offline first message,
Double Ratchet, untrusted relay, and verification. What's missing is FS
*and* PCS named *separately* with their mechanisms, the invariant stated
crisply, and the TOFU/key-change detail.

**Strong L6 answer.** "Anchored on the **Signal Protocol**, and I'll state
the invariant first because everything serves it: **no server component
ever holds a private key capable of decrypting a message, and the only
thing that makes trusting an untrusted server safe is out-of-band
verification.** Now the mechanics.

*X3DH for asynchronous initial agreement.* Every device has a long-term
**identity key** (private key never leaves the device). Each user
publishes to the key server a bundle of **public** material: the public
identity key, a **signed prekey** (medium-term, rotated periodically,
signed by the identity key so its authenticity is checkable), and a pool
of **one-time prekeys** (single-use). When Alice wants to message an
*offline* Bob, she fetches his bundle and performs **three-to-four DH
combinations** — identity×signed-prekey, ephemeral×identity, ephemeral×
signed-prekey, and ephemeral×one-time-prekey — and hashes them into a
shared root secret. She can encrypt and send the first message
immediately; Bob reconstructs the same secret when he next connects. The
one-time prekey is consumed (deleted) on use. **The key server stores only
public keys** — it cannot derive the shared secret, because it never has a
private key. That's the invariant made concrete.

*Double Ratchet for per-message keys — and here are the two properties,
which are NOT the same thing.* On top of the X3DH root key runs the Double
Ratchet, which gives **two distinct guarantees I want to name separately**:

- **Forward secrecy** — *compromise today does not expose* past *messages.*
  This comes from the **symmetric-key ratchet**: each message key is
  derived from a KDF chain and **the input is deleted after deriving the
  next link**, so you cannot run the chain backwards to recover an earlier
  message key. Steal the device now and you can't decrypt yesterday's
  messages.
- **Post-compromise security / self-healing** — *compromise today does not
  expose* future *messages, once the ratchet turns.* This comes from the
  **Diffie-Hellman ratchet**: each side periodically ratchets in a *fresh
  DH keypair*, mixing new entropy the attacker never saw. So after the next
  back-and-forth, the chain heals — an attacker who stole your keys is
  locked out of future messages. FS protects the past; PCS protects the
  future; **the symmetric ratchet gives FS, the DH ratchet gives PCS.**
  Conflating them is the single most common crypto error I hear.

*The server is an untrusted relay — say it as the invariant.* The relay
sees an opaque ciphertext blob **plus the cleartext routing metadata it
needs to deliver** (recipient ID, timestamp, maybe message size). It
routes by metadata exactly like guide 13's fan-out — *that's why fan-out
survives E2EE* — but **no relay or key-server component holds a private
key capable of decryption**. A full server breach yields ciphertext and
metadata, never plaintext.

*Trust establishment — verification is the trust anchor that makes the
untrusted server safe.* The residual risk is the **key server**: a
malicious or compromised one can perform an **active MITM** by handing
Alice *its own* public key in place of Bob's. Three layers of defense:
**TOFU (trust-on-first-use)** — accept the key the first time and pin it;
**out-of-band verification** — Alice and Bob compare a **safety number /
key fingerprint** (scan a QR code in person, or read the number aloud),
which is a hash of both identity keys, so a substituted key produces a
mismatch; and **key-change warnings** — if a contact's key changes later,
warn the user (could be a new device, could be an attack). The crucial
point: **key-server compromise only enables MITM if users skip
verification.** Verification is what lets you build E2EE on top of an
*untrusted* server — you don't have to trust the key distributor, you have
to give users a way to detect substitution.

*One honest summary:* the server routes opaque ciphertext by cleartext
metadata; the decryption keys live only on the endpoints; FS and PCS are
two separate ratchet-provided properties; and verification is the anchor
that makes the untrusted relay safe."

**What's different at L6:** the invariant stated first and crisply (no
server private key can decrypt; verification makes an untrusted server
safe); FS and PCS named as **two distinct properties** with **two distinct
mechanisms** (symmetric ratchet vs DH ratchet) and tied to past-vs-future;
X3DH's public-only key server and offline-first-message made concrete;
TOFU + safety-number + key-change-warning as the three-layer trust story,
with the explicit "compromise enables MITM *only if users skip
verification*."

**Anti-signal.** "The server encrypts with a managed key" (not E2EE — the
server can read it). Or "we have forward secrecy because we rotate keys"
with no separation of past-vs-future protection and no mechanism. Or
"we trust the key server to give us the right key" with no verification. →
Packet: *"Put the decryption key on the server (not actually E2EE);
conflated forward secrecy with post-compromise security; trusted the key
server blindly with no out-of-band verification."*

**Packet quote (Strong Hire).**
> *"Stated the invariant up front: no server component holds a
> decryption-capable private key, and out-of-band verification is what
> makes an untrusted server safe. X3DH for async agreement (public-only key
> server, encrypted first message to an offline recipient). Named forward
> secrecy and post-compromise security as TWO distinct properties — past
> vs future — provided by the symmetric ratchet and the DH ratchet
> respectively. Server is an untrusted relay routing opaque ciphertext by
> cleartext metadata. Trust = TOFU + safety-number QR verification +
> key-change warnings, with 'compromise enables MITM only if users skip
> verification.' Unprompted."*

### Deep dive C — Scalable E2EE: multi-device, groups, and what E2EE breaks

**Phrasing.** *"Two things. First: a 5,000-member group, someone posts —
walk me through the encryption, and what specifically breaks if you treat
it like a 1:1. Second: the server can't read messages now — so how does a
push notification show 'Mom: dinner?', and what other server-side features
just died?"*

**Strong L5 answer.** "**Multi-device:** each device is its own identity
with its own key pair, so the sender encrypts the message **once per
recipient device** — sender-side fan-out to the recipient's set of
devices. **Groups:** the naive approach is pairwise — encrypt the message
separately to every member — but for 5,000 members that's 5,000
encryptions per message, which is too much, so for large groups you use
**Sender Keys**: each sender has a per-group symmetric *sender key*
distributed once (pairwise) to all members, then the message is encrypted
*once* under that sender key and the same ciphertext goes to everyone —
O(1) per message instead of O(n). **What E2EE breaks:** the server can't
read content, so **push notifications** can't include the text from the
server — instead you send an **encrypted payload** the client decrypts, or
a contentless 'you have a message' wakeup; **server-side search** moves to
a **client-side index**; **content moderation** can't scan messages, so
it moves to **client-side reporting**; and **backup** has to be
**encrypted with a key the user holds**, not readable by the server."
Solid — names per-device fan-out, Sender Keys, and the main breakage list
with mitigations. What's missing is the Sender-Keys→MLS flip with a
threshold, the key-change/device-trust subtlety, sealed sender, and the
ciphertext-fan-out cost framing.

**Strong L6 answer.** "Three parts: multi-device, group scaling with a
committed flip point, and the breakage-and-mitigation matrix that's the
real system-design content.

**Multi-device — each device is a cryptographic identity.** One user with
a phone, laptop, and web session is **three key pairs**, each with its own
X3DH bundle and its own Double Ratchet session per conversation. The
sender encrypts to a **signed device list** for each recipient — so a
message to a 1:1 contact with 3 devices is **3 ciphertexts**, and the
general **ciphertext fan-out = recipients × devices**. The trust subtlety:
when a user **links a new device**, that device's key must propagate to
contacts, and **the server must not be able to silently inject a rogue
device** into someone's device list — so the device list is **signed by
the user's identity key** and a device change triggers a **key-change
warning** to contacts, same trust mechanism as deep dive B. That's the
**malicious-device-addition** attack and its defense.

**Group E2EE — Sender Keys, flipping to MLS at a threshold.**
- **Small-to-medium groups → Sender Keys** (Signal's group optimization).
  Each member generates a **sender key** (a symmetric chain key) and
  distributes it **pairwise** to every other member *once* via the
  existing 1:1 channels. Then each message is encrypted **once** under the
  sender's sender key — **O(1) encryption per message**, and the same
  ciphertext fans out to all members. Per-message cost is great; the catch
  is **key rotation on membership change**: when someone *leaves*, every
  remaining member must rotate and redistribute sender keys to preserve
  forward/post-compromise security, which is **O(n) redistribution**, and
  across all senders it trends toward **O(n²)** churn for a high-turnover
  group.
- **Large / high-churn groups → MLS (RFC 9420 / TreeKEM).** MLS arranges
  members as leaves of a **balanced binary tree** of key-encapsulation
  nodes; a member updating their key touches only their **leaf-to-root
  path**, so a group key update is **O(log n)** instead of O(n) — in a
  group of 1,000, ~10 operations instead of 1,000. MLS gives FS and PCS at
  group scale and is the modern answer for large, dynamic groups.
- **The committed flip point.** I flip from Sender Keys to MLS at roughly
  **a few hundred to ~1,000 members** — the threshold is where the
  membership-churn cost of Sender-Key redistribution (≈O(n) per change, per
  sender) exceeds MLS's O(log n) update. For a *small, stable* group Sender
  Keys are simpler and cheaper; for a *large or churny* group MLS wins on
  the key-update cost. I'd make it a per-group attribute so a group that
  grows past the threshold **migrates** Sender-Keys→MLS as a real
  operation. The flip is driven by **n × churn-rate**, not n alone.

**What E2EE breaks — and the mitigations (the system-design meat).**

| Feature (worked in guide 13) | Why E2EE breaks it | Mitigation |
|---|---|---|
| **Fan-out / routing** | *Doesn't* break | Relay routes opaque ciphertext by **cleartext metadata** (recipient, ts) — guide 13's fan-out is intact |
| **Push notification content** | Push service can't read the body | **Encrypted push payload** decrypted client-side, or a **contentless wakeup** ("you have a message") that triggers a client fetch |
| **Server-side search** | Server never sees plaintext | **Client-side index**: each device indexes its own decrypted messages locally |
| **Spam / abuse / moderation** | Server can't scan content | **Client-side reporting** (user reports decrypt-and-attach), **sender attribution**, **metadata signals** (volume, velocity, graph), **rate limits** — never content scanning |
| **Backup / history** | Server can't hold readable history | **Encrypted backup with a user-held key** (or HSM-backed PIN/secure-enclave recovery so the server still can't read it) |
| **Multi-device sync** | New device has no past keys | Re-encrypt history device-to-device, or sync from an encrypted backup; **never** a server-readable copy |

**Metadata protection — sealed sender.** Even with content encrypted, the
relay learns *who sends to whom*. **Sealed sender** removes the sender
identifier from the envelope the server sees — the recipient learns the
sender (from inside the encrypted payload), the server does not. It's not
perfect (timing/traffic analysis remains), but it shrinks the metadata the
untrusted relay holds, which matters because metadata is what survives
E2EE.

**The cost shape — and how it differs from guide 13.** E2EE *pushes the
crypto compute to the clients* (encrypt/decrypt happen on phones — nearly
free for the server, which just relays bytes). What it *multiplies* is
**ciphertext copies = recipients × devices**: a 1:1 message to a
3-device contact is 3 ciphertexts; a Sender-Keys group message is one
ciphertext but a *membership change* triggers O(n) key-distribution
messages. So the server-side dominator shifts from guide 13's
plaintext-fan-out *compute* to **fan-out *bandwidth/relay* of ciphertext
copies plus key-distribution traffic** — and the key server's read QPS
(every new conversation fetches a bundle). The crypto itself is *not* the
dominator; it's on the edge."

**What's different at L6:** per-device cryptographic identity with the
signed-device-list defense against malicious device addition; Sender Keys
*and* MLS with a **committed flip threshold** justified by membership-churn
cost (O(n) redistribution vs O(log n) TreeKEM update) and named as a
migration; the **breakage-and-mitigation matrix** with fan-out explicitly
*surviving*; sealed sender for metadata; and the **cost-shape shift** from
plaintext-fan-out-compute to ciphertext-copy-bandwidth + key-distribution.

**Anti-signal.** Pairwise-encrypt to 5,000 members with no group
optimization; or "E2EE, and search/push/moderation all still work the
same"; or never naming that fan-out *survives* because the server routes by
metadata; or injecting a new device with no signed-device-list defense. →
Packet: *"Used pairwise encryption for a 5,000-member group (no Sender
Keys/MLS); claimed E2EE changed nothing server-side; didn't see that
fan-out survives via cleartext metadata or that push/search/moderation/
backup each need a client-side mitigation."*

**Packet quote (Hire L6).**
> *"Per-device cryptographic identity; ciphertext fan-out = recipients ×
> devices; signed device list to block malicious device addition. Group
> crypto: Sender Keys (O(1)/msg) flipping to MLS/TreeKEM (O(log n)
> key-update) at ~hundreds–1k members, justified by membership-churn cost
> and named as a migration. Gave the breakage-and-mitigation matrix — push
> = encrypted payload/contentless wakeup, search = client index,
> moderation = client reporting + metadata, backup = user-held key — and
> stressed fan-out SURVIVES because the relay routes opaque ciphertext by
> cleartext metadata. Added sealed sender for metadata, and shifted the
> cost dominator to ciphertext copies + key-distribution, not crypto
> compute. Unprompted."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **"We'll use SSL."** Deprecated term, and it conflates three primitives.
  One sentence; push on which of key-exchange / encryption / authentication
  they mean.
- **Stopping at transport TLS.** Believing edge-terminated TLS protects
  content from the *server*. It doesn't — the server holds plaintext. This
  is the necessary-but-not-sufficient miss.
- **Server-held decryption key.** "The server / KMS manages the message
  key." Then it's not end-to-end; the server can read everything.
- **Conflating FS and PCS.** "Forward secrecy because we rotate." Can't say
  which protects past vs future, or which mechanism (symmetric vs DH
  ratchet) gives each. The crypto-axis L5 ceiling.
- **Trusting the key server.** No out-of-band verification → a malicious
  key server MITMs silently. Verification is the trust anchor; missing it
  guts the whole guarantee.
- **Pairwise group encryption at scale.** O(n)/message, O(n²) on churn for
  a large group. The Sender-Keys→MLS flip is the lesson.
- **"E2EE changes nothing server-side."** Ignoring that search, push
  content, moderation, and backup all break and need client-side
  mitigations.
- **Forgetting fan-out survives.** Not seeing that the relay still routes
  opaque ciphertext by *cleartext metadata* — and so guide 13's fan-out is
  intact, which is the reassuring half of the breakage story.
- **No metadata story.** Content encrypted but who-talks-to-whom wide open,
  with no sealed-sender / minimization awareness.
- **0-RTT for everything.** Allowing replayable 0-RTT early data on
  state-changing requests.
- **No cost / dominator.** Not seeing that crypto is cheap (on clients) and
  ciphertext copies (recipients × devices) + key-distribution traffic are
  the actual cost.

### Interviewer-side (your own traps)

- **Letting them relitigate AES-vs-ChaCha as a religious debate.** Both are
  fine AEADs; it's a 30-second commit. By minute 30 force the E2EE
  invariant and the FS-vs-PCS distinction — that's where the signal is.
- **Leading them to X3DH / the FS-vs-PCS split / the Sender-Keys flip.**
  These are the elegant answers, so they're tempting to hand over. Don't.
  If they reach them alone, that's the L6 finding; if you hand it over, the
  packet won't write convincingly.
- **Not driving to "the server is in the threat model."** It's the whole
  premise. If by minute 20 they're still treating TLS as the answer, push
  the subpoena/breach scenario explicitly.
- **Over-rewarding "we use the Signal Protocol."** Naming it is not a
  signal. "X3DH because Bob's offline and the key server holds only public
  prekeys; Double Ratchet for FS via the symmetric ratchet *and* PCS via
  the DH ratchet; verification because the key server is untrusted" *is*.
- **Eating their 3-minute question window.** Still scoring Googleyness.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it.
Numbers explicit, trade-offs committed. **This assumes guide 13's scale
and delivery design and layers security on top** — I won't re-derive the
gateway, inbox, or fan-out hybrid; I'll reference them and reason about
what security changes.

### 6.1 Functional requirements (committed scope)

v1: **transport security** for every client↔server hop (TLS 1.3 / WSS) and
**mTLS** internally; an **untrusted key server** distributing **public**
key material (identity keys, signed prekeys, one-time-prekey pools);
**asynchronous initial key agreement** (X3DH — encrypt a first message to
an *offline* recipient); **per-message keys** with **forward secrecy** and
**post-compromise security** (Double Ratchet); **multi-device** (per-device
cryptographic identity, sender-side fan-out to a signed device list);
**group E2EE** (Sender Keys flipping to MLS at a threshold); **trust
establishment** (TOFU + safety-number/QR verification + key-change
warnings); and the breakage mitigations — **encrypted push** (or
contentless wakeup), **client-side search index**, **client-side
abuse reporting + metadata signals**, **user-key-held encrypted backup**,
and **sealed-sender** metadata minimization. The invariant: **no server
component holds a private key capable of decryption.**

**Out of scope v1, said out loud:** the chat scale/delivery mechanics
themselves (connection management, inbox, ordering, fan-out hybrid — all
inherited from `13-realtime-chat.md`); the credential/login flow and IdP
federation (that's `06-sso-auth-service.md`); session lifecycle/revocation
(that's `10-session-management.md`); voice/video media encryption (SRTP
is a separate data plane — `12-voice-video-calling.md`); post-quantum key
exchange (a real roadmap item — PQXDH — but not v1's focus).

### 6.2 Non-functional requirements (with numbers)

Inherited scale from guide 13 in *italics*; security-specific in **bold**.

| Metric | Target | Reasoning |
|---|---|---|
| *Concurrent connections* | *100M* | Inherited. Each rides a TLS/WSS connection — TLS handshake cost at reconnect matters. |
| *Messages/sec (peak)* | *~1M sent/sec* | Inherited. Each is now an opaque ciphertext blob to the relay. |
| TLS 1.3 handshake | **1-RTT added latency** (0-RTT on resumption, idempotent only) | The transport-layer cost; 0-RTT bounded by replay risk. |
| Resumption ticket lifetime | **~hours, not days** | Bounds a stolen-ticket replay window. |
| Prekey bundle size | **~few hundred bytes** (identity + signed prekey + one one-time prekey + signatures) | Fetched on every new conversation; small + cacheable. |
| One-time-prekey pool depth | **~100 per device** | Replenished when low (e.g. <20 left); deep enough to cover offline-send bursts. |
| Prekey replenishment trigger | **client uploads more when pool < ~20** | Keeps the pool from exhausting → preserves first-message FS. |
| Key-server read QPS | **≈ new-conversation rate** (read-heavy: every session start fetches a bundle) | Public-material-only → can be AP, cached, cheap. |
| Per-device key-state storage | **~1–4KB per active conversation** (ratchet state) on the *device* | Client-side; not a server cost. |
| Double-ratchet state / conversation | **~hundreds of bytes–few KB** (chain keys, DH keypairs, skipped-key cache) | On the endpoints. |
| Group-size flip (Sender Keys → MLS) | **~hundreds to ~1,000 members** | Above this, membership-churn redistribution (O(n)) loses to MLS O(log n). |
| Ciphertext fan-out multiplier | **recipients × devices** | The cost line that changed from guide 13's plaintext fan-out. |
| Revocation/verification SLA | **key-change warning surfaced within one fetch** | Detection, not prevention; verification is the anchor. |

### 6.3 Capacity estimation (worked)

- **Key server (read-heavy, public-only).** Every *new* conversation
  fetches a prekey bundle. If ~1% of 1M msg/sec opens a new conversation,
  that's ~10k bundle reads/sec — trivial, and **cacheable** (the signed
  prekey is reusable; only the one-time prekey must be consumed atomically).
  Storage: 1B devices × (identity + signed prekey + ~100 one-time prekeys ×
  ~32B) ≈ **~3–4KB/device of public material ≈ a few TB total** — small,
  and it's all *public*, so a breach leaks nothing decryptable.
- **One-time-prekey pool.** ~100/device, consumed one-per-new-X3DH, stored
  in a **Redis-shaped TTL/pool structure**; an atomic pop on fetch ensures
  single-use. Replenished by the client when low. **Pool exhaustion** for a
  popular offline user → fall back to the signed prekey (see 6.7) — the
  AP-vs-correctness trade is here.
- **Ciphertext fan-out.** A 1:1 message to a contact with avg ~2.5 devices
  ≈ 2.5 ciphertext copies; a small Sender-Keys group of 12 with ~2.5
  devices each is **one ciphertext per device-stream** (Sender Keys keep
  per-message O(1)), but a *membership change* costs O(n) key-distribution
  messages. The relay bandwidth scales with **recipients × devices**, not
  message count alone.
- **Crypto compute.** Encrypt/decrypt happen on **clients**. Server-side
  crypto cost ≈ 0 beyond TLS termination. This is why E2EE is *cheap for
  the server* — the compute moved to the edge.
- **TLS handshake load.** 100M connections reconnecting (guide 13's
  reconnect storms) means handshake volume; **0-RTT resumption** removes
  the round trip for idempotent reconnects, and session tickets keep it
  cheap — but the *first* `SEND` waits for 1-RTT to avoid replay.

**Numbers that changed a design choice:**
- key server holds only **public** material → it can be **AP and cheap**,
  and its compromise is bounded by **verification**, not by access control.
- **ciphertext fan-out = recipients × devices** → multi-device is the new
  cost multiplier vs guide 13; Sender Keys keep groups O(1)/message.
- **prekey pool depth × replenishment** → the AP target for "Alice can
  always start a conversation"; exhaustion degrades FS, not availability.
- group **churn × n** (not n alone) → the Sender-Keys → MLS flip point.

### 6.4 API design / key-exchange flow

```
# Transport (every hop): TLS 1.3 -> WebSocket upgrade = WSS
#   client --TCP--> --TLS1.3 (ECDHE + cert auth + AEAD)--> --Upgrade: websocket--> WSS
#   internal service<->service: mTLS (both present certs)

# Key server (CONTROL PLANE; PUBLIC material only; untrusted)
POST /v1/keys/identity        { device_id, identity_pub, signed_prekey_pub, sig }
POST /v1/keys/prekeys         { device_id, one_time_prekeys[] }   # replenish pool
GET  /v1/keys/bundle/{user}   -> { per-device: identity_pub, signed_prekey_pub, sig,
                                   one_time_prekey_pub? }          # ? absent if pool empty
GET  /v1/keys/devices/{user}  -> { signed device list }           # for multi-device fan-out

# X3DH initial agreement (CLIENT-SIDE; server only relays/serves public keys)
#   Alice: fetch Bob's bundle -> DH(IK_A, SPK_B), DH(EK_A, IK_B),
#          DH(EK_A, SPK_B), DH(EK_A, OPK_B) -> KDF -> root key
#   Alice sends: { to: Bob, ciphertext = DoubleRatchet(root, msg),
#                  EK_A_pub, used_one_time_prekey_id }     # first message; Bob offline OK

# Message relay (DATA PLANE; opaque ciphertext + cleartext routing metadata)
WS  SEND   { to_device_list, ciphertext_per_device[], conv_id, ts }   # server can't read ciphertext
WS  PUSH   { from?, ciphertext, conv_id, ts }                         # from? omitted under sealed sender

# Encrypted push (push service can't read content)
POST /v1/push  { device_token, encrypted_payload | "wakeup" }         # decrypt client-side

# Trust establishment (CLIENT-SIDE)
GET  /v1/safety-number/{peer}  -> fingerprint(IK_self, IK_peer)       # compare out-of-band / QR
#   key change for {peer} -> client raises a key-change WARNING
```

The shape: the **key server is control-plane and serves only public
keys**; the **relay is data-plane and carries opaque ciphertext** plus
the cleartext metadata it needs to deliver; **all key agreement and
encryption happen on the clients**; and **verification is a client-side
out-of-band step** the server cannot forge.

### 6.5 Data model

```
# Key server (durable-ish, PUBLIC material only — a breach leaks nothing decryptable)
identity_key:  (user_id, device_id) -> identity_pub, signed_prekey_pub, spk_sig, spk_rotated_at
prekey_pool:   (user_id, device_id) -> [one_time_prekey_pub ...]   # atomic pop on fetch; single-use
device_list:   user_id -> [{device_id, identity_pub} ...], signed_by_user_identity_key
               # signed by the USER so the server can't inject a rogue device

# Relay / message store (opaque to the server)
envelope:      (conv_id, seq) -> ciphertext_blob, to_device_id, ts   # server routes by metadata only
               # ordering/seq/inbox all inherited from guide 13 — unchanged, just opaque payloads

# Client-side ONLY (never on the server)
ratchet_state: conv_id -> { root_key, send_chain, recv_chain, DH_keypair, skipped_keys }  # ~1-4KB
search_index:  local full-text index over DECRYPTED messages                # client-side search
pinned_keys:   peer_user_id -> trusted identity_pub (TOFU)                   # key-change detection
encrypted_backup_key: user-held (PIN/enclave/HSM-recovery) — server can't read
```

**Why this split:** the key server holds **only public keys** — that's the
property that makes it *untrusted-but-useful*; losing or breaching it leaks
nothing decryptable, and active MITM via a substituted key is caught by
verification. **Private keys and ratchet state live only on devices.** The
relay's message store is the same store as guide 13 — same ordering,
inbox, and fan-out — but every **payload is an opaque ciphertext**, so the
delivery machinery is unchanged and the server simply *can't read*.

### 6.6 High-level architecture

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  Clients (phone / desktop / web) — each DEVICE = a crypto identity │
   │  holds: identity privkey, ratchet state, client search index,     │
   │         pinned peer keys (TOFU), encrypted-backup key              │
   │  does:  X3DH agreement, Double Ratchet encrypt/decrypt, verify     │
   └───────────────┬──────────────────────────────────────────────────┘
                   │
   ╔═══════════════▼═══════════════════════════════════════════════════╗
   ║  LAYER 1 — TRANSPORT SECURITY (TLS 1.3 / WSS)                      ║
   ║  TCP 3-way (no security) -> TLS 1.3 1-RTT [ECDHE key agreement +   ║
   ║  cert authentication + AES-GCM/ChaCha20 AEAD; PFS from ephemeral]  ║
   ║  -> WebSocket upgrade = WSS.  0-RTT resume (idempotent only).      ║
   ║  cert pinning + CT logs (anti-MITM).  TERMINATES AT THE SERVER --> ║
   ║  *** server holds the TLS plaintext, which is the E2E CIPHERTEXT ***║
   ╚═══════════════╤═══════════════════════════════════════════════════╝
                   │  (mTLS between internal services below)
        ┌──────────▼───────────┐          ┌─────────────────────────────┐
        │  WSS Gateway / Relay │  routes  │  KEY SERVER (UNTRUSTED)      │
        │  (DATA PLANE)        │  opaque  │  (CONTROL PLANE)             │
        │  sees: CIPHERTEXT +  │  by      │  stores PUBLIC keys ONLY:    │
        │  cleartext metadata  │  metadata│  identity_pub, signed prekey,│
        │  (recipient, ts)     │◄────────►│  one-time-prekey pool,       │
        │  CANNOT DECRYPT      │          │  signed device list          │
        │  fan-out = guide 13  │          │  CANNOT DECRYPT ANYTHING     │
        └──────────┬───────────┘          │  AP, cached, cheap           │
                   │                       └─────────────────────────────┘
   ╔═══════════════▼═══════════════════════════════════════════════════╗
   ║  LAYER 2 — END-TO-END ENCRYPTION (between CLIENTS only)            ║
   ║  X3DH initial agreement (offline-capable) -> Double Ratchet:      ║
   ║   symmetric ratchet = FORWARD SECRECY (past safe);                ║
   ║   DH ratchet = POST-COMPROMISE SECURITY / self-healing (future).  ║
   ║  INVARIANT: no server box holds a decryption-capable private key. ║
   ║  TRUST ANCHOR: out-of-band safety-number / QR verification +      ║
   ║  TOFU + key-change warnings (makes the untrusted server safe).    ║
   ╚═══════════════════════════════════════════════════════════════════╝

   inherited from guide 13 (unchanged, payloads now opaque): connection
   registry, per-recipient inbox, per-conversation seq ordering, push/pull
   fan-out hybrid. E2EE rides ON TOP without changing the delivery plane.

   what E2EE BREAKS (mitigations, client-side): push content -> encrypted
   payload / contentless wakeup; search -> client index; moderation ->
   client reporting + metadata; backup -> user-held-key encrypted backup;
   metadata -> sealed sender (server doesn't learn who->whom).
```

The design's whole point: **two independent layers** — transport TLS
secures the hop (and the server holds *its* plaintext, which is the E2E
*ciphertext*), and **end-to-end encryption secures the content so no server
box can read it**; the **key server is untrusted and holds only public
keys**; **verification is the trust anchor**; and **the delivery plane from
guide 13 is unchanged because it routes opaque blobs by cleartext
metadata**.

### 6.7 Layered transport security + key exchange (see deep dive A)

- **Order:** TCP (no security) → **TLS 1.3 1-RTT** (ECDHE key agreement +
  certificate authentication + AES-GCM/ChaCha20 AEAD) → **WebSocket upgrade
  = WSS**. Three primitives, three jobs, kept distinct.
- **PFS** from the **ephemeral** in ECDHE: a leaked long-term key can't
  decrypt recorded past sessions.
- **0-RTT** resumption removes the round trip on reconnect but is
  **replayable** → idempotent requests only; the first `SEND` waits 1-RTT;
  ticket lifetime ~hours.
- **Defense in depth:** **certificate pinning** + **CT logs** against
  CA-misissuance MITM; **mTLS** for internal service-to-service.
- **The bridge:** TLS terminates at the server, which holds plaintext.
  Where it terminates (edge vs gateway) is **operational, not
  security-relevant for an E2EE payload** — the application bytes are
  *already* end-to-end ciphertext. Transport is necessary-but-not-
  sufficient; the server-in-threat-model requirement forces Layer 2.

### 6.8 End-to-end encryption — the invariant (see deep dive B)

- **Invariant:** *no server component holds a private key capable of
  decryption; verification is what makes the untrusted server safe.*
- **X3DH:** key server distributes **public** identity key + signed prekey
  + one-time-prekey pool → Alice agrees a shared secret and sends an
  encrypted first message to an **offline** Bob; one-time prekey consumed.
- **Double Ratchet, two distinct properties:** **forward secrecy** (past
  safe) from the **symmetric-key ratchet** (KDF chain, prior inputs
  deleted); **post-compromise security / self-healing** (future safe once
  the ratchet turns) from the **DH ratchet** (fresh DH entropy mixed in).
  *FS ≠ PCS — name them separately.*
- **Untrusted relay:** ciphertext + cleartext routing metadata; routes like
  guide 13; can't decrypt.
- **Trust:** TOFU + **safety-number/QR out-of-band verification** +
  key-change warnings; **key-server compromise enables active MITM only if
  users skip verification.**

### 6.9 Scalable E2EE — multi-device, groups, breakage (see deep dive C)

- **Multi-device:** each device = a crypto identity; encrypt to a
  **signed device list**; ciphertext fan-out = **recipients × devices**;
  signed list blocks **malicious device addition**; device change → warning.
- **Groups:** **Sender Keys** (O(1) encryption per message) for small/stable
  groups; **MLS / TreeKEM** (O(log n) key update) for large/churny groups;
  **flip at ~hundreds–1,000 members**, driven by **n × churn**, named as a
  migration.
- **What E2EE breaks + mitigations:** push content → encrypted payload /
  contentless wakeup; search → client-side index; moderation → client
  reporting + sender attribution + metadata signals + rate limits; backup →
  **user-held-key encrypted backup** (HSM/PIN recovery); multi-device sync →
  device-to-device or encrypted-backup, never server-readable.
- **Metadata:** **sealed sender** so the relay doesn't learn who→whom.
- **Fan-out survives** because the relay routes opaque ciphertext by
  cleartext metadata — guide 13's delivery plane is intact.

### 6.10 Multi-region / consistency

CAP commits, said out loud: **prekey-pool reads AP; device-list correctness
CP-leaning; established Double-Ratchet sessions are
region-/server-independent.**

- **Key server is read-heavy and AP.** Bundle reads (identity + signed
  prekey) are cacheable and replicated; a regional blip serves stale-but-
  valid *public* keys — acceptable, because public keys change rarely and a
  substituted/stale key is caught by **verification**. **Availability of
  the prekey pool** is the priority: Alice should *always* be able to start
  a conversation.
- **The one CP-leaning piece: the device list.** You must **not encrypt to
  a stale or removed device** (that's a security regression — a removed
  laptop shouldn't keep decrypting). So the **signed device list** wants
  read-your-writes / bounded staleness consistency: I commit to a
  **bounded device-list staleness (e.g. ≤ a few seconds, surfaced as a
  key-change warning if it changed)** — closer to CP than the prekey pool.
  The atomic **one-time-prekey pop** (single-use) also wants linearizable
  consume, but degrades gracefully to the signed-prekey fallback (below).
- **Prekey exhaustion (the named trade).** If a popular offline user's
  one-time-prekey pool is empty, X3DH **falls back to the signed prekey
  alone** — the agreement still succeeds, but the **first message loses
  one-time-prekey forward secrecy and becomes replayable** until Bob comes
  online. I accept that for *availability* (Alice can still message), bound
  it by aggressive replenishment (pool < 20 → top up) and **rate-limiting
  bundle fetches** so an attacker can't deliberately drain the pool, and I
  **name the trade out loud**: availability over first-message FS, bounded
  and monitored.
- **Control-plane / data-plane split for crypto.** The **key-distribution
  control plane** (key server) and the **encrypted-message data plane**
  (relay) are separate. **A key-server outage must not drop established
  encrypted sessions** — existing Double Ratchet conversations keep
  ratcheting locally with zero server involvement; only *new* conversation
  setup and *new* device linking degrade. This is the security analog of
  guide 13's control/data-plane split.

### 6.11 Cost (back-of-envelope, monthly)

Public-cloud pricing as a proxy at the 6.2 numbers. **The cost shape
differs from guide 13: crypto moves to the clients (cheap for us), but
ciphertext copies multiply.**

| Component | Notes | $/mo |
|---|---|---|
| *Relay / gateway fleet (inherited)* | guide 13's connection fleet; now routes opaque blobs; **ciphertext fan-out = recipients × devices** inflates relay bandwidth | **~$350–650k** |
| Key server (public-material store) | read-heavy bundle fetches, cached, AP; small public data | ~$25k |
| One-time-prekey pool (Redis-shaped) | atomic pop, TTL, replenishment; soft state | ~$15k |
| TLS termination compute | handshakes at 100M-connection reconnect scale; 0-RTT resumption amortizes | ~$30k |
| Sealed-sender / push relay | encrypted push payloads, contentless wakeups | ~$20k |
| Server-side crypto compute | **~$0 — encryption is on the clients** | ~$0 |
| **Total** | | **~$440–740k/mo** |

**Dominator: the relay fan-out of ciphertext copies** (recipients ×
devices) — *not* crypto compute, which is on the edge. This is the contrast
with guide 13: there the dominator was the connection-fleet *memory* and
inbox storage of *plaintext* fan-out; here it's the relay *bandwidth* of
*ciphertext* copies plus key-distribution traffic, with crypto compute
pushed off our books entirely. Multi-device is the multiplier; Sender Keys
keep groups O(1)/message so a megagroup doesn't blow up the per-message
cost (only its membership churn does).

### 6.12 Failure modes & blast radius

| Failure | Effect | Mitigation / policy |
|---|---|---|
| **Key-server compromise** | Attacker can *attempt* active MITM by substituting a public key | **Out-of-band verification** (safety number/QR) catches substitution; key-change warnings; the server holds **only public keys** so a breach leaks **nothing decryptable**. Fail toward **warning the user**, not silent acceptance |
| **One-time-prekey exhaustion** (popular offline user) | First message can't use a one-time prekey | **Fall back to the signed prekey** — agreement still succeeds; **first-message FS degraded + replayable** until peer online. Bounded by replenishment (<20 → top up) + bundle-fetch rate limits. Named trade: availability over first-message FS |
| **Lost / wiped device keys** | Ratchet state gone; can't decrypt old sessions | **Session re-establishment** (new X3DH) + **key-change warning** to contacts; restore from **user-key-held encrypted backup**; past messages unrecoverable without backup (that's FS working as designed) |
| **TLS cert expiry / misissuance** | MITM risk / outage | **Cert pinning** in the client + **CT logs** to detect misissuance; automated rotation + monitoring; mTLS for internal hops |
| **0-RTT replay** | Replayed early-data on reconnect | **0-RTT only for idempotent requests**; first state-changing `SEND` waits for the 1-RTT handshake; short ticket lifetime |
| **Malicious device addition** | Rogue device injected into a user's device list to read messages | **Device list signed by the user's identity key** (server can't inject); device change → **key-change warning** to contacts; verification re-anchors trust |
| **Key-server outage** | Can't fetch bundles / link new devices | **Control/data-plane split**: established Double-Ratchet sessions keep working with **zero server involvement**; only new-conversation setup + device linking degrade; key server is AP and replicated |

**Fail-open vs fail-closed, per path:** the **message data plane fails
toward availability** (a key-server blip never drops established encrypted
sessions — they ratchet locally). The **trust / device-list path fails
toward warning the user** (a key change or a substitution surfaces a
warning rather than silently proceeding; we do **not** silently encrypt to
an unverified-and-changed key). And the **prekey-exhaustion path fails
toward availability with a named FS degradation**. This per-path split is
the L6 commit.

**SLO/error budget.** Key-server availability (bundle fetch) ≥ 99.95%;
established-session delivery rides guide 13's 99.99% (unaffected by the key
server). Verification is **detection, not an SLO** — the security property
is "a substitution is *catchable*," not "prevented."

### 6.13 Evolution at 10× (1B users, ~1B device keys, 10M msg/sec)

- **Key server:** unchanged in *shape* — read-heavy, public-only, AP,
  cached; add replicas/shards by `hash(user_id)`. Bundle-fetch QPS scales
  with new-conversation rate; caching the (reusable) signed prekey absorbs
  most of it. Named seam: the **one-time-prekey pool** write/pop rate — keep
  it sharded and the replenishment aggressive so exhaustion stays rare.
- **Ciphertext fan-out:** the cost wall. recipients × devices at 10× is the
  relay-bandwidth dominator; Sender Keys keep groups O(1)/message so the
  pressure is multi-device + group *membership churn*, not message volume.
- **Groups:** the **Sender-Keys → MLS threshold may lower** as groups grow;
  it's a per-group knob + a migration, not a redesign. MLS's O(log n)
  updates are what make very large groups tractable at 10×.
- **Crypto compute:** still on the clients — **does not appear on our cost
  curve.** The one architectural seam that *could* change is the cipher
  suite: a **post-quantum key exchange (PQXDH)** is the roadmap item, and
  that's a *protocol* change (hybrid classical+PQ KEM in X3DH), not a knob.
- **Cost:** ~linearly with relay bandwidth (ciphertext copies); the key
  server stays cheap because it's public-only and cacheable.

**What does *not* change:** the invariant (no server private key decrypts);
the FS-via-symmetric-ratchet / PCS-via-DH-ratchet split; the
untrusted-public-only key server; verification as the trust anchor; the
two-layer transport-vs-E2E separation; the breakage-mitigation matrix; the
control/data-plane split. The seams named at v1 are the seams at 10×.

### 6.14 What I'd own vs. delegate

I'd personally own the **cryptographic protocol contract** — the X3DH/
Double-Ratchet message format, the FS/PCS guarantees, and the
no-server-private-key **invariant** (the security-critical thing the whole
product's trust rests on) — and the **trust-establishment UX** (safety
numbers, key-change warnings), because the human end is where E2EE
actually succeeds or fails. I'd delegate the **transport-TLS / WSS edge**
to the team that already runs the connection gateway (it's guide 13's
fleet — a clean seam), the **key-server operation** to the team that runs
our public-material KV/Redis tier (it's public-only and AP, so it's a
low-risk hand-off), the **push relay** to the notifications team (with the
encrypted-payload contract pinned), and **client search/backup** to the
client platform teams. The **MLS group-crypto library** is a natural
shared-library hand-off to a crypto-platform team, with the protocol
contract owned centrally.

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence. Right is the level
call.

| Evidence | Call |
|---|---|
| "We'll use SSL." Conflated key exchange / encryption / authentication; believed edge TLS protected content from the server; no end-to-end story even when pushed on a server breach/subpoena. | **Strong No Hire** |
| Reached "encrypt the messages," but put the key on the server / a KMS (not actually E2EE); when pushed, couldn't make the server *unable* to decrypt; conflated forward secrecy with key rotation. | **No Hire** |
| Separated transport TLS from E2EE and named the Signal Protocol; key server holds public keys; but couldn't distinguish FS from PCS, missed out-of-band verification (trusted the key server), and claimed E2EE broke nothing server-side. Saw pieces, not the system. | **Lean No Hire** |
| Cleanly separated the three layers and the three TLS primitives (ECDHE / AEAD / certificate); knew WSS-not-SSL and TLS-not-SSL. Committed to a Signal-style design: public-only key server, X3DH for offline first message, Double Ratchet for per-message keys, server-can't-read invariant. Named at least two broken features (push, search) with mitigations. Got verification as the backstop when prompted. Didn't separate FS from PCS or reach the Sender-Keys→MLS flip even when prompted. | **Hire L5** |
| All of L5-Hire, **plus**: attributed PFS specifically to ephemeral DH; named the untrusted-relay invariant; described per-device multi-device fan-out; reached the FS-vs-PCS distinction and verification-as-trust-anchor when prompted; gave a fuller breakage list with mitigations; some cost reasoning. | **Hire L5 / Lean L6** |
| All of the above **unprompted**, **plus**: kept the three TLS primitives distinct and tied **PFS to the ephemeral in ECDHE**; stated the **invariant** (no server box holds a decryption-capable private key; verification makes an untrusted server safe) up front; named **forward secrecy and post-compromise security as two distinct properties** with two distinct mechanisms (symmetric ratchet / DH ratchet); X3DH with public-only key server + offline first message; **TOFU + safety-number/QR verification + key-change warnings** with "compromise enables MITM only if users skip verification"; volunteered the **what-E2EE-breaks matrix** (push, search, moderation, backup) with mitigations and that **fan-out survives**; committed the **Sender-Keys → MLS flip** at a threshold; surfaced $/mo with the ciphertext-fan-out dominator; stated CAP commits. | **Hire L6** |
| Everything in L6, **plus**: named the **0-RTT replay caveat** + idempotency rule and cert-pinning/CT/mTLS as defense-in-depth; reasoned that **TLS-termination location is operational, not security-relevant for an E2EE payload**, so the two layers are independent; committed **prekey-pool AP vs device-list CP-leaning** with a bounded device-list staleness; handled **one-time-prekey exhaustion → signed-prekey fallback** and named the **first-message-FS trade**; defended the **control/data-plane split** (key-server outage must not drop established sessions); added **sealed sender** for metadata; named the **PQXDH** post-quantum roadmap as a protocol (not knob) change; named what they'd own (protocol contract + invariant + trust UX) vs delegate (TLS edge, key-server ops, push, client search); closed with a self-aware retro. | **Strong Hire L6** |

---

## Sources used in preparing this guide

- RFC 8446 — *The Transport Layer Security (TLS) Protocol Version 1.3*
  (1-RTT handshake, mandatory ephemeral (EC)DHE for PFS, AEAD-only cipher
  suites, 0-RTT early data and its replay caveat, removal of static-RSA
  key exchange): rfc-editor.org/rfc/rfc8446
- RFC 6455 — *The WebSocket Protocol* (the HTTP `Upgrade` handshake; over
  TLS this is `wss://` — WSS, the transport the gateway maintains):
  rfc-editor.org/rfc/rfc6455
- Signal — *The X3DH Key Agreement Protocol* (asynchronous initial key
  agreement; public identity key + signed prekey + one-time-prekey pool;
  encrypted first message to an offline recipient; the one-time-prekey-
  exhaustion → signed-prekey fallback and its forward-secrecy/replay
  caveat): signal.org/docs/specifications/x3dh/
- Signal — *The Double Ratchet Algorithm* (symmetric-key ratchet for
  forward secrecy; Diffie-Hellman ratchet for post-compromise security /
  self-healing; per-message keys; skipped-message handling):
  signal.org/docs/specifications/doubleratchet/
- Signal — *Technology Preview: Sealed Sender for Signal* (removing the
  sender identifier from the envelope the server sees; metadata
  minimization on an untrusted relay): signal.org/blog/sealed-sender/
- Signal — *Private Group Messaging / Sender Keys* (the group optimization:
  per-sender symmetric sender key distributed pairwise, message encrypted
  once → O(1) per message; rekey on membership change):
  signal.org/blog/private-groups/
- RFC 9420 — *The Messaging Layer Security (MLS) Protocol* + TreeKEM
  (balanced-tree group key agreement; O(log n) group key updates; FS and
  PCS for groups from two to thousands — the large-group answer):
  rfc-editor.org/rfc/rfc9420 and datatracker.ietf.org/doc/html/rfc9420
- WhatsApp — *Encryption Overview / Technical White Paper* (Signal Protocol
  at WhatsApp scale: per-device identity keys, multi-device sender-side
  fan-out, encrypted backups with a user-held key, contentless/encrypted
  push): whatsapp.com/security
- OWASP — *Transport Layer Security Cheat Sheet* (TLS 1.3, cert pinning,
  HSTS, AEAD cipher suites, mTLS for service-to-service):
  cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html
- Hello Interview — *Design Signal / WhatsApp E2EE* (interview framing for
  X3DH, Double Ratchet, the untrusted-server invariant, multi-device, and
  what E2EE breaks): hellointerview.com/learn/system-design
- Alex Xu — *System Design Interview Vol. 2* (the chat-system chapter this
  builds on; the E2EE extension: key exchange, per-message keys, group
  encryption): bytebytego / the book's chat + security chapters.

---

*End of guide. Related:* `13-realtime-chat.md` *(the scale/fan-out sibling
this builds on — connection management, inbox, ordering, and the push/pull
fan-out hybrid are all inherited here and simply made opaque); *
`10-session-management.md` *(auth/session security — cookie/token hygiene,
fail-open vs fail-closed, the CAP-committed revocation discipline that
rhymes with the trust/verification path here); and *
`06-sso-auth-service.md` *(identity attestation — who the parties* are*,
upstream of the key exchange that secures what they say).*
