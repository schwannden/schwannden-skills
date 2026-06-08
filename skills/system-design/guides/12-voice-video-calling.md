# Question 12: Real-Time Voice/Video Calling System (WebRTC media transport, e.g. Zoom / Google Meet / WhatsApp calling)

> Interviewer's guide for the 1-hour Google L5/L6 system-design round.
> Anchor problem for the **real-time media transport / signaling-vs-
> media-plane** archetype. The prompt is canonical (every video product,
> WebRTC's own RFC suite, the SFU-vs-MCU debate every infra team has had).
> The calibration value is *not* whether the candidate knows what WebRTC
> is — it's whether they can hold a hard latency budget in their head for
> an hour against a lossy, NAT'd, congested network. The central tension:
> **you cannot have low latency, high quality, AND low server cost at the
> same time — the topology choice (P2P mesh vs SFU vs MCU) is where you
> commit and defend, and the latency budget is what disqualifies the easy
> answers.** Sub-150ms one-way is the bar; everything in the design either
> spends or protects that budget.

---

## 1. Why this question (interviewer's framing)

A calling system *looks* like "open a WebSocket and stream some packets."
A prepared L4 will say "WebRTC, peer-to-peer, done" and stop. That answer
is *correct for a 1:1 call and catastrophically wrong for a 50-person
meeting* — and the whole question is about that gap. The real prompt is:
**you are the media transport for a product with millions of concurrent
calls; the budget from one person's mouth to another's ear is ~150ms and
the network underneath you drops 1–3% of packets and reorders the rest.
What topology do you commit to, how do you spend the latency budget hop by
hop, and what happens when a server carrying ten thousand live calls
dies?**

That forces explicit reasoning on five axes:

- **Latency vs quality vs server cost — pick two.** P2P mesh has the
  lowest latency and zero media-server cost but dies past ~4 participants
  (O(n²) uplinks). An MCU mixes everything server-side so clients are
  cheap, but it adds a decode-mix-encode hop on the *hot path* (latency)
  and burns a CPU core per call (cost). An SFU forwards without mixing —
  the modern default — but pays egress fan-out bandwidth. There is no
  free corner; the L6 names which corner they give up and why.
- **Control plane vs data plane.** Signaling (who's calling whom, SDP,
  ICE candidates) is the control plane and rides a WebSocket. Media is the
  data plane and rides SRTP/UDP. **They fail independently** — a signaling
  outage must not drop calls in progress. Candidates who conflate the two
  miss the single most load-bearing idea on the page.
- **Connection establishment through hostile networks.** Both endpoints
  are usually behind NAT. STUN discovers your reflexive address; ICE
  races candidate pairs; TURN relays the ~10–20% of sessions where direct
  P2P is impossible. "Just connect the two peers" ignores that the
  internet won't let you.
- **Degradation under loss, not failure.** The interesting failure mode
  isn't a node dying — it's 2% packet loss and 40ms of jitter on a real
  network. Jitter buffers, NACK/RTX, FEC, PLC, and congestion-controlled
  adaptive bitrate are how you keep a call usable, and each one *spends or
  protects* the latency budget.
- **Sticky, long-lived, stateful sessions.** A call is a 45-minute stateful
  thing pinned to one SFU node. Where does that state live, how do you
  route to the right node, and what's the blast radius when it dies?

### What "Hire" looks like at each level

**L5 Hire.** Commits to numbers by minute 10 (concurrent calls,
participants/call, the ≤150ms one-way budget, packet-loss tolerance,
per-stream bitrate). Splits **signaling (control plane, WebSocket) from
media (data plane, SRTP/UDP)** explicitly. Walks ICE end to end —
SDP offer/answer, STUN for reflexive addresses, TURN as the relay
fallback — and knows roughly what fraction needs TURN. **Picks SFU over
mesh and MCU and defends it numerically** (mesh's O(n²) uplinks, MCU's
per-call CPU). Names a jitter buffer and at least one loss-recovery
mechanism. Handles "what happens when the media server dies" without
freezing.

**L6 Hire.** All of the above, plus: **drives the room** (narrates the
budget, pre-ranks deep dives off the NFRs). **Allocates the mouth-to-ear
budget hop by hop** — capture, encode, network, jitter buffer, decode,
render — and shows which design choices spend it (MCU mixing, deep jitter
buffer) vs protect it (edge SFUs, short adaptive buffer), unprompted.
States the **CAP-shaped commitment for media**: media is best-effort/AP —
you'd rather conceal a lost packet (PLC) or drop a frame than block the
stream waiting for a retransmit, because a late packet is a useless
packet. Volunteers **simulcast/SVC layer selection per receiver** as the
SFU's actual job. Names **congestion control (GCC / transport-cc / REMB)**
and adaptive bitrate as the thing that keeps the call from collapsing.
Proactively addresses **SFU node death + sticky routing + ICE-restart
reconnection**, **TURN relay cost as a bandwidth dominator**, and the
**cascaded-SFU pattern** for cross-region calls. Surfaces $/month and
names the dominator (egress bandwidth). States what they'd own vs delegate.

### Classic downlevel traps

1. **"WebRTC is peer-to-peer, so it scales."** The modal L4 answer. When
   pushed — "now it's a 50-person all-hands" — they either keep the mesh
   (each client uploads 49 streams; their uplink and CPU melt) or invent a
   server on the spot with no topology reasoning. Either way the packet
   writes itself: *did not see that mesh is O(n²) and breaks past ~4.*
2. **Conflating signaling and media.** Routing media through the WebSocket,
   or claiming "if signaling goes down the call drops." A candidate who
   can't separate the control plane from the data plane has missed the
   architecture. The corollary trap: putting the SFU *behind* the signaling
   server on the hot path.
3. **Reliable transport for media (TCP / "just retransmit everything").**
   Using TCP or insisting every lost packet be retransmitted. A 200ms-late
   audio packet is worse than a concealed one — head-of-line blocking
   destroys a real-time stream. The fix is UDP + selective recovery
   (NACK/RTX only when there's budget, FEC, PLC), not reliability.
4. **MCU by default.** "Server mixes all the streams into one" — sounds
   efficient (clients get one stream) but adds a decode/mix/encode hop on
   the latency-critical path and costs a CPU core per call. Defensible only
   for specific cases (PSTN bridging, very-low-power clients, recording);
   wrong as the modern default.
5. **No TURN / "ICE will figure it out."** Ignoring that ~10–20% of
   sessions can't traverse NAT and need a relay — which is also where the
   bandwidth cost and a real SPOF live. Or never mentioning NAT at all.
6. **No degradation story.** Designs for the perfect network. When told
   "3% loss, 40ms jitter," has no jitter buffer, no FEC, no adaptive
   bitrate — just "the call gets bad." At L6 this is table stakes.

---

## 2. The 60-minute plan

Minute-by-minute. What you say, what you listen for, when you push back vs.
stay quiet.

### 0–5 min — Intro

**Say:** *"I'm <name>, L7 on <unrelated infra team>. 60-second bio, then:
design a real-time voice/video calling system — think Zoom, Google Meet,
WhatsApp calling. People join a call and see/hear each other live. Start
1:1 if you like, but I'll grow it. Drive it however you want; I'll
interject."*

**Listen for:** do they restate and scope ("are we doing 1:1, small group,
or webinar-scale broadcast? those are different systems") or immediately
draw two phones with an arrow between them? Restating and naming that the
topology depends on participant count is an L6 tell.
**Push back when:** they whiteboard before scoping. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** almost nothing. If asked "scale?" → *"Product scale — millions of
concurrent calls. You tell me participants per call and what that forces."*
If asked "audio only or video?" → *"Both. Tell me how they differ in your
budget."* If asked "latency target?" → *"What would you commit to, and what
does that number disqualify?"*

**Listen for:**
- Tight functional commit: 1:1 + group calls, join/leave, mute, active-
  speaker, screen-share, network-adaptive quality. Bonus for explicitly
  cutting recording, transcription, and the application chat (separate
  systems — name them as out of scope or as a side channel, deep dive C).
- NFRs **with numbers**: concurrent calls, participants/call (and that the
  topology *changes* with this number), **mouth-to-ear one-way ≤150ms good
  / ≤300ms tolerable round-trip**, acceptable packet loss (~1–3% with
  recovery), jitter target, per-stream bitrate (audio ~40kbps Opus, video
  0.5–2.5Mbps per simulcast layer), call setup time.

**Push back when:**
- "Low latency" with no number → *"Quantify. One-way mouth-to-ear in ms?
  What's the ITU bar?"*
- No topology-vs-scale link → *"1:1 and 50-person — same architecture?"*
- Conflates the media transport with the chat/recording features →
  *"Those ride different transports. What's the core media path?"*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip math, *"Before we draw — what does the
math say the server has to push?"*

**Listen for:**
- Worked numbers: per-call uplink/downlink, SFU egress fan-out (N
  participants → SFU forwards ~N×(N−1) streams worst case, less with
  simulcast layer selection), cores per N participants, TURN relay
  fraction (~10–20%) and its bandwidth.
- **The number that decides the architecture:** mesh uplink scales O(n²)
  per client → a 5th participant on residential uplink is already painful
  → that's *why* you move to a server (SFU) at ~4–5, and *why* MCU's
  per-call CPU is too expensive at millions of calls.
- Box diagram with the **control/data plane split drawn explicitly**:
  signaling (WebSocket) + STUN/TURN + SFU media plane, signaling *not* on
  the media hot path.

**Push back when:**
- 9 boxes with media flowing through the signaling server → *"Is media on
  the WebSocket? Why is the signaling server on the media hot path?"*
- Reflexive "one big SFU" → *"Where is it relative to the users? What's the
  RTT from Sydney to your us-east SFU, and how much of your 150ms is gone?"*

### 25–45 min — Deep dives (the diagnostic zone)

Three **mandatory** dives (this question carries three, all load-bearing):

1. **Signaling + connection establishment.** Ask: *"Two users, both behind
   home NAT. Walk me from 'tap call' to first audio packet. SDP, ICE, STUN,
   TURN — and what's the WebSocket doing?"* The control/data-plane split
   should fall out here. If TURN never appears, that's a finding.
2. **Media topology at scale.** Ask: *"It's 1:1. Now it's 5 people. Now
   50. Walk me through what changes each time. Mesh, SFU, MCU — pick and
   defend with numbers."* SFU-as-default with simulcast layer selection
   should appear. MCU-by-default is a down-level.
3. **Latency budget + degradation under loss.** Ask: *"Allocate your 150ms
   mouth-to-ear, hop by hop. Now the network drops 3% of packets with 40ms
   jitter. Keep the call usable — what do you do, and what does it cost the
   budget?"* Jitter buffer (adaptive), NACK/RTX vs FEC vs PLC, and
   congestion-controlled adaptive bitrate should all appear.

**Listen for at L6:** the AP-for-media commit (conceal, don't block); edge
SFUs to protect the budget; simulcast/SVC per-receiver selection; adaptive
jitter buffer naming the latency-vs-smoothness trade-off; GCC/transport-cc;
SFU-death blast radius + ICE-restart.

**Push back hard** on TCP/reliable media (*"a 200ms-late packet — useful or
useless?"*), on mesh-at-50 (*"each client's uplink is now how many
streams?"*), on MCU-by-default (*"what's the CPU per call, and what did you
just add to the hot path?"*), on no-TURN (*"both behind symmetric NAT, P2P
fails — now what?"*).

### 45–55 min — Evolution / curveball

Pick **one** (the first two are the strongest):

- *"The SFU node carrying 10,000 live calls crashes. Walk me through what
  happens to those calls, minute by minute, and how they recover."* (Sticky
  routing, blast radius, ICE-restart/reconnect, graceful drain on deploy.)
- *"A carrier wants to bridge PSTN phone numbers into your calls — someone
  dials in from a landline. How does a SIP/RTP call from the telephone
  network get into your WebRTC/SFU world?"* (SIP gateway / media bridge;
  this is the AI-voice-agent / contact-center hook.)
- *"You need live captions: a transcription service emits text events on a
  different connection with its own clock. Align them with the media so the
  caption lands on the right word."* (Stream ↔ out-of-band metadata
  correlation via RTP timestamps + RTCP sender reports — deep dive C; most
  candidates miss this.)
- *"Half your users are in APAC, your SFUs are in us-east. Fix the latency."*
  (Edge SFUs + cascaded-SFU cross-region pattern.)

**Listen for:** seam identification, not redesign. L6 names the 2–3 knobs
and the migration path.

### 55–60 min — Wrap

**Say:** *"That's time. What would you do differently with 15 more minutes?
Then — questions for me?"*

**Still scoring:** self-aware retro ("I didn't get to bandwidth-estimation
ramp-up behavior or the recording pipeline") and what they ask.

---

## 3. Probing prompts (the kit)

Pre-loaded, with the signal each hunts. Drop verbatim; use silence after.

| Prompt | Signal hunted |
|---|---|
| *"One-way mouth-to-ear budget — commit a number. What's the ITU bar?"* | Latency grounding. ≤150ms good (G.114), ≤400ms unacceptable. Load-bearing. |
| *"1:1, 5-person, 50-person — same architecture? Where does it change?"* | Topology-vs-scale link. Mesh→SFU transition at ~4–5 is the tell. |
| *"Both peers behind home NAT. How does the first media packet get there?"* | ICE/STUN/TURN. Does NAT traversal exist in their mental model at all? |
| *"What fraction of sessions can't do direct P2P and need a relay?"* | ~10–20% need TURN. Knows the relay is real, not theoretical. |
| *"Is media on the WebSocket? What's the WebSocket actually for?"* | Control/data plane split. Signaling ≠ media transport. |
| *"Signaling server has an outage. What happens to calls in progress?"* | Planes fail independently — live calls survive (media is direct/SFU). |
| *"Mesh at 50 people — each client's uplink carries how many streams?"* | O(n²): 49 encodes + 49 uplinks per client. Sees why mesh breaks. |
| *"Why SFU over MCU? What did MCU just add to your hot path?"* | SFU forwards (no mix); MCU adds decode-mix-encode latency + CPU/call. |
| *"50 people, your laptop is on cellular. How does the SFU not flood you?"* | Simulcast/SVC: SFU selects a lower layer per receiver. |
| *"Allocate your 150ms hop by hop — capture to render."* | Budget discipline. Names the spenders (jitter buffer, mixing). |
| *"3% loss, 40ms jitter. Keep audio usable — what runs?"* | Adaptive jitter buffer + NACK/RTX + FEC/RED + PLC, chosen by budget. |
| *"A 200ms-late retransmitted packet — useful or useless? So what?"* | Media is AP: conceal/drop, never block. Why TCP is wrong here. |
| *"Network drops from 2Mbps to 400kbps mid-call. What detects it, what reacts?"* | Congestion control (GCC/transport-cc/REMB) → adaptive bitrate / layer drop. |
| *"SFU with 10k live calls dies. Blast radius? How do calls recover?"* | Sticky routing, blast radius, ICE-restart/reconnect, drain-on-deploy. |
| *"Where does call/session state live, and how do you route to its SFU?"* | Session registry (Redis + TTL), sticky assignment, presence. |
| *"A landline dials in. How does SIP/RTP get into your WebRTC world?"* | SIP gateway / media bridge — telephony ingress, AI-voice / contact-center. |
| *"Cost per month — what's the dominator?"* | Egress bandwidth (SFU fan-out + TURN relay), not compute. L6 marker. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

All three below are **mandatory** for this question. For each: phrasing,
L5 vs L6 shape, anti-signal, packet quote.

### Deep dive A — Signaling + connection establishment

**Phrasing.** *"Two users, both behind home NAT, tap 'call.' Walk me from
that tap to the first media packet arriving. Where do SDP, ICE, STUN, and
TURN come in — and what is the WebSocket actually carrying?"*

**Strong L5 answer.** Names the **control/data-plane split** cleanly. The
WebSocket (or any reliable bidirectional channel through the signaling
server) carries **signaling**: an **SDP offer** from the caller (codecs,
media types, ICE parameters), an **SDP answer** from the callee. Each peer
gathers **ICE candidates**: host (LAN), **server-reflexive** via **STUN**
(the public IP:port the NAT mapped you to), and **relay** via **TURN**.
Candidates are exchanged over signaling (trickle ICE — send them as
discovered, don't wait). ICE then **races candidate pairs** with
connectivity checks and picks the best working one. If direct/reflexive
pairs all fail (symmetric NAT, restrictive firewall), it falls back to a
**TURN relay**. Once a pair is nominated, **DTLS handshake** establishes
keys and media flows over **SRTP**. Names that ~10–20% of sessions need
TURN.

**Strong L6 answer.** All of the above, plus the moves that earn the level:
- States the **plane independence as an invariant**: signaling is the
  control plane (WebSocket to a signaling service); media is the data plane
  (SRTP/UDP, peer-to-peer or via SFU). **They fail independently** — *a
  signaling outage does not drop calls in progress*, because once ICE has a
  nominated pair and DTLS keys, media flows without touching the signaling
  server. Signaling is only needed again for renegotiation (someone joins,
  screen-share starts) or **ICE-restart** (network change).
- Quantifies **call setup**: ICE gathering + connectivity checks + DTLS
  handshake is the cost. The **DTLS handshake is ~1–2 RTTs** and is on the
  setup path, not the steady-state path — so it costs connection time
  (target sub-second to first media), not per-packet latency. SRTP itself
  is cheap (symmetric encryption per packet).
- Names the **session registry**: signaling state (who's in which call,
  which SFU they're assigned to) lives in a shared store — **Redis with a
  TTL** and heartbeats so a dead client's presence expires. Signaling
  servers are stateless and horizontally scaled; the registry is the
  source of truth.
- Distinguishes **STUN (cheap, stateless, just reports your reflexive
  address — runs at huge scale on tiny boxes) from TURN (a bandwidth-
  carrying relay — every media byte flows through it, so it's a cost and
  capacity concern, deep dive on cost).**

**Anti-signal.** Media flows over the WebSocket; or "if signaling is down
the call drops"; or no NAT/STUN/TURN in the model at all ("the two peers
just connect"). → Packet: *"Conflated control and data plane — routed media
through the signaling channel and claimed a signaling outage drops live
calls; no NAT-traversal model."*

**Packet quote (Hire).**
> *"Walked ICE end to end — SDP offer/answer over the WebSocket, host /
> STUN-reflexive / TURN-relay candidates, trickle ICE, connectivity checks,
> DTLS-then-SRTP. Stated the control/data-plane split as an invariant:
> media flows peer/SFU-direct, so a signaling outage leaves calls in
> progress alive. Put session state in Redis with TTL + heartbeats, kept
> signaling servers stateless. Sized TURN at ~15% of sessions. Unprompted."*

### Deep dive B — Media topology at scale (mesh vs SFU vs MCU)

**Phrasing.** *"Start at 1:1. Now make it 5 people. Now 50. Walk me through
what changes each time. Mesh, SFU, MCU — pick one as your default and
defend it with numbers, and tell me exactly when you'd switch."*

**Strong L5 answer.** Names all three and picks SFU:
- **P2P mesh:** every participant sends their stream directly to every
  other. For N people, each client has **N−1 uplinks and N−1 encodes**;
  total streams are **O(n²)**. Great for 1:1 (lowest latency, zero server
  cost). **Breaks past ~4** — a 5th participant means each client uploads
  4× its video on a residential uplink, and encodes 4 streams. Untenable.
- **SFU (Selective Forwarding Unit):** each participant uploads **once** to
  the server; the SFU **forwards** their stream to the others without
  decoding/mixing. Single uplink per client; the server pays the egress
  fan-out. Scales to dozens–hundreds. **The modern default.**
- **MCU (Multipoint Control Unit):** server **decodes all streams, mixes
  them into one composite, re-encodes**, sends each client a single stream.
  Clients are cheap (one decode), but the server burns a **CPU core per
  call** and adds a decode-mix-encode hop. Legacy / special-case.

Picks SFU and explains the uplink win.

**Strong L6 answer.** All of the above, plus the moves that earn the level:
- **SFU's real job is per-receiver layer selection, via simulcast or SVC.**
  Each sender publishes **multiple quality layers** (simulcast: e.g. 3
  independent encodes — 1080p/720p/360p; or SVC: one layered stream). The
  SFU then **forwards a different layer to each receiver** based on that
  receiver's downlink, screen size, and whether they're the active speaker.
  So the laptop on fiber gets 1080p of the speaker and 180p thumbnails of
  everyone else; the phone on cellular gets 360p. This is what makes "50
  people" tractable — *you never send everyone everything.*
- **Egress math, committed.** Worst case an SFU forwards ~N×(N−1) streams,
  but layer selection + only-forward-active-speakers-at-high-res collapses
  it. Names a number: at ~2.5Mbps top layer, a single SFU core handles a
  few hundred forwarded streams; an N-participant call needs roughly
  `participants / streams-per-core` cores. **SFU is bandwidth-bound, not
  CPU-bound** (it forwards, doesn't transcode) — the opposite of MCU.
- **Names exactly when each non-default wins:**
  - **Mesh wins at 1:1 (and maybe 2–3):** lowest latency, no server in the
    media path, no egress cost. Use it.
  - **MCU wins when the client cannot handle N streams or you need one
    composite:** very-low-power/legacy endpoints, **PSTN/SIP bridging**
    (the phone gets one mixed audio stream — deep dive C / curveball),
    **server-side recording/broadcast** (composite to HLS for 100k
    viewers). Accept the CPU-per-call and the mixing latency *for that
    slice only.*
  - **SFU everywhere else.**
- States the **AP-for-media commitment** even here: the SFU forwards
  best-effort and does **not** wait to reassemble — a dropped packet is the
  receiver's problem to conceal (deep dive C).

**Anti-signal.** MCU by default ("server mixes everything") with no
awareness of the per-call CPU or the added hot-path latency; or mesh-at-50
with no O(n²) reasoning; or "SFU" named with no idea what it actually does
differently from an MCU. → Packet: *"Defaulted to MCU mixing without seeing
the per-call CPU cost or the decode-mix-encode latency it adds to the hot
path; could not explain simulcast layer selection."*

**Packet quote (Strong Hire).**
> *"Committed to SFU as default and defended it numerically: mesh is O(n²)
> uplinks and dies at ~4, MCU burns a core per call and adds a mix hop, SFU
> forwards once-up/fan-out-down and is bandwidth-bound not CPU-bound.
> Explained the SFU's real job as per-receiver simulcast/SVC layer
> selection — speaker at high res, thumbnails low — so '50 people' never
> sends everyone everything. Carved out mesh for 1:1 and MCU only for
> PSTN-bridge / low-power / recording. Unprompted."*

### Deep dive C — Latency budget + degradation under loss

**Phrasing.** *"Allocate your 150ms mouth-to-ear budget hop by hop. Now the
network drops 3% of packets with 40ms of jitter. Keep the call usable —
walk me through every mechanism, and tell me what each one costs your
budget."*

**Strong L5 answer.** Allocates the budget roughly:

| Hop | Budget |
|---|---|
| Audio capture + encode (Opus, ~20ms frames) | ~25–30ms |
| Network (one-way, RTT/2) + SFU forward | ~40–60ms |
| **Jitter buffer** (de-jitter before playout) | ~30–50ms |
| Decode + render/playout | ~15–20ms |
| **Total** | **~120–150ms** |

Then names the recovery mechanisms:
- **Jitter buffer** absorbs out-of-order / variable-delay packets so
  playout is smooth; it *trades latency for smoothness.*
- **NACK/RTX:** receiver detects a gap (RTP sequence number), asks for a
  retransmit. Works only if there's time before playout.
- **FEC / RED:** send redundant parity so a lost packet is reconstructed
  without a round trip (costs bandwidth, not latency).
- **PLC (packet-loss concealment):** if the packet is lost *and* there's no
  time to recover, the decoder synthesizes a plausible fill so audio
  doesn't click.
- **Adaptive bitrate:** if loss/congestion is sustained, drop quality.

**Strong L6 answer.** All of the above, plus the moves that earn the level:
- **States the AP-for-media commitment explicitly:** *a late packet is a
  useless packet.* You never use TCP and never block the stream waiting for
  a retransmit — head-of-line blocking would destroy real-time playout. The
  hierarchy is: **recover if there's budget (NACK/RTX), reconstruct without
  a round trip if there isn't (FEC/RED), conceal if you can't (PLC), and
  drop the frame as a last resort.** This is the central trade-off of the
  whole question, named.
- **Adaptive jitter buffer, with the trade-off stated:** the buffer
  **grows under jitter (more latency, fewer concealments) and shrinks when
  the network is clean (less latency).** "You either wait — and spend
  latency — or play out a concealment — and spend quality. The buffer is
  the knob, and we keep it as short as the network allows because we're
  defending the 150ms." Audio buffers stay short (tens of ms); video can
  tolerate a bit more.
- **Picks recovery by media type and budget:** audio gets **FEC/RED** (no
  round trip — protects the budget) + **PLC**; **NACK/RTX is only viable
  when one-way delay is low enough that a retransmit beats playout** (LAN,
  short RTT). Video keyframes get NACK + a **PLI/FIR** to request a fresh
  keyframe after heavy loss.
- **Congestion control closes the loop:** **GCC (Google Congestion
  Control)** estimates available bandwidth from delay-gradient +
  loss, signaled via **transport-cc** feedback (or the older **REMB**). The
  sender then **adapts bitrate** — and with simulcast, the SFU just **drops
  the receiver to a lower layer** rather than asking the sender to slow
  down for everyone. Names that without congestion control you get
  **congestion collapse**: loss → retransmits → more traffic → more loss.
- **Protects the budget architecturally:** **edge SFUs close to users** (so
  network hop is 20–40ms, not a cross-continent 150ms+), and **no MCU
  mixing on the hot path** (that decode-mix-encode hop would blow the
  budget). Ties it back: *sub-300ms round-trip is what makes conversation
  feel natural; every architectural choice either spends or protects it.*

**Anti-signal.** Proposes TCP or "retransmit every lost packet" for media;
or has a jitter buffer but doesn't see it as a latency-vs-smoothness knob;
or "the call just degrades" with no named mechanism. → Packet: *"Treated
media like reliable transport — proposed retransmitting all lost packets,
did not see that a late packet is useless or that head-of-line blocking
breaks real-time; no congestion-control loop, so no congestion-collapse
defense."*

**Packet quote (Hire L6).**
> *"Allocated the 150ms budget hop by hop and named the spenders (jitter
> buffer, any mixing) vs protectors (edge SFU). Stated media as AP — a late
> packet is useless, never block on a retransmit — with the recover/
> reconstruct/conceal/drop hierarchy: NACK/RTX only with budget, FEC/RED
> and PLC for audio. Adaptive jitter buffer framed as the latency-vs-
> smoothness knob. Closed the loop with GCC/transport-cc adaptive bitrate +
> SFU layer-drop, and named congestion collapse as the failure it prevents.
> Unprompted."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **"WebRTC is P2P so it scales."** No topology reasoning; mesh held past
  4. One follow-up ("50 people") and it collapses. Down-level.
- **Media on the WebSocket / planes conflated.** Can't separate control
  from data; thinks a signaling outage drops live calls.
- **Reliable transport for media.** TCP, or "retransmit everything." The
  head-of-line-blocking / late-packet-is-useless miss is fatal at L6.
- **MCU by default.** No awareness of per-call CPU or the mixing hop on the
  latency path. Quotable mistake.
- **No NAT / no TURN.** "The peers just connect." Ignores that ~10–20% of
  the internet won't let you, and that TURN is a cost + SPOF.
- **No degradation story.** Designs for a perfect network; "it gets bad"
  under loss with no jitter buffer / FEC / PLC / adaptive bitrate.
- **No congestion control.** No bandwidth estimation, so no answer to
  "bandwidth drops mid-call" and no congestion-collapse defense.
- **One global SFU.** Cross-continent RTT eats the whole budget; no edge /
  cascaded-SFU story.
- **No cost math.** "We'd use a media server" with no $/month and no idea
  that egress bandwidth (SFU fan-out + TURN relay) is the dominator.
- **Stateless treatment of a stateful call.** No sticky routing, no
  blast-radius answer when an SFU dies, no reconnection/ICE-restart.

### Interviewer-side (your own traps)

- **Letting them dwell on codec trivia.** Opus vs AAC vs VP9 vs AV1 is a
  30-second commit, not the question. By minute 30 force the topology and
  degradation scenarios — that's where the signal is.
- **Leading them to SFU / simulcast.** Tempting because it's the elegant
  answer. Don't. If they reach it alone, that's the L6 finding; handed to
  them, the packet won't write convincingly.
- **Not driving to the loss/degradation scenario.** Mandatory. "Perfect
  network" designs hide the whole skill. If unprompted by minute 40, push.
- **Over-rewarding "we'll use WebRTC."** WebRTC is not a signal. "WebRTC
  because we need sub-150ms over UDP with built-in SRTP, NACK, and
  congestion control, and we'll run our own SFU because the off-the-shelf
  mesh dies at 4" *is*.
- **Eating their 3-minute question window.** Still scoring on Googleyness.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it.
Numbers explicit, trade-offs committed.

### 6.1 Functional requirements (committed scope)

v1: **1:1 calls** and **group calls** (up to ~50 participants on the
interactive path); **join / leave**; **mute audio / disable video**;
**active-speaker detection** (so the SFU prioritizes the speaker's high-res
layer); **screen-share** (a second media track); **network-adaptive
quality** (degrade gracefully under loss/congestion); **device/network
change mid-call** (ICE-restart).

**Out of scope v1, said out loud:** **recording / broadcast to 100k passive
viewers** (that's a separate MCU-composite → HLS/LL-HLS pipeline — name it,
don't build it); **end-to-end encryption beyond SRTP** (SFU forwarding sees
SRTP-decrypted media unless we add insertable streams — flag it);
**transcription / captions** (a side channel — deep dive in 6.9);
**in-call text chat** (rides signaling, trivial); **PSTN bridging** (the
SIP-gateway evolution — 6.10).

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| Mouth-to-ear one-way latency | **≤150ms good, ≤300ms round-trip "natural"** | ITU-T G.114: ≤150ms one-way is transparent; 150–400ms degrades; >400ms unacceptable. This number disqualifies MCU-on-hot-path and one-global-SFU. |
| Concurrent calls | **~1M concurrent calls** (millions of participants) | Product scale. Drives SFU fleet sizing + egress cost. |
| Participants / call (interactive) | **2 → ~50** | **The topology changes with this number**: mesh ≤4, SFU beyond. |
| Acceptable packet loss | **1–3% with recovery, usable to ~10%** | Real networks. Drives FEC/PLC/NACK + adaptive bitrate. |
| Jitter target | **<30ms absorbed** by adaptive buffer | Buffer trades latency for smoothness; kept short to defend the budget. |
| Audio bitrate | **~40kbps Opus** | Cheap; protect it hardest (audio matters more than video). |
| Video bitrate | **0.5–2.5Mbps per simulcast layer** | 3 layers (~180p/360p/720p–1080p); SFU selects per receiver. |
| Call setup time (to first media) | **<1s** | ICE gather + connectivity checks + DTLS handshake (~1–2 RTT). |
| TURN relay rate | **~10–20% of sessions** | NAT traversal fails for symmetric NAT / restrictive firewalls. Cost + capacity. |
| Availability (signaling) | **99.99%** | Can't start/modify calls without it. |
| Availability (media/SFU) | **99.99%, calls-in-progress survive signaling loss** | Data plane independent of control plane. |

### 6.3 Capacity estimation (worked)

- **Per-client bandwidth (SFU, 50-person call, layer-selected).** Uplink:
  one stream, ~2.5Mbps top layer (simulcast adds ~30% for the extra
  layers). Downlink: speaker at high res (~2.5Mbps) + ~24 visible
  thumbnails at ~150kbps ≈ **~6Mbps down**. Mesh would have needed 49
  uplinks (~120Mbps up) — **dead on arrival**, which is the whole reason
  for the SFU.
- **SFU egress.** A core forwards (not transcodes) packets; budget ~a few
  hundred forwarded streams per core at these bitrates. A 50-person call ≈
  50 inbound, fan-out bounded by layer selection + active-speaker → on the
  order of ~1–2 cores per large call; **SFU is bandwidth-bound** (a 50-way
  call is tens of Mbps in, hundreds of Mbps out).
- **Fleet.** 1M concurrent calls, mostly 1:1 (which *could* be P2P but we
  route many through SFU for NAT/observability) + a long tail of group
  calls → thousands of SFU nodes, **placed at the edge** (region-local) so
  the network hop is 20–40ms, not 150ms+.
- **TURN.** ~15% of sessions relay *all* their media through TURN. At
  ~2–6Mbps/session that's the **single biggest bandwidth line** after SFU
  egress — and it's pure relay, no value-add, so we minimize it.
- **Session registry.** ~1M calls × a few KB (participants, SFU
  assignment, ICE state) ≈ low-GB in Redis with TTL — trivial; it's a
  routing/coordination store, not the media path.

**Numbers that changed a design choice:**
- 49 uplinks at 1:1-mesh → **move to SFU at ~4–5 participants.**
- ≤150ms one-way → **edge SFUs** and **no MCU mixing on the hot path.**
- TURN at 15% × multi-Mbps → **egress is the cost dominator**, design to
  minimize relays (prefer direct/reflexive; TURN is fallback only).
- SFU is forward-not-transcode → **bandwidth-bound**, so we scale on egress
  Gbps, not cores.

### 6.4 API / signaling messages

```
# Control plane (WebSocket to signaling service; JSON messages)
JOIN        { callId, userId, deviceInfo }      -> assigned SFU + ICE servers (STUN/TURN creds)
OFFER       { callId, sdp }                      # SDP offer (codecs, ICE params)
ANSWER      { callId, sdp }                      # SDP answer
ICE_CAND    { callId, candidate }                # trickle ICE, sent as gathered
RENEGOTIATE { callId, sdp }                       # someone joined / screen-share / track change
ICE_RESTART { callId }                            # network changed; re-gather + re-nominate
LEAVE       { callId, userId }

# Media plane (NOT on the WebSocket): SRTP/UDP, peer<->peer (1:1) or client<->SFU.
#   RTP carries media; RTCP carries SR/RR, NACK, PLI/FIR, transport-cc feedback.
```

The WebSocket carries *only* signaling. The first media packet flows over
SRTP after ICE nominates a pair and DTLS completes — and from then on the
call does **not** depend on the signaling server except for renegotiation
or ICE-restart.

### 6.5 Data model

- **`call`** (Redis, TTL + heartbeat): `call_id → {participants[],
  sfu_node_id, region, created_at, state}`. The routing source of truth.
- **`participant`** (Redis): `(call_id, user_id) → {device, ice_state,
  publishing_tracks[], assigned_layers, last_heartbeat}`. TTL expiry on
  missed heartbeats so dead clients fall out.
- **`presence`** (Redis, short TTL): `user_id → online/in_call`. Heartbeat-
  refreshed.
- **`sfu_node`** (Redis / control plane): `sfu_node_id → {region, load,
  draining?}`. Used for placement + graceful drain.
- **TURN credentials** are short-lived (time-limited HMAC), minted per
  session by the signaling service.

Media itself is **never stored** (except the separate recording pipeline);
the only durable-ish state is soft session/routing state, which is
recoverable by re-join.

### 6.6 High-level architecture

```
        ┌──────────────────────────────────────────────────────────────┐
        │  Client A (browser/app)        Client B (browser/app)        │
        │  WebRTC stack: ICE agent, SRTP, jitter buffer, GCC, codecs   │
        └──────┬─────────────────────────────────────────┬─────────────┘
               │ WebSocket (CONTROL PLANE)                │ WebSocket
               │ SDP / ICE / renegotiate                  │
        ┌──────▼──────────────────────────────────────────▼─────────────┐
        │  Signaling Service  (stateless, horizontally scaled)          │
        │  - SDP offer/answer relay, trickle ICE                        │
        │  - SFU assignment + TURN cred minting                         │
        └──────┬──────────────────────────────────┬─────────────────────┘
               │ read/write session state          │ mints/checks
        ┌──────▼─────────────┐            ┌────────▼────────┐
        │ Session Registry   │            │ STUN servers    │ <- reflexive addr
        │ (Redis, TTL +      │            │ (cheap, stateless)│   (no media)
        │  heartbeats)       │            └─────────────────┘
        └────────────────────┘
   ─────────────────────────────────────────────────────────────────────
        DATA PLANE (SRTP/UDP — independent of control plane)
        ┌──────────┐   direct P2P (1:1, ~80%)    ┌──────────┐
        │ Client A │◄───────────────────────────►│ Client B │  (mesh ≤4)
        └────┬─────┘                              └─────┬────┘
             │ group call / NAT-blocked / observability │
             │                ┌─────────────────────────▼─────────┐
             │                │  EDGE SFU (region-local)          │
             └───────────────►│  - forwards (no mix)              │◄─── other
                              │  - per-receiver simulcast/SVC     │     participants
                              │    layer selection                │
                              │  - NACK/PLI, transport-cc relay   │
                              └────────────┬──────────────────────┘
                                           │ cascade (cross-region)
                              ┌────────────▼──────────────────────┐
                              │  TURN relay (~15% of sessions)     │  <- all media
                              │  (bandwidth dominator; fallback)   │     bytes flow
                              └────────────────────────────────────┘
```

The design's whole point: **signaling is the control plane and media is the
data plane — they fail independently**; **media stays at the edge and is
forwarded, not mixed**, to defend the ≤150ms budget; and **TURN is fallback
only** because it's the cost dominator.

### 6.7 Signaling + connection establishment (deep dive A)

Decision: **WebSocket signaling, full ICE with STUN + TURN fallback,
DTLS-SRTP for media.** (Full walk-through in deep dive A.) The load-bearing
commitments:
- Control/data plane split is an **invariant**: live calls survive a
  signaling outage.
- **Trickle ICE** for fast setup; **DTLS handshake (~1–2 RTT)** on the
  setup path keeps first-media <1s; SRTP per-packet cost is negligible.
- Session/routing state in **Redis with TTL + heartbeats**; signaling
  servers stateless.
- **TURN is fallback only** (~15%); STUN is the cheap common case.

### 6.8 Media topology (deep dive B)

Decision: **SFU as default; mesh for 1:1; MCU only for PSTN-bridge /
low-power / recording.** (Full walk-through in deep dive B.) Load-bearing:
- Mesh O(n²) uplinks → breaks at ~4.
- SFU forwards once-up / fan-out-down, **bandwidth-bound not CPU-bound**.
- **Per-receiver simulcast/SVC layer selection** is the SFU's real job and
  is what makes 50-way calls tractable.

### 6.9 Latency budget + degradation (deep dive C)

Decision: **media is AP — conceal/drop, never block; adaptive jitter
buffer; FEC/RED + PLC for audio, NACK/RTX only with budget; GCC/transport-
cc adaptive bitrate + SFU layer-drop.** (Full walk-through in deep dive C.)
Budget is allocated hop-by-hop to ~120–150ms; **edge SFUs + no hot-path
mixing** protect it.

### 6.10 Stream ↔ out-of-band metadata correlation (the subtle one)

*Scenario: live captions / transcription / AI-agent signals arrive on a
**different transport with a different clock** and must align to the media.*

This is the deep-dive most candidates miss, and it's high-leverage:
- The media stream is **RTP**, timestamped in the codec's clock (e.g. Opus
  at 48kHz) with monotonically increasing **sequence numbers**. RTP
  timestamps are **not wall-clock** — they start at a random offset.
- The mapping to real time comes from **RTCP Sender Reports (SR)**, which
  pair an **RTP timestamp with an NTP wall-clock timestamp**. That pair is
  the Rosetta Stone: it lets you convert any RTP timestamp to wall time and
  thus align a media position to an event on another channel.
- The **transcription service** (or AI-voice agent) consumes the audio,
  emits text events on its own connection (WebSocket/gRPC) with its own
  clock. To land a caption on the right word: stamp each transcript event
  with the **RTP timestamp / media offset of the audio it derived from**,
  convert both sides to the common NTP timeline via the SR mapping, and
  apply a **bounded re-sync** (a small alignment window — tens to low
  hundreds of ms — to absorb the side channel's clock drift and processing
  delay). Out-of-window events are clamped, not trusted blindly.
- The principle, stated: **never trust two independent clocks to agree;
  pick one authoritative timeline (the RTP-via-SR media clock), translate
  the side channel onto it, and bound the correction.** This is exactly the
  pattern for AI-voice-agent transport and contact-center analytics.

### 6.11 PSTN / SIP interop (telephony ingress)

*Scenario: a landline dials in, or an AI voice agent answers a phone call.*

- The carrier network speaks **SIP** (signaling) and **RTP** (media, often
  G.711) — *not* WebRTC. You put a **SIP gateway / media bridge** at the
  edge: it terminates the SIP/RTP leg from the carrier and **bridges it
  into the WebRTC/SFU world** (translating SIP↔SDP, transcoding G.711↔Opus,
  and — because a phone gets exactly one audio stream — this leg often goes
  through an **MCU-style mix** so the caller hears the whole room as one
  stream).
- This is the one place MCU mixing is *correct on the hot path*: the PSTN
  endpoint cannot do selective forwarding or render N thumbnails. Accept
  the mix latency for that leg; the rest of the call stays SFU.
- The same gateway is the substrate for **AI voice agents** (bot joins as a
  participant, consumes mixed audio, emits TTS audio back) and
  **contact-center transport** — which is where the sub-300ms turn-latency
  budget bites hardest: no MCU on the hot path *for the WebRTC legs*, edge
  bridges, short jitter buffers.

### 6.12 Multi-region / CAP

CAP commits, said out loud: **media is AP/best-effort; signaling is CP-ish
(strongly-consistent session registry within region); session registry is
globally readable, regionally authoritative.**

- **Media wants the SFU closest to participants.** Each participant connects
  to a **region-local edge SFU**. For a **cross-region call** (people in
  APAC + US), SFUs **cascade**: each user hits their nearest SFU, and the
  SFUs forward between themselves over the (fast, provisioned) backbone —
  so you pay the cross-region hop **once between SFUs**, not once per
  participant pair. This bounds the long-haul latency and the egress.
- **Signaling can be regional with a global session registry.** Call
  routing state lives in Redis; geo-routing (DNS/anycast) sends a joining
  client to the nearest signaling + SFU. The registry is **regionally
  authoritative for a given call** (the call is pinned to a home region's
  SFU cluster); other regions read it to route joiners.
- **Why media is AP and we don't fight it:** there is no globally
  consistent "media state" — each receiver's playout is independent. We
  optimize for latency and accept per-receiver quality variance.

### 6.13 Cost (back-of-envelope, monthly)

The dominator is **egress bandwidth**, not compute — because the SFU
forwards rather than transcodes, and TURN relays raw media.

| Component | Notes | Driver |
|---|---|---|
| **SFU egress bandwidth** | Fan-out: every participant's downlink is server egress. Hundreds of Mbps per large call × thousands of concurrent calls. | **#1 cost. $/GB egress.** |
| **TURN relay bandwidth** | ~15% of sessions relay *all* media (up+down) through TURN at multi-Mbps. Pure relay, no value-add. | **#2 cost.** Minimize relays. |
| SFU compute | Forward, not transcode → cheap per stream. Cores scale with stream count, but bandwidth saturates first. | Secondary. |
| Signaling + STUN | Tiny payloads, stateless boxes. STUN is a packet or two per session. | Negligible. |
| Session registry (Redis) | Low-GB, routing only. | Negligible. |

**Contrast SFU vs MCU cost:** SFU's cost is **egress bandwidth**; MCU's is
**compute** (a CPU/GPU core per call to decode-mix-encode). At millions of
concurrent calls, MCU's per-call core is the killer — *that's* why SFU
wins, not just latency. **Dominator: SFU + TURN egress bandwidth.** The
single biggest cost lever is **driving down the TURN-relay fraction**
(better ICE, more STUN success) and **edge placement** (shorter, cheaper
hops + less backbone egress).

### 6.14 Failure modes & blast radius

| Failure | Effect | Mitigation / policy |
|---|---|---|
| **SFU node death (10k live calls)** | All calls on that node drop their media | **Sticky routing** assigns each call to one SFU; on death, clients detect media stall → **reconnect via signaling → reassigned to a new SFU → ICE-restart** re-establishes media in seconds. Blast radius = one node's calls. Keep nodes smaller / spread calls to bound it. **Graceful drain on deploy:** mark node `draining`, migrate or let calls finish, no new assignments. |
| **TURN exhaustion / capacity** | The ~15% of sessions that need relay can't connect | TURN is **fail-closed for those sessions** (no relay = no media), so over-provision + autoscale TURN on relay-fraction, alert on capacity. Direct/STUN sessions unaffected. |
| **Signaling outage** | Can't start/modify calls; presence stale | **Calls in progress SURVIVE** (data plane independent — media flows SFU/P2P-direct without signaling). New joins + renegotiation + ICE-restart fail until recovery. This is the headline property of the plane split. |
| **Congestion collapse** | Loss → retransmits → more loss | **GCC/transport-cc** caps send rate; SFU **drops receivers to lower simulcast layers** instead of demanding sender slowdown; NACK suppressed when no budget. |
| **Region failure** | Region's SFUs + signaling gone | Geo-routing fails clients over to next-nearest region; cross-region calls re-cascade; in-region calls re-establish via ICE-restart. Higher latency accepted during failover. |
| **DTLS/key issue** | Can't establish secure media | Connection setup fails fast → retry; doesn't affect established calls (keys already exchanged). |

**Fail-open vs fail-closed, per path:** *media* is best-effort — under loss
it **degrades, never blocks** (conceal/drop). *Signaling* failures are
isolated by design (live calls don't depend on it). *TURN* is
**fail-closed** for the sessions that need it (no relay = no call), which is
why it's over-provisioned. This split is the L6 commit.

**SLO/error budget.** Media 99.99% (a call dropping is the worst UX);
signaling 99.99% but with the explicit property that its outage doesn't
drop live calls. Page on TURN-relay-fraction spikes (NAT/connectivity
regression) and on SFU node-death rate.

### 6.15 Evolution at 10× (and broadcast)

- **More concurrent calls (10×):** add edge SFU capacity linearly; SFU is
  stateless-per-call and shared-nothing, so it scales horizontally. The
  egress bill scales linearly — the named seam is **cost**, so push harder
  on reducing TURN fraction and on SVC (single layered stream vs 3
  simulcast encodes) to cut uplink+egress.
- **Webinar / 100k passive viewers:** *this* is where you add an **MCU /
  composite → LL-HLS/WebRTC-broadcast** tier — the interactive core stays
  SFU; a separate broadcast pipeline mixes once and fans out via CDN. Named
  as a seam, not a redesign.
- **E2E encryption:** add **insertable streams / SFrame** so the SFU
  forwards ciphertext it can't read (it loses the ability to do server-side
  recording/transcription on that media — a stated trade-off).
- **AI voice agents at scale:** the SIP-gateway + mix path (6.11) becomes a
  first-class fleet; the metadata-correlation path (6.10) becomes
  load-bearing for real-time agent reasoning.

**What does not change:** the control/data-plane split, SFU-as-default,
the AP-for-media commitment, edge placement, the ≤150ms budget discipline.
The seams named at v1 are the seams at 10×.

### 6.16 What I'd own vs. delegate

I'd personally own the **media-plane contract** (topology, the AP/conceal
commitment, the latency budget) and the **control/data-plane separation
invariant** — they're the architecture-defining decisions the whole product
depends on. I'd delegate the **SFU node operation** to the team that runs
our edge media fleet, the **TURN/STUN infrastructure** to the networking
team, and the **session registry (Redis) ops** to the platform-storage
team. The **recording/broadcast pipeline** and **SIP-gateway** are natural
separate-team handoffs with clean interfaces (composite-out, SIP-in).

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence. Right is the level call.

| Evidence | Call |
|---|---|
| No latency budget after two prompts; "WebRTC, it's peer-to-peer, it scales"; no NAT/signaling model; held mesh at 50. | **Strong No Hire** |
| Named WebRTC and a media server but conflated signaling and media (routed media over the WebSocket / said signaling outage drops live calls); proposed TCP or retransmit-everything for media; no degradation story. | **No Hire** |
| Split signaling from media and walked ICE, but defaulted to MCU mixing with no per-call-cost awareness; jitter buffer named but not as a latency knob; "the call degrades" with no mechanism; single global SFU. | **Lean No Hire** |
| Committed to ≤150ms one-way, participants-drive-topology, ~1–3% loss, per-stream bitrates by minute 10. Split control/data plane and walked SDP/ICE/STUN/TURN end to end. **Picked SFU over mesh and MCU and defended it numerically.** Named a jitter buffer and at least one recovery mechanism. Handled SFU-death without freezing. Didn't reach simulcast layer selection or the AP-conceal framing unprompted. | **Hire L5** |
| All of L5-Hire, **plus**: allocated the latency budget hop by hop; reached simulcast/SVC layer selection when prompted; stated media-is-best-effort (conceal, don't block) and adaptive jitter buffer as a latency-vs-smoothness knob; correct plane-independence instinct on signaling outage; some egress-cost reasoning. | **Hire L5 / Lean L6** |
| All of the above **unprompted**, **plus**: allocated the budget and named spenders vs protectors (edge SFU, no hot-path mix) before being asked; stated the **AP-for-media commitment** with the recover/reconstruct/conceal/drop hierarchy and *why TCP is wrong*; explained the SFU's job as **per-receiver simulcast/SVC layer selection**; closed the congestion loop with **GCC/transport-cc adaptive bitrate + SFU layer-drop** and named congestion collapse; addressed **SFU-death blast radius + sticky routing + ICE-restart**; surfaced $/mo with **egress bandwidth as the dominator** and the SFU-vs-MCU cost contrast. Named the **fixed plane-split invariant** (live calls survive signaling loss). | **Hire L6** |
| Everything in L6, **plus**: generalized to the **cascaded-SFU cross-region** pattern (cross-region hop paid once between SFUs); produced the **stream ↔ out-of-band metadata correlation** design (RTP timestamps + RTCP SR/NTP mapping + bounded re-sync) for captions/AI signals; named the **SIP-gateway / PSTN-bridge** as the one place MCU mixing is correct on the hot path and tied it to AI-voice / contact-center sub-300ms turn latency; defended **TURN-fraction reduction** as the top cost lever; named what they'd **own vs delegate**; closed with a self-aware retro. | **Strong Hire L6** |

---

## Sources used in preparing this guide

- ITU-T Recommendation **G.114** — *One-way transmission time* (≤150ms
  preferred / 150–400ms with degradation / >400ms unacceptable; the
  mouth-to-ear budget): itu.int/rec/T-REC-G.114 and
  cs.columbia.edu/~andreaf/new/documents/other/T-REC-G.114-200305.pdf
- RFC **3550** — *RTP: A Transport Protocol for Real-Time Applications*
  (RTP timestamps + sequence numbers; RTCP Sender Reports mapping RTP→NTP):
  datatracker.ietf.org/doc/html/rfc3550
- RFC **8825** — *Overview: Real-Time Protocols for Browser-Based
  Applications (WebRTC)*: datatracker.ietf.org/doc/html/rfc8825
- RFC **8829** — *JavaScript Session Establishment Protocol (JSEP)* (SDP
  offer/answer, ICE, renegotiation): datatracker.ietf.org/doc/html/rfc8829
- RFC **8445** — *Interactive Connectivity Establishment (ICE)* (candidate
  gathering, connectivity checks, nomination):
  datatracker.ietf.org/doc/html/rfc8445
- RFC **5389 / 8489** — *Session Traversal Utilities for NAT (STUN)*
  (server-reflexive address discovery):
  datatracker.ietf.org/doc/html/rfc8489
- RFC **8656** — *Traversal Using Relays around NAT (TURN)* (relay fallback
  when P2P fails): datatracker.ietf.org/doc/html/rfc8656
- RFC **6716** — *Definition of the Opus Audio Codec* (low-latency speech,
  ~6–510kbps; FEC/PLC support): datatracker.ietf.org/doc/html/rfc6716
- **Google Congestion Control (GCC)** draft —
  *A Google Congestion Control Algorithm for Real-Time Communication*
  (delay-gradient + loss-based bandwidth estimation; transport-cc/REMB
  feedback): datatracker.ietf.org/doc/html/draft-ietf-rmcat-gcc
- BlogGeek.me (Tsahi Levent-Levi) — *WebRTC Multiparty Video Alternatives,
  and Why SFU is the Winning Model* (mesh vs SFU vs MCU trade-offs,
  simulcast): bloggeek.me/webrtc-multiparty-video-alternatives/
- Hello Interview — *WebRTC / real-time video system design* breakdown
  (signaling vs media plane, SFU topology, NAT traversal):
  hellointerview.com/learn/system-design
- Alex Xu, *System Design Interview Vol. 2* — proximity / real-time chapters
  (connection management, presence, fan-out).
- DesignGurus / System Design Handbook — video-calling / live-streaming
  breakdowns (SFU fan-out, edge placement, CDN broadcast tier).
- antmedia.io & metered.ca — *Mesh vs SFU vs MCU WebRTC topology* (capacity
  rules of thumb: mesh ≤4, SFU 5–100+, MCU composite cases):
  antmedia.io/webrtc-network-topology/

---

*End of guide. Related:* `13-realtime-chat.md` *(the long-lived-connection
and signaling overlap — WebSocket lifecycle, presence, multi-device
delivery and ordering — which this guide deliberately treats as the
control plane and leaves the chat/ordering depth to).*
