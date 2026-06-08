# Question 13: Real-Time Chat / Messaging System (long-lived connections + fan-out, e.g. WhatsApp / Messenger / Slack)

> Interviewer's guide + golden answer for the 1-hour Google L5/L6
> system-design round. The anchor problem for the **long-lived
> connection management / message fan-out / delivery-semantics**
> archetype, and a canonical L6 prompt (Onsites.fyi lists *"design a
> global messaging platform with multi-device delivery and read
> receipts"* verbatim). Frame it around WhatsApp / Messenger / Slack.
> Voice: L7 Senior Staff who has run hundreds of these and has internal
> calibration on what good looks like. The calibration value is *not*
> whether the candidate can draw a WebSocket — it's whether they can hold
> three tensions in their head for an hour at once: **(a) where the
> long-lived connection state lives and what happens when a gateway node
> dies; (b) exactly-once-*feeling* delivery over an at-least-once
> transport, with per-conversation ordering; and (c) fan-out that works
> for both a 1:1 DM and a 100k-member channel.** This *looks* like
> CRUD-over-WebSocket. It is not.

---

## 1. Why this question (interviewer's framing)

A chat system *looks* like "open a socket, POST a message, push it to the
other guy." The modal L4 draws a WebSocket, a message table, and stops.
That answer is not wrong — it is *incomplete in exactly the place the
question is asking about*. The hard part of chat is that you are holding
**tens of millions of persistent connections** that each cost you memory
whether or not anyone is typing, the **transport gives you nothing for
free** (TCP closes, devices sleep, networks flap), and a single message
might fan out to one recipient or to a hundred thousand. The candidate
who treats this as "an API with a socket in front" is telling you they've
never operated a real-time system.

Five things this tests that little else in the canon tests as cleanly:

1. **Connection state at scale.** Where does "user U is live on gateway
   node G" live, how consistent is it, and what happens to a million
   connections when G dies at 3am during a deploy? This is the direct
   analog of a SIP registration / session layer — a registry of which
   node holds each live session, re-registration on reconnect, graceful
   drain before a push. The candidate who never asks "what holds the
   connection state" has missed the whole front half of the problem.
2. **Delivery semantics over an unreliable transport.** Exactly-once
   across a network to a sleeping phone is a fantasy. The honest answer
   is **at-least-once + receiver idempotency on a client-generated
   message ID**, with a **monotonic per-conversation sequence number**
   for ordering and gap detection. A candidate who promises exactly-once
   has failed the question in one sentence — same as the webhook round.
3. **The offline / mailbox model.** The recipient is offline 90% of the
   time. "Push it down the socket" is half a system; the other half is
   the durable **inbox/mailbox** that holds messages until a device
   reconnects and drains them. Delivered-to-server, delivered-to-device,
   and read are *three different states*, and the strong candidate names
   all three.
4. **Fan-out that flips strategy by conversation size.** A 1:1 DM and a
   small group are fan-out-on-write (push a copy to each recipient's
   inbox). A 100k-member channel is the celebrity/megachannel problem —
   write amplification kills you, so large channels flip to
   fan-out-on-read (a shared log the members pull). This is the same
   fan-out-on-write-vs-read decision as the news-feed canon, wearing a
   real-time costume.
5. **Backpressure and out-of-band metadata.** A device on a bad network
   is a slow consumer; an unbounded per-connection send buffer is an OOM
   waiting to happen. Typing indicators, presence, and read receipts
   ride a *different, droppable* path than messages, so they can't
   head-of-line-block the message stream. The L6 volunteers both.

### What "Hire" looks like at each level

**L5 Hire.** Commits to numbers by minute 10 (concurrent connections,
messages/sec peak, fan-out ratio, per-connection memory, delivery p99).
Draws the right shape unprompted: a **stateless-ish WebSocket gateway
tier** holding the persistent connections, a **connection registry**
(user/device → gateway node) in Redis-or-equivalent, a **message
service** that persists to a write-optimized store (Cassandra-shaped),
and a **per-recipient inbox** for offline delivery. States
**at-least-once + client-message-ID dedup** without being asked. Handles
"the recipient is offline" with a durable mailbox rather than dropping
the message. Knows a 100k-member channel can't fan out on write the same
way a DM does, at least when prompted.

**L6 Hire.** All of the above, **plus**: *drives the room* (narrates the
budget, pre-ranks the deep dives off the NFRs). Treats **connection
state as soft state recoverable by reconnect** and walks the
gateway-node-death blast radius — *and names the reconnect/thundering-herd
storm and how to damp it* — before being asked. Volunteers the
**monotonic per-conversation sequence number** as the structural
ordering + gap-detection primitive (gap → catch-up fetch, never a DLQ),
distinct from the client message ID used for dedup. States an explicit
**CAP commitment**: messages are AP with per-conversation ordering;
presence is best-effort AP. Volunteers the **push→pull flip for large
channels** with the threshold where it flips, unprompted. Names
**backpressure** (bounded send buffer, drop-to-mailbox vs.
disconnect-and-resync), the **out-of-band metadata path**, and the
**control-plane / data-plane split**. Surfaces $/month and the dominator
(gateway connection-fleet memory + inbox storage). Names what they'd own
vs. delegate.

### Classic downlevel traps

1. **"WebSocket + message table, done" with no connection registry.**
   The modal L4 answer. When pushed — "user A is on gateway 1, user B on
   gateway 7; how does A's message reach B?" — they either hand-wave a
   broadcast to all gateways (O(fleet) per message) or invent the
   registry on the spot. Packet: *"Did not have a routing answer for
   cross-gateway delivery; the connection registry was missing until
   prompted."*
2. **Promising exactly-once delivery.** "We'll ack end-to-end so it's
   exactly-once." Exactly-once *delivery* to a phone that can ack-then-
   die-before-persisting is impossible; the honest answer is
   at-least-once + idempotent apply on a client message ID. One sentence
   and the packet writes itself.
3. **Ordering left to wall-clock timestamps.** "We'll sort by
   `created_at`." Clocks skew across senders and gateways; two messages
   1ms apart on different nodes can invert. The structural answer is a
   **per-conversation sequence number**, assigned by the single writer of
   that conversation. Missing this is an L5-ceiling signal.
4. **Fan-out-on-write for everything.** Pushing a copy into 100k inboxes
   on every message in a megachannel is the write-amplification cliff —
   one message becomes 100k writes. The hybrid flip (large channels →
   pull) is the news-feed-celebrity lesson; not knowing it caps the level.
5. **No offline story.** "Push it down the socket." The recipient is
   offline most of the time; without a durable inbox the message is gone.
   This is not an edge case — it is the *common* case.
6. **Per-connection memory hand-waved.** "We'll just add servers." At
   10–50KB/connection × 100M connections the gateway fleet *is* the cost
   and the scaling wall; a candidate who never multiplies that out is
   missing the dominator.

---

## 2. The 60-minute plan

Minute-by-minute against the canonical budget. For each slice: **Say**
(verbatim lines), **Listen for** (the signal), **Push back when**
(trigger + line). Two deep dives are **mandatory**; the third is chosen
by weakness.

### 0–5 min — Intro & framing

**Say:** *"I'm <name>, L7 on an unrelated infra team. 60-second bios,
then: design a real-time chat / messaging system — think WhatsApp or
Slack. Users have persistent connections, send 1:1 and group messages,
get them in real time when online and on reconnect when offline, with
read receipts and multi-device. Drive it however you like; I'll
interject."*

**Listen for:** do they restate and name the hard part ("so the core
tension is holding millions of live connections *and* delivering
reliably over a transport that drops") or immediately draw a WebSocket
box? Restating + naming connection-state-plus-delivery is an L6 tell.
**Push back when:** they whiteboard before scoping. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** almost nothing. If asked "scale?" → *"Google/WhatsApp scale —
you tell me what that means."* If asked "1:1 only or groups?" → *"Both,
and I want a 100k-member channel in scope — Slack-style."* If asked
"end-to-end encryption?" → *"Out of scope for today unless you want it;
assume transport TLS and focus on delivery + connections."*

**Listen for:**
- Tight functional commit: connect/maintain a session; send 1:1; send
  group; deliver online (push) + offline (inbox drain on reconnect);
  ordering per conversation; read receipts + delivery receipts;
  presence/typing; multi-device. Bonus for cutting E2E crypto, message
  search, and media transcoding aloud (those are separate systems).
- NFRs **with numbers**: concurrent connections, messages/sec peak,
  fan-out ratio, per-connection memory, delivery p99, presence update
  rate, inbox storage/user, max channel size where push→pull flips.

**Push back when:**
- "Highly scalable" with no number → *"Quantify. Concurrent connections?
  Messages/sec at peak? Per-connection memory?"*
- "Exactly-once" → *"Across a network to a phone that can ack then die
  before it persists? Defend that, or give me the honest guarantee."*
- They conflate "real-time" with "we don't persist" → *"The recipient is
  offline 90% of the time. Where does the message live until they come
  back?"*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip the math, *"Before we draw — what
does the napkin say you need? Specifically, what does per-connection
memory do to your fleet?"*

**Listen for:**
- Worked numbers: connections (e.g. 100M concurrent), per-connection
  memory (10–50KB → gateway fleet size), messages/sec, fan-out
  amplification, inbox storage.
- **The numbers that decide the architecture:** (1) per-connection
  memory × connections sets the gateway fleet and is the dominator; (2)
  fan-out ratio + max channel size forces the push/pull hybrid; (3)
  offline-fraction forces the durable inbox.
- The right box diagram: client ⇄ **WebSocket gateway tier** ⇄
  **connection registry** (user/device → node) + **message service**
  (assigns seq, persists, fans out) + **per-recipient inbox** +
  **presence store** (TTL'd). Control plane separate from data plane.

**Push back when:**
- 12 boxes → *"Which are on the message hot path? p99 budget per hop?"*
- "Broadcast each message to all gateways" → *"That's O(fleet) per
  message at 1M msg/sec. How does a sender's gateway find *only* the
  recipient's gateway?"* (forces the registry)
- Reflexive Spanner-for-messages → *"At your write rate, what does
  Paxos-per-message cost, and do you need global strong consistency on a
  per-conversation-ordered chat log?"*

### 25–45 min — Deep dives (the diagnostic zone)

Two **mandatory** dives:

1. **Connection management at scale.** Ask: *"You have 100M live
   connections across your gateway fleet. One gateway holding a million
   of them hard-crashes mid-deploy. Walk me through the next 60 seconds —
   what happens to those users, where does the connection state go, and
   what do you do about the reconnect wave?"* This is where soft-state +
   registry re-registration + thundering-herd damping must appear.
2. **Message delivery semantics & ordering.** Ask: *"A user tells you
   they saw the same message twice, and separately saw an old message
   land *after* a newer one. Walk me through how each happens and how
   your system makes each safe."* This is where client-message-ID dedup +
   per-conversation sequence numbers + gap-detection-triggers-catch-up
   must surface. If the sequence number doesn't appear, that's a finding.

Third dive — pick on weakness — **fan-out** (*"a 100k-member announcement
channel; someone posts; what happens?"*): almost always worth forcing if
they haven't volunteered the push→pull flip.

**Listen for at L6:** connection state as recoverable soft state;
registry with TTL + heartbeat; jittered reconnect + backoff to damp the
herd; at-least-once + client-msg-ID dedup; per-conversation monotonic
seq; gap → catch-up fetch (never DLQ); the three delivery states;
push→pull flip with a threshold; bounded send buffer / backpressure;
out-of-band metadata path; control/data-plane split.

**Push back hard** on "broadcast to all gateways" (*"cost per message at
your fleet size?"*), on "sort by timestamp" (*"two senders, skewed
clocks, 1ms apart — which is first, and who decides?"*), on
"fan-out-on-write everywhere" (*"100k members, one message — how many
writes?"*), on "we just push, no inbox" (*"recipient's phone is asleep;
where's the message in 3 hours?"*).

### 45–55 min — Evolution / curveball

Pick **one** (mandatory if not already covered):
- *"A gateway node dies and 1M clients reconnect at once. Walk me through
  the thundering herd, minute by minute, and how you keep the fleet from
  cascading."* (the reconnect-storm scenario — *the* curveball here.)
- *"10× growth — 1B concurrent connections, 10M msg/sec. What breaks
  first?"* (per-connection memory wall; fleet + registry shard count.)
- *"One region holding a user's home inbox goes dark. What happens to
  their messages and their live sessions?"* (region failover; home-region
  inbox; ordering scope.)
- *"A 100k-member channel suddenly gets 500 msg/sec of activity. What
  backs up?"* (megachannel hot partition + the pull path.)

**Listen for:** seam identification, not redesign. L6 names the 2–3 knobs
(registry shards, gateway autoscale, push→pull threshold) and the
migration path; L5 tends to start over.

### 55–60 min — Wrap

**Say:** *"That's time. What would you do differently with 15 more
minutes? Then — questions for me?"*

**Still scoring:** self-aware retro ("I didn't get to cross-region
ordering on the inbox replication lag") and what they ask. A great
closing question I've heard: *"When a whole gateway zone fails over, who
owns the runbook for the reconnect-rate limiter, and how do you tune the
jitter so you don't DDoS yourself?"* That's someone who's been paged by a
reconnect storm.

---

## 3. Probing prompts (the kit)

Pre-loaded, with the signal each hunts. Drop verbatim; use silence after.

| # | Prompt | Signal hunted |
|---|---|---|
| 1 | "Concurrent connections, messages/sec peak, per-connection memory — commit." | Workload grounding. Per-conn memory × connections is the dominator and should drive fleet sizing. |
| 2 | "User A is on gateway 1, B on gateway 7. How does A's message reach B?" | The connection registry (user/device → node). Broadcast-to-all-gateways is the wrong answer. |
| 3 | "Where does 'user U is live on node G' live, and how consistent is it?" | Registry as soft state, TTL'd, refreshed by heartbeat; reconnect re-registers. |
| 4 | "Gateway holding 1M connections hard-crashes. Next 60 seconds?" | Soft-state recovery via reconnect; blast radius bounded to that node; herd damping. |
| 5 | "1M clients reconnect at once. How do you not melt the fleet?" | Jittered backoff, reconnect-rate limiter, capacity headroom — the thundering-herd answer. |
| 6 | "At-least-once or exactly-once? Defend it." | At-least-once + idempotency; rejects exactly-once-over-network as impossible. |
| 7 | "Subscriber saw the same message twice. What did you give them to dedupe on?" | Client-generated message ID; receiver idempotent apply / UNIQUE constraint. |
| 8 | "An old message lands after a newer one. What orders them?" | Monotonic per-conversation sequence number, not wall-clock; single writer assigns it. |
| 9 | "Client notices seq 41 then 43. What does it do?" | Gap detection → catch-up fetch of the missing range; degrades gracefully, never DLQ. |
| 10 | "Delivered-to-server, delivered-to-device, read — same thing?" | Three distinct states; receipts at each; the two-tick / blue-tick model. |
| 11 | "Recipient's phone is asleep. Where's the message in 3 hours?" | Durable per-recipient inbox/mailbox; drained on reconnect by cursor. |
| 12 | "100k-member channel, one post. How many writes?" | Fan-out-on-write amplification; the push→pull flip for large channels. |
| 13 | "At what channel size do you flip from push to pull, and why?" | A committed threshold (e.g. ~1–10k) and the write-amplification reasoning. |
| 14 | "A device on a 2G network can't drain its socket. What happens to its buffer?" | Bounded send buffer + backpressure; drop-to-mailbox or disconnect-and-resync, not unbounded growth → OOM. |
| 15 | "Typing indicators and read receipts — same path as messages?" | Out-of-band, droppable metadata path; must not head-of-line-block the message stream. |
| 16 | "Presence: too-short vs too-long heartbeat TTL — what breaks each way?" | Too short = flapping under jitter; too long = stale presence. The timeout-tuning trade-off. |
| 17 | "Per-conversation ordering — is it global ordering too?" | No. Ordering scope is per-conversation; explicitly *not* a global total order. |
| 18 | "Cost per month at your connection count. Dominator?" | L6 marker. Gateway connection-fleet memory + inbox storage, not "compute is free." |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

Pick **2–3**. For each: phrasing, L5 vs L6 shape, anti-signal, packet
quote. A and B are the mandatory pair; C if there's time or weakness.

### Deep dive A — Connection management at scale

**Phrasing.** *"You're holding 100M live connections across your gateway
fleet. One gateway node — call it G, holding a million connections —
hard-crashes mid-deploy. Walk me through the next 60 seconds: what
happens to those users, where the connection state lives, how routing
recovers, and what you do about the reconnect wave."*

**Strong L5 answer.** "The gateway tier holds the persistent WebSocket
(or long-poll fallback) connections; it's the stateful edge. A
connection registry — Redis or equivalent — maps `user_id`/`device_id` →
the gateway node holding that live connection, so the message service
can route a message to the right node. The registry entry is keyed per
device, and there's a per-user set of active devices so fan-out finds
them in one lookup. When G crashes, its million connections drop; the
clients detect the dropped socket and reconnect, landing on a *different*
gateway (via the load balancer), which writes a fresh registry entry. The
registry entries for G are stale; I'd TTL them so they expire, or have
the gateway clean up on graceful shutdown. While a user is briefly
disconnected, their messages queue in the inbox and drain on reconnect —
so nothing is lost, there's just a few seconds of delay." Correct,
competent, names the registry and the recovery-by-reconnect. What's
missing is the *reconnect storm* and the per-connection-memory wall as
first-class concerns.

**Strong L6 answer.** "Same shape, but three things I want to be explicit
about, because they're where this bites in production.

*Connection state is soft state, recoverable by reconnect.* I never try
to *migrate* a live connection off a dying node — that's a fool's errand.
The session (which conversations you're subscribed to, your cursor) is
reconstructable: on reconnect the client re-registers in the registry and
re-syncs from its inbox cursor. This is structurally the same as a SIP
registration layer — a registry of which node holds each live session,
re-registration on reconnect, and graceful drain before a planned deploy.
For a *planned* push I drain: stop accepting new connections on G, send
clients a `GOAWAY`-style hint to reconnect elsewhere *with jitter*, let
the fleet absorb them over a window, then take G down. The crash case is
the drain case without the warning.

*The reconnect storm is the real failure mode, not the lost connections.*
A million clients all detecting a dead socket within the same TCP-timeout
window will reconnect in a synchronized wave — a thundering herd that can
topple the *next* gateway, which sheds load, whose clients then reconnect,
and now you have a cascading fleet collapse. Mitigations, layered: (1)
**jittered, exponential reconnect backoff on the client** — randomize the
first retry over a wide window so the herd spreads; (2) a
**reconnect-rate limiter / admission control at the gateway tier** that
sheds-with-`Retry-After` above a threshold so the fleet degrades
gracefully instead of toppling; (3) **capacity headroom** — I size the
fleet so the loss of one node (or one AZ) can be absorbed by the rest,
i.e. N+2 at the zone level. The registry write rate also spikes during a
storm, so the registry has to absorb a burst of re-registrations — I keep
its writes cheap (one key per device, TTL'd) and shard it by `user_id`.

*Per-connection memory is the scaling wall.* At ~10–50KB per connection —
socket buffers, TLS state, per-connection bookkeeping — a million
connections is 10–50GB on one node, and 100M connections is the dominant
cost of the whole system. (The famous existence proof is WhatsApp's
Erlang fleet doing ~2–3M connections/server with ~hundreds of bytes of
*process* overhead per connection — but the TCP/TLS buffers are the real
floor, so 10–50KB is the honest planning number for a non-Erlang stack.)
This number sets the fleet size, drives the decision to keep the gateway
*thin* (no business logic, just connection + routing — control-plane and
data-plane logic live behind it), and is why I'd push back on putting
anything heavyweight in the gateway process.

*Presence and heartbeats.* Each connection sends a heartbeat (ping)
every ~30s; presence is a **TTL'd key in the presence store refreshed by
the heartbeat** (say TTL 45s). This is the classic timeout-tuning
trade-off I'll commit on: too short and a client on a jittery network
flaps online/offline every few seconds (and spams presence fan-out); too
long and a user who actually dropped shows 'online' for a minute. I'd set
TTL ≈ 1.5× the heartbeat interval, accept up to ~45s of stale-online, and
state that presence is **best-effort AP** — I will not pay strong
consistency for 'last seen.' One thing I'll name explicitly: **split-brain
on the connection registry** — if a client reconnects to a new node
before the old node's entry expires, the registry can briefly show *two*
live locations; I resolve it last-writer-wins with a monotonic connection
generation/epoch so the message service routes to the newest and the
stale node's push is a harmless no-op (the message is also in the inbox)."

**What's different at L6:** soft-state-recoverable-by-reconnect stated as
the design principle; the reconnect/thundering-herd storm as *the* failure
mode with a layered damping answer; per-connection memory multiplied out
as the dominator and the reason the gateway stays thin; presence as a
TTL'd heartbeat-refreshed key with the explicit timeout trade-off and an
AP commit; registry split-brain named and resolved with a generation
epoch; graceful drain before deploy as the planned-case mirror of the
crash.

**Anti-signal.** "We'd migrate the connections to another node" (you
can't move a live TCP socket), or "they reconnect, no big deal" with no
awareness of the synchronized wave, or no per-connection-memory math. →
Packet: *"Treated a gateway death as a trivial reconnect; did not
anticipate the synchronized reconnect storm or the cascading-collapse
risk, and never sized per-connection memory."*

**Packet quote (Hire).**
> *"Treated connection state as soft state recoverable by reconnect
> (registry re-registration, never socket migration); on gateway death
> volunteered the synchronized reconnect storm and damped it with
> client-side jittered backoff + a gateway admission/reconnect-rate
> limiter + N+2 zone headroom. Multiplied per-connection memory (10–50KB
> × connections) as the fleet dominator and kept the gateway thin.
> Presence as a TTL'd heartbeat key with the short-vs-long timeout
> trade-off, stated best-effort AP. Named registry split-brain and
> resolved it with a connection generation epoch. Unprompted."*

### Deep dive B — Message delivery semantics & ordering

**Phrasing.** *"A user reports two bugs: they saw the same message twice,
and separately they saw an old 'I'm running late' land *after* a newer
'I'm here.' Walk me through how each happens and how your system makes
each safe. I want the data structures."*

**Strong L5 answer.** "At-least-once delivery, so duplicates are expected
— a gateway can push a message, the device can ack, then the network can
drop the ack so we redeliver; or the device acks then dies before
persisting locally. So the *client* generates a stable message ID (a
client-side UUID) at compose time, sent with the message and constant
across every retry. The receiver (and the server) dedupe on it — a
processed-ID set / UNIQUE constraint — so a duplicate is a no-op. For
ordering, I'd order messages within a conversation by a server-assigned
timestamp or by a per-conversation counter, and the client renders in
that order; a message that arrives out of order gets re-sorted into place
by the client using that key, not by arrival order. The inbox holds
messages for offline recipients and drains them in order on reconnect."
Correct, competent — names at-least-once, client-message-ID dedup, and an
ordering key. What's missing is making the sequence number the
*structural* primitive for gap detection, and the three delivery states.

**Strong L6 answer.** "Two distinct problems, two mechanisms, plus a
third thing the question is hinting at — gap detection.

*Duplicates → idempotency on a client-generated message ID.* The client
mints a UUID (or a `(device_id, client_seq)` pair) at compose time,
stable across every resend. `(conversation_id, client_message_id)` is the
idempotency key. The message service does an idempotent insert (UNIQUE
constraint / conditional write) so a redelivered message is a no-op
server-side, and the receiving device keeps a short-TTL processed-ID set
so a re-pushed message is a no-op client-side. This gives exactly-once
*effect* on top of at-least-once *delivery* — the only honest
exactly-once there is. (This is the same move as the webhook round's
`event_id`-dedup.)

*Ordering → a monotonic per-conversation sequence number.* This is the
structural primitive, and it mirrors the webhook round's monotonic
last-write-wins. When a message is accepted, the message service assigns
it a **per-conversation, gap-free, monotonically increasing `seq`** —
*not* a wall-clock timestamp, because clocks skew across senders and
gateways and two messages 1ms apart on different nodes can invert. The
key is that there's a **single writer per conversation** (I shard the
conversation log so one partition owns `seq` assignment for a given
`conversation_id`), so the counter is monotonic by construction — no
distributed coordination, no clock dependence. Clients render strictly by
`seq`. An 'old' message arriving after a 'new' one carries a *lower* seq,
so the client just inserts it at its correct position — out-of-order
arrival is a *normal, expected* outcome of at-least-once + multi-path
delivery, and it's handled by sorting on seq, not by trusting arrival
order.

*Gap detection → catch-up fetch, never a DLQ.* Because `seq` is gap-free
per conversation, the client can detect loss: if it has seq 41 and the
next push is seq 43, it *knows* 42 is missing and issues a **catch-up
fetch** (`GET messages?conversation=X&after=41`) to pull the gap from the
durable log. This is how the system degrades gracefully — a dropped or
reordered message isn't an error to dead-letter, it's a gap to fill. The
durable per-conversation log (Cassandra-shaped, partitioned by
`conversation_id`, clustered by `seq`) is the source of truth; the live
push is an *optimization* on top of a pull-able log, exactly like the
webhook reconciliation lesson — the push path is best-effort, the log is
correct.

*The three delivery states — name them, because read receipts depend on
it.* `sent` (server accepted + assigned seq + persisted) → first tick;
`delivered` (the recipient's *device* acked receipt) → second tick;
`read` (the recipient opened the conversation) → blue tick. These are
three separate acks flowing back, and `delivered` vs `read` is a
*per-device* fact in a multi-device world (deep dive C). Receipts
themselves are low-priority metadata — they ride the out-of-band path
(deep dive C), so a flood of read receipts can't head-of-line-block
actual messages.

So: duplicate → idempotent no-op; out-of-order → sort by seq; gap →
catch-up fetch; offline → inbox drain by seq cursor on reconnect. One
honest guarantee — at-least-once delivery, exactly-once effect,
per-conversation ordering — and I'll state the CAP commit: messages are
**AP with per-conversation ordering**, *not* a global total order across
conversations, because nobody needs the message in chat-A ordered against
the message in chat-B."

**What's different at L6:** separates dedup (client message ID) from
ordering (per-conversation seq) as two mechanisms; makes seq the
structural gap-detection primitive with the single-writer justification
for monotonicity (and explicitly rejects wall-clock); gap → catch-up
fetch from a pull-able log, never DLQ; names the three delivery states
and that delivered/read are per-device; states the AP +
per-conversation-ordering (not global) CAP commit out loud.

**Anti-signal.** "Exactly-once delivery, we ack end to end." Or ordering
by wall-clock with no single-writer / no gap detection. Or routing a
reordered message to a dead-letter queue as if it were a failure. →
Packet: *"Claimed exactly-once delivery; ordered by wall-clock with no
gap-detection mechanism; treated a reordered message as an error."*

**Packet quote (Strong Hire).**
> *"Separated dedup (client-generated message ID, idempotent insert) from
> ordering (monotonic per-conversation sequence number, single-writer
> per conversation so it's gap-free and clock-free). Used the gap in seq
> to trigger a catch-up fetch from the durable per-conversation log —
> 'the live push is an optimization on a pull-able log; a gap is filled,
> never dead-lettered.' Named the three delivery states (sent/delivered/
> read) and that delivered+read are per-device. Committed to AP with
> per-conversation (not global) ordering. Unprompted."*

### Deep dive C — Fan-out (1:1 vs small group vs megachannel)

**Phrasing.** *"A DM is one recipient. A family group is twelve. A Slack
announcement channel is 100,000 members and someone just posts to it.
Walk me through your fan-out for each, and what specifically breaks if
you treat the 100k channel the same as the DM."*

**Strong L5 answer.** "For 1:1 and small groups, fan-out-on-write: when a
message is accepted, the message service looks up the recipients, and for
each one writes a copy into that recipient's inbox and — if they're online
(connection registry says which gateway) — pushes it down their socket
via that gateway. Twelve recipients, twelve inbox writes + up-to-twelve
pushes; fine. For a 100k-member channel, fan-out-on-write means one post
becomes 100k inbox writes and up to 100k pushes — that's a huge write
amplification and a latency spike, and a burst of posts to a busy channel
multiplies it. So for large channels I'd switch to fan-out-on-read: store
the message once in the channel's log, and members pull it (or get a
lightweight 'new message in channel X' notification and then fetch). I'd
pick a threshold — big channels pull, small ones push." Identifies the
amplification and the right fix, usually after the prompt.

**Strong L6 answer.** "Three regimes, and the design *flips strategy by
conversation size* — this is the news-feed celebrity problem in real-time
clothing.

1. **1:1 and small groups → fan-out-on-write (push).** On accept, assign
   the per-conversation seq, persist once to the conversation log, then
   for each recipient: append a pointer to their inbox and, if the
   registry shows them online, push via their gateway. Each recipient's
   inbox is their merged, per-conversation-ordered view; the push is the
   real-time optimization, the inbox is the durable truth they drain on
   reconnect. At a fan-out of ~5–20 this is cheap and gives the best
   latency.

2. **Large channels → fan-out-on-read (pull).** Above a threshold —
   I'll commit to roughly **1k–10k members** — fan-out-on-write is a
   write-amplification cliff: one post × 100k members = 100k writes, and a
   busy channel at even 10 posts/sec is 1M writes/sec from a *single*
   channel — a textbook hot partition. So large channels store the
   message **once** in the channel log and members **pull**: on
   reconnect/open, a client reads `channel_log after <my_cursor>`. For
   *liveness* without 100k pushes, I fan out a tiny, cheap **invalidation
   /'channel X advanced to seq N'** signal (collapsible, and only to the
   subset *currently viewing* that channel), and they fetch. The heavy
   payload is never copied 100k times.

3. **The hybrid is the answer, and the threshold is the knob.** Small →
   push (latency-optimal, write-cheap at low fan-out); large → pull
   (write-cheap at high fan-out, slightly higher read latency). The flip
   point is where `members × post_rate` write amplification exceeds what a
   single inbox-shard wants to absorb. I'd make it a per-channel attribute
   so a group that *grows* past the threshold gets migrated from push to
   pull (and I'd name that migration as a real operation, not magic).

**Ordering must survive the flip.** In *both* regimes the message gets its
per-conversation `seq` from the single-writer channel partition *before*
fan-out — so push-recipients and pull-recipients converge on the identical
order, and a member who was pushed some messages and pulls others stitches
them by seq with no inversion. The fan-out strategy is a *delivery*
choice; ordering is decided once, upstream, by seq assignment. That's the
property that makes the hybrid safe.

**The megachannel hot partition is the thing to watch.** A single
100k-member channel with a burst of activity is a hot
`conversation_id` partition — both for seq assignment and for the pull
reads. I'd keep the channel log on its own partition(s), cache the tail
of hot channels (the last N messages, read-through), and rate-limit /
collapse the liveness notifications so a 500-msg/sec channel sends *one*
'advanced to seq N' per client per tick, not 500. Blast radius: a hot
megachannel is isolated to its own partition + cache; it doesn't degrade
DMs."

**What's different at L6:** commits a concrete flip threshold (~1k–10k)
with the write-amplification math; the pull path uses a cheap collapsible
liveness signal only to current viewers, not 100k payload copies; ordering
is preserved across the flip *because seq is assigned upstream of fan-out*
(the load-bearing insight); names the push→pull *migration* as a real
operation; treats the megachannel as a hot partition with isolation +
tail cache + notification collapsing.

**Anti-signal.** "Fan-out-on-write for everything, just add inbox shards"
(the amplification cliff), or flips to pull but loses ordering across the
two paths, or pushes the full payload to all 100k as a 'notification.' →
Packet: *"Fanned out on write to a 100k-member channel — one post became
100k writes — and did not arrive at the push→pull flip even when pushed;
or flipped but couldn't preserve ordering across the two delivery paths."*

**Packet quote (Hire L6).**
> *"Three fan-out regimes: 1:1/small-group push (fan-out-on-write into
> per-recipient inboxes), large-channel pull (fan-out-on-read from a
> single channel log + a cheap collapsible liveness signal to current
> viewers only), flipping at ~1k–10k members on write-amplification math.
> Crucially preserved per-conversation ordering across the flip by
> assigning seq upstream of fan-out. Treated the megachannel as a hot
> partition with isolation + tail cache + notification collapsing.
> Connected it to the news-feed celebrity problem. Unprompted."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **No connection registry.** Can't route A→B across gateways without
  broadcasting to the whole fleet (O(fleet) per message). The registry is
  table stakes; missing it is a front-half failure.
- **Exactly-once delivery promise.** One sentence and you know. Push:
  "Across a network to a phone that acks then dies before persisting?"
- **Wall-clock ordering.** Skewed clocks invert messages; the structural
  answer is a per-conversation sequence number from a single writer.
- **No gap detection.** Without a gap-free seq, a dropped message is
  silent data loss; the client must be able to notice 41→43 and fetch 42.
- **No offline/inbox model.** "Push down the socket" loses every message
  to an offline (i.e. most) recipient.
- **Fan-out-on-write for megachannels.** The 100k-write amplification
  cliff; the hybrid flip is the lesson.
- **Ordering lost across the push/pull flip.** Assign seq upstream of
  fan-out or the two paths disagree.
- **Unbounded per-connection send buffer.** A slow consumer on a bad
  network OOMs the gateway; bound the buffer, then drop-to-mailbox or
  disconnect-and-resync.
- **Metadata on the message path.** Typing/read receipts head-of-line-
  blocking real messages; they belong on a separate droppable path.
- **Heavyweight gateway.** Business logic in the connection process
  inflates per-connection memory — the dominator — and couples a
  control-plane blip to established connections.
- **No per-connection-memory math / no cost.** "We'll add servers"
  without multiplying 10–50KB × connections, the actual dominator.

### Interviewer-side (your own traps)

- **Letting them dwell on WebSocket-vs-long-poll as a religious debate.**
  It's a 3-minute commit (WebSocket, long-poll/SSE fallback for hostile
  networks). By minute 30 force the gateway-death and the ordering
  scenarios — that's where the signal is.
- **Leading them to the sequence number or the push→pull flip.** Both are
  the elegant answers, so they're tempting to hand over. Don't. If they
  reach them alone, that's the L6 finding; if you hand it over, the packet
  won't write convincingly.
- **Not driving to the reconnect storm.** It's the L6 separator on the
  connection side. If unprompted by minute 45, push the gateway-death
  scenario explicitly.
- **Over-rewarding "we'll use Redis for the registry."** Redis is not a
  signal. "Redis for the registry because lookups are O(1) and TTL'd, keyed
  per device, sharded by user_id, and we tolerate brief split-brain
  resolved by a connection epoch" *is*.
- **Eating their 3-minute question window.** Still scoring Googleyness.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it.
Numbers explicit, trade-offs committed.

### 6.1 Functional requirements (committed scope)

v1: **establish + maintain** a persistent connection (with reconnect);
**send 1:1** messages; **send group** messages (small groups *and* large
channels up to 100k); **real-time delivery** when the recipient is online
(push) and **offline delivery** via a durable inbox drained on reconnect;
**per-conversation ordering**; **delivery + read receipts** (sent /
delivered / read); **presence + typing indicators**; **multi-device**
(one user, several devices, consistent view).

**Out of scope v1, said out loud:** end-to-end encryption (assume
transport TLS; E2E is a separate crypto design); message search/indexing;
media upload/transcoding (we carry a blob pointer, a separate object
store handles bytes); voice/video calling (that's `12-voice-video-
calling.md` — the signaling overlaps, the media path doesn't); spam/abuse
(a separate platform).

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| Concurrent connections | **100M** (peak) | The defining scale number. Sets the gateway fleet. |
| Per-connection memory | **~10–50KB** (socket + TLS buffers + bookkeeping) | × 100M = **1–5 TB of RAM across the fleet** — the dominator and the scaling wall. |
| Messages/sec (peak) | **~1M sent/sec** | Drives the message-service + log write rate. |
| Fan-out (delivery tasks/sec) | **~5M/sec** typical; bursts far higher | Avg group ~5–20; a megachannel post is the tail. |
| Delivery p99 (online → device) | **≤ 300ms** | Real-time feel; it's a chat, latency is felt. |
| Presence update rate | **~3M/sec** (heartbeats) | Heartbeat every ~30s × 100M = ~3.3M/sec. Best-effort. |
| Inbox storage / user | **~tens of MB** hot (recent + undelivered); cold archived | Pointers + recent messages; not full history hot. |
| Max channel size before push→pull flips | **~1k–10k members** | Above this, fan-out-on-write amplification cliffs. |
| Availability — connect/deliver | **99.99%** | If chat is down, the product is down. |
| Durability | Messages **durable** (persisted before ack); **connection state is soft** (reconnect recovers) | Losing a message is a bug; losing a connection is a reconnect. |

### 6.3 Capacity estimation (worked)

- **Gateway fleet (the dominator).** 100M connections × ~10–50KB =
  **1–5 TB RAM** just for connection state. At, say, ~1M connections per
  node (an aggressive, Erlang-class number; 200–500k is more typical for
  a JVM/Go stack), that's **100–500 gateway nodes**, plus N+2 zone
  headroom so one node/AZ loss is absorbable. *This number drives keeping
  the gateway thin* — every KB of per-connection bookkeeping is multiplied
  by 100M.
- **Message write rate.** 1M msg/sec × ~1KB = **~1 GB/sec** into the
  durable per-conversation log; ~86 TB/day raw before TTL/compaction.
  Cassandra-shaped (partition by `conversation_id`, cluster by `seq`),
  not a single-primary SQL box, and *not* Spanner (Paxos-per-message at
  1M/sec is unjustified for a log that needs per-conversation, not global,
  consistency).
- **Fan-out amplification.** 1M msg/sec × avg fan-out → ~5M delivery
  tasks/sec for the push path; the megachannel tail is bounded *because*
  large channels pull instead of multiplying writes.
- **Registry.** 100M devices × one small entry, TTL'd, sharded by
  `user_id`. Read on every routed message (cacheable), written on
  connect/reconnect — spikes during a reconnect storm, so writes are kept
  to one cheap key per device.
- **Presence.** ~3.3M heartbeats/sec into a TTL'd store; pure soft state,
  sized for write throughput not durability.

**Numbers that changed a design choice:**
- 10–50KB × 100M = 1–5 TB → gateway must be *thin*; control/data-plane
  split; per-connection memory is the cost model.
- 1M msg/sec → log store is Cassandra-shaped, partitioned by conversation,
  not Spanner; ordering is per-conversation, not global.
- ~1k–10k channel size → the push→pull fan-out flip.
- Reconnect of 1M clients at once → jittered backoff + gateway admission
  control + N+2 headroom.

### 6.4 API design

```
# Connection (data plane, over a persistent WebSocket; long-poll/SSE fallback)
WS    /v1/connect            Authorization: Bearer <token>, Device-Id
                             → server registers (user,device)->node in registry;
                               heartbeat ping/pong every ~30s (presence TTL refresh)

# Over the open socket (framed messages):
→ SEND   { client_message_id, conversation_id, body, ts_client }
← ACK    { client_message_id, conversation_id, seq }      # server assigned seq
← PUSH   { conversation_id, seq, sender, body, sent_at }  # an inbound message
→ RECEIPT{ conversation_id, seq, state: delivered|read, device_id }
← META   { conversation_id, typing|presence|read }        # out-of-band, droppable

# Catch-up / offline drain (data plane, plain HTTPS — works without a socket)
GET   /v1/conversations/{cid}/messages?after_seq=<n>&limit=50   # gap fill + drain
GET   /v1/inbox?after_cursor=<c>                                # cross-conversation drain

# Control plane (separate path; a blip here must NOT drop live connections)
POST  /v1/conversations              { type: dm|group|channel, members[] }
POST  /v1/conversations/{cid}/members
GET   /v1/conversations/{cid}/members
GET   /v1/users/{uid}/devices
```

`SEND`→`ACK` carries the server-assigned `seq`; `after_seq` powers both
gap-fill and offline drain. The control plane (conversation/membership
CRUD) is a *separate service and path* from the data plane (connect +
deliver) so a control-plane outage degrades the ability to *create*
channels, not the ability to deliver on existing connections.

### 6.5 Data model

```
# Durable, write-optimized (Cassandra-shaped)
message:        (conversation_id PK, seq CLUSTER) -> client_message_id,
                sender_id, body_or_blobref, sent_at        # the source-of-truth log
conversation:   conversation_id PK -> type(dm|group|channel), member_count,
                fanout_mode(push|pull), created_at          # mode flips at threshold
seq_counter:    conversation_id -> next_seq                 # single-writer per conv
inbox:          (user_id, device_id, cursor_seq) -> pointer-list   # per-device drain cursor
receipt:        (conversation_id, seq, device_id) -> delivered_at, read_at

# Soft state (Redis-shaped, TTL'd)
connection_reg: (user_id, device_id) -> {gateway_node, conn_epoch}  TTL ~60s
                user_id -> {device_id...}                  # fan-out finds devices in one read
presence:       user_id -> {state, last_seen}  TTL ~45s    # refreshed by heartbeat
```

**Why this split:** the message log and receipts are durable truth (losing
a message is a bug). The connection registry and presence are *soft state*
— a node loss just means reconnect and re-register, so they're optimized
for cheap O(1) TTL'd writes, not durability. **Per-device** inbox cursor +
receipts are what make multi-device work: each device drains independently
and has its own delivered/read state.

### 6.6 High-level architecture

```
        ┌───────────────────────────────────────────────────────────┐
        │  Clients (phone / desktop / web) — 100M persistent conns    │
        │  WebSocket (long-poll / SSE fallback on hostile networks)   │
        │  client mints client_message_id; jittered reconnect backoff │
        └───────────────┬───────────────────────────────────────────┘
                        │  persistent connection
              ┌─────────▼───────────┐   ◄── DATA PLANE
              │  WebSocket Gateway   │   thin: connection + routing only
              │  Tier (100–500 nodes)│   ~10–50KB/conn → 1–5 TB RAM (DOMINATOR)
              │  ├ holds the socket  │   heartbeat → presence TTL refresh
              │  ├ on connect: register (user,device)->node, conn_epoch
              │  └ bounded send buf  │   slow consumer → drop-to-inbox / disconnect
              └───┬──────────────┬───┘
   register/route │              │ inbound SEND
      ┌───────────▼──┐    ┌──────▼─────────────────┐
      │ Connection   │    │   Message Service       │
      │ Registry     │◄───┤  ├ assign per-conv seq  │ (single writer / conv partition)
      │ (Redis, TTL, │    │  ├ persist to log       │
      │  sharded by  │    │  ├ fan-out decision ────┼──► push (small) | pull (large)
      │  user_id)    │    │  └ enqueue deliveries   │
      └──────────────┘    └───┬───────────┬─────────┘
      ┌──────────────┐        │           │
      │ Presence     │        │ push       │ large-channel: store once,
      │ Store (TTL)  │        │ (lookup    │ send cheap "advanced to seq N"
      │ best-effort  │        │  recipient │ to current viewers; they GET
      └──────────────┘        │  gateways) │
                              ▼           ▼
                     ┌───────────────┐  ┌──────────────────────┐
                     │  Inbox (per   │  │  Message Log (durable,│
                     │  user/device, │  │  Cassandra-shaped,    │
                     │  drain cursor)│  │  PK conversation_id,  │
                     └───────────────┘  │  CLUSTER seq)         │◄─ catch-up / drain
                                        └──────────────────────┘   (GET after_seq)

        ┌──────────────────────────────────────────────────┐
        │  CONTROL PLANE (separate service + path)           │
        │  conversation/membership CRUD, fanout-mode flips   │
        │  a blip here must NOT drop established connections  │
        └──────────────────────────────────────────────────┘

   out-of-band METADATA path (typing, presence, receipts): low priority,
   droppable, never head-of-line-blocks the message stream above.
```

The design's whole point: **the gateway is thin and stateful-but-soft**,
**ordering is decided once by per-conversation seq upstream of fan-out**,
**delivery is at-least-once over a pull-able durable log**, and **fan-out
flips push→pull by channel size**.

### 6.7 Connection management (see deep dive A)

- **Gateway tier** holds the persistent connections; thin (connection +
  routing only), because per-connection memory × 100M is the dominator.
- **Connection registry** (`(user,device) → node, conn_epoch`, TTL'd,
  sharded by `user_id`) routes a message to the right gateway in one
  lookup; a per-user device set lets fan-out find all devices at once.
- **Connection state is soft** — never migrate a live socket; reconnect
  re-registers and re-syncs from the inbox cursor. Planned deploys
  **drain** with a jittered `GOAWAY`; crashes are drain without warning.
- **Reconnect storm** damped by client jittered backoff + gateway
  reconnect-rate admission control + N+2 zone headroom.
- **Presence** = TTL'd key refreshed by the ~30s heartbeat (TTL ~45s ≈
  1.5× interval); best-effort AP; **split-brain** on the registry resolved
  by `conn_epoch` last-writer-wins.

### 6.8 Delivery semantics & ordering (see deep dive B)

- **At-least-once delivery, exactly-once effect**: client-generated
  `client_message_id`; idempotent insert + per-device dedup set.
- **Per-conversation monotonic `seq`** assigned by the single-writer
  conversation partition — clock-free, gap-free, the ordering primitive.
- **Gap detection** (41→43) → **catch-up fetch** from the durable log;
  never a DLQ — the live push is an optimization on a pull-able log.
- **Three delivery states**: sent / delivered / read; delivered+read are
  **per-device**.
- **CAP commit**: messages are **AP with per-conversation ordering**, not
  a global total order.

### 6.9 Fan-out (see deep dive C)

- **1:1 + small groups → fan-out-on-write (push)** into per-recipient
  inboxes + live push via the registry.
- **Large channels (≳1k–10k) → fan-out-on-read (pull)**: store once,
  members pull; a cheap **collapsible "advanced to seq N"** signal goes
  only to *current viewers*, not 100k payload copies.
- **Ordering survives the flip** because `seq` is assigned upstream of
  fan-out; a growing group **migrates** push→pull as a real operation.
- **Megachannel = hot partition**: isolate, tail-cache, collapse liveness
  signals; blast radius doesn't reach DMs.

### 6.10 Backpressure & out-of-band metadata

- **Bounded per-connection send buffer.** A device on 2G can't drain its
  socket; the buffer is capped. On overflow, policy: messages are already
  durable in the inbox, so we **drop the live push and let the device
  resync from its cursor on reconnect** (or disconnect-and-resync if it's
  truly stuck) — we never grow the buffer unbounded and OOM the gateway.
  This is the slow-consumer / backpressure discipline.
- **Out-of-band metadata path.** Typing indicators, presence deltas, and
  read receipts are **low-priority, droppable, and ride a separate logical
  stream** from messages, so a flood of "X is typing" can't head-of-line-
  block real message delivery. A typing indicator dropped under load is a
  non-event; a message dropped is not — different paths, different SLAs.

### 6.11 Multi-region / consistency

CAP commits, said out loud: **messages AP with per-conversation ordering;
presence best-effort AP; conversation/membership control plane
CP-leaning.**

- **Home-region inbox.** Each user's inbox + their conversations' logs
  have a **home region**; reads/writes are region-local for latency. A
  user connects to their nearest gateway, which routes to the home region
  for their conversations.
- **Cross-region delivery.** A message from a user in EU to a user homed
  in US is written to the conversation's home-region log (single writer →
  one seq authority, so **ordering stays correct cross-region**), and the
  recipient's gateway (wherever they are) pushes/pulls from there. The
  **ordering guarantee scope is per-conversation, anchored at the
  conversation's home partition — never a global cross-region total
  order**, which we explicitly don't need.
- **Region failover.** If a region holding a conversation's home log goes
  dark: live sessions there reconnect elsewhere (soft state); the log
  fails over to a replica (async-replicated, so a few seconds of recent
  messages may need re-drive from sender retry / client resend — safe
  because of idempotent `client_message_id`). Presence in that region is
  just rebuilt by heartbeats. We accept brief cross-region staleness; we
  do **not** pay synchronous global consensus per message.

### 6.12 Cost (back-of-envelope, monthly)

Public-cloud pricing as a proxy at the 6.2 numbers:

| Component | Notes | $/mo |
|---|---|---|
| Gateway connection fleet | 100–500 nodes for 1–5 TB conn RAM + N+2 headroom | **~$300–600k** |
| Message log (Cassandra-shaped) | ~1 GB/sec writes, TTL'd, replicated | ~$120k |
| Inbox storage | per-device recent + undelivered, hot tier | ~$80k |
| Connection registry + presence (Redis) | soft state, TTL'd, sharded | ~$40k |
| Fan-out / message-service compute | seq assignment + delivery enqueue | ~$30k |
| **Total** | | **~$570k–870k/mo** |

**Dominator: the gateway connection fleet** (per-connection memory ×
100M) — which is exactly why the gateway is kept thin and why the
push→pull flip matters (it bounds the inbox-write second-largest line).
A megachannel fanned out on write would blow up the inbox storage + write
line; the pull flip is a *cost* lever, not just a latency one.

### 6.13 Failure modes & blast radius

| Failure | Effect | Mitigation / policy |
|---|---|---|
| Gateway node death | ~1M connections drop | Soft state → reconnect re-registers; clients jittered-backoff; blast radius bounded to that node's users for a few seconds |
| Reconnect storm | 1M synchronized reconnects threaten cascade | Client jittered backoff + gateway reconnect-rate admission control (`Retry-After`) + N+2 zone headroom |
| Connection registry inconsistency (split-brain) | Message routed to a stale node | `conn_epoch` last-writer-wins; stale push is a harmless no-op (message also in inbox) |
| Slow consumer (bad network) | Per-conn send buffer fills | Bounded buffer → drop live push, resync from inbox cursor; never unbounded → OOM |
| Megachannel write amplification | One post → 100k writes | Push→pull flip above ~1k–10k; store-once + collapsible liveness signal |
| Region failover | Home-region log/sessions lost | Sessions reconnect (soft); log fails to async replica; idempotent client_message_id covers re-drive; brief staleness accepted |
| Message store hot partition | A busy conversation/channel saturates one partition | Isolate hot `conversation_id`; tail-cache the last N; rate-limit/collapse liveness; ordering still via single seq writer |
| Control-plane outage | Can't create/modify conversations | Data plane unaffected — established connections keep delivering (the split is deliberate) |

**Fail-open vs fail-closed, per path:** *delivery* fails toward
availability (a registry blip or a dropped push degrades to "fetch from
the durable log on reconnect" — messages are never lost because the log
is the truth); the *control plane* (membership changes) fails closed (we
do not deliver to a member we can't confirm is still in the channel). This
split is the L6 commit.

**SLO/error budget.** 99.99% delivery → 4.32 min/mo. Page at 10× burn.
Connection-availability SLO is separate from message-delivery SLO so a
reconnect-storm incident doesn't burn the delivery budget.

### 6.14 Evolution at 10× (1B connections, 10M msg/sec)

- **Gateway tier:** unchanged in *shape* — it's thin and horizontally
  scaled; add nodes linearly. The named seam: per-connection memory is the
  wall, so 10× connections = 10× the dominant cost; if that's untenable
  you push more clients onto a more efficient connection model (Erlang-
  class processes, or QUIC with cheaper per-connection state) — that's the
  one seam that's an *architecture* change, not a knob.
- **Connection registry:** more shards; `hash(user_id)` keeps it even;
  reconnect-storm write bursts get bigger, so the admission control limits
  matter more.
- **Message log:** add partitions linearly; partition-by-`conversation_id`
  keeps distribution even; hot megachannels get dedicated partitions.
- **Fan-out:** the push→pull threshold may *lower* as fan-out grows; it's a
  per-channel knob, not a redesign.
- **Cost:** ~linearly to several $M/mo; gateway fleet still dominates,
  which is why the per-connection-memory efficiency is the thing I'd
  invest engineering in first.

**What does *not* change:** the per-conversation seq ordering primitive,
the at-least-once + client-message-ID contract, the push/pull hybrid, the
soft-state-recoverable-by-reconnect principle, the control/data-plane
split, the AP + per-conversation-ordering CAP commit. The seams named at
v1 are the seams at 10×.

### 6.15 What I'd own vs. delegate

I'd personally own the **delivery contract and the per-conversation seq /
ordering semantics** (the security-and-correctness-critical invariant the
whole product depends on) and the **gateway connection model** (because
per-connection memory is the dominant cost and the scaling wall). I'd
delegate the **message log operation** to the team that already runs our
Cassandra-class fleet, the **registry + presence** to the team that runs
the in-memory KV tier, and the **control plane** (conversation/membership
CRUD) to a product-platform team — it's a natural seam because it fails
independently of delivery. The **media path** (blob upload/transcode) is a
clean hand-off to object-store + media-processing teams.

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence. Right is the level
call.

| Evidence | Call |
|---|---|
| No connection registry after prompting; "broadcast to all gateways"; no per-connection-memory math; "we just push, no inbox." | **Strong No Hire** |
| Drew a WebSocket + message table; promised exactly-once delivery; ordered by wall-clock; when pushed on a 100k channel, fanned out on write and didn't reach the flip. | **No Hire** |
| Has a connection registry and a durable inbox; at-least-once + client-message-ID dedup; but ordering left to timestamps with no gap detection, and the gateway-death answer was "they reconnect, no big deal" with no storm awareness. Saw pieces, not the system. | **Lean No Hire** |
| Committed to 100M connections, per-connection memory, ~1M msg/sec, delivery p99 by minute 10. Thin gateway + registry + durable inbox unprompted. At-least-once + client-message-ID dedup; recognized the megachannel needs push→pull when prompted. Handled offline via inbox drain. Didn't reach the per-conversation seq / gap-detection or the reconnect-storm damping even when prompted. | **Hire L5** |
| All of L5-Hire, **plus**: arrived at a per-conversation ordering mechanism (sequence/version, not wall-clock) when prompted; named the reconnect storm and a damping idea when pushed on gateway death; stated an AP-with-per-conversation-ordering commit; per-device delivered/read; some cost reasoning. | **Hire L5 / Lean L6** |
| All of the above **unprompted**, **plus**: treated connection state as soft state recoverable by reconnect and volunteered the reconnect/thundering-herd storm with layered damping (client jittered backoff + gateway admission control + N+2 headroom) before being asked. Proposed the **monotonic per-conversation sequence number** (single-writer, clock-free, gap-free) as the structural ordering primitive and used the gap to trigger a **catch-up fetch, never a DLQ**. Named the three delivery states and per-device receipts. Volunteered the **push→pull fan-out flip** at a committed threshold and preserved ordering across it by assigning seq upstream of fan-out. Multiplied per-connection memory as the dominator. Surfaced $/mo with the gateway fleet as dominator. CAP commit stated. | **Hire L6** |
| Everything in L6, **plus**: named **registry split-brain** and resolved it with a connection epoch; volunteered **backpressure** (bounded send buffer → drop-to-inbox) and the **out-of-band metadata path** (typing/receipts can't head-of-line-block messages); named the **control-plane/data-plane split** and that a control-plane blip must not drop live connections; defended Cassandra-not-Spanner for the log with a Paxos-per-message-at-1M/sec cost argument; anchored cross-region ordering at the conversation's home partition while explicitly refusing a global total order; named what they'd own (delivery contract + seq semantics + connection model) vs. delegate (log ops, registry/presence, control plane); closed with a self-aware retro. | **Strong Hire L6** |

---

## Sources used in preparing this guide

- Hello Interview / System Design Sandbox — *Design WhatsApp* (stateful
  WebSocket gateway vs. stateless chat service, connection/session
  registry mapping device→gateway in Redis, per-user device set for
  fan-out, persist-to-Cassandra-first then catch-up on reconnect):
  systemdesignsandbox.com/learn/design-whatsapp
- Alex Xu — *System Design Interview Vol. 2*, "Design a Chat System"
  (WebSocket connection handling, message sync via per-recipient inbox,
  message ID + sequence for ordering, online/offline presence with
  heartbeat, group-chat fan-out): bytebytego / the book's chat chapter.
- DesignGurus — *Design WhatsApp* (gateway connection management, message
  store, group fan-out, read receipts / delivery states):
  designgurus.io/course-play/system-design-interview-crash-course/doc/design-whatsapp
- RFC 6455 — *The WebSocket Protocol* (the persistent full-duplex
  connection, ping/pong heartbeat frames, close handshake — the transport
  the gateway tier maintains): rfc-editor.org/rfc/rfc6455
- High Scalability — *How WhatsApp Grew to ~500M Users, 11,000 cores, 70M
  messages/sec* and the *3M-connections-per-server* analyses (Erlang
  one-process-per-connection model, per-connection memory as the scaling
  variable — the existence proof for the thin-gateway argument):
  highscalability.com/how-whatsapp-grew-to-nearly-500-million-users-11000-cores-an/
- ByteByteGo — *How WhatsApp Handles 40 Billion Messages Per Day* (write
  path, message store sizing, fan-out at scale):
  blog.bytebytego.com/p/how-whatsapp-handles-40-billion-messages
- GetStream — *How WhatsApp Works: Architecture Deep Dive* (connection
  layer, delivery receipts, multi-device sync): getstream.io/blog/whatsapp-works/
- Onsites.fyi — *Google L6 interview questions* (the canonical prompt
  *"design a global messaging platform with multi-device delivery and read
  receipts"*): onsites.fyi/blog/article/google-L6-software-engineer-interview-questions

---

*End of guide. Related:* `12-voice-video-calling.md` *(the
signaling/long-lived-connection management overlaps directly — the
registry, presence, and graceful-drain patterns recur, though the media
data plane does not) and* `08-webhook-delivery.md` *(at-least-once +
idempotency + the monotonic-stamp ordering primitive and "a gap/stale
event degrades gracefully, never to a DLQ" all rhyme with the delivery
semantics here).*
