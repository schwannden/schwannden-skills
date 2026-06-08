# Question 14: Live Video Streaming System (real-time ingest → transcode → fan-out, e.g. Twitch / YouTube Live)

> Interviewer's guide for the 1-hour Google L5/L6 system-design round.
> Anchor problem for the **real-time streaming pipeline** archetype —
> ingest + transcode + CDN fan-out. The prompt is canonical (every live
> platform: Twitch, YouTube Live, sports streaming, interactive shopping).
> The calibration value is *not* whether the candidate can put a video on
> a CDN — it's whether they can hold **the latency-vs-reach-vs-cost
> triangle** in their head for an hour: sub-second interactive latency
> (WebRTC) reaches thousands at high per-viewer cost; HLS/DASH reaches
> millions cheaply at 10–30s latency; LL-HLS is the negotiated middle.
> A candidate who can't *commit a glass-to-glass latency target and
> defend the protocol and topology that follow from it* is answering a
> different, easier question than the one being asked.

---

## 1. Why this question (interviewer's framing)

Live streaming *looks* like "video on a CDN." A prepared L4 will say
"OBS pushes RTMP, we transcode to an HLS ladder, CloudFront serves the
segments, done" and stop. That answer is not wrong — it is the *standard
broadcast tier* and it is **incomplete in exactly the place the question
is probing**. The real prompt is: **one broadcaster's uplink has to reach
millions of viewers; the product has a latency expectation; egress
bandwidth will dominate your bill; and when the broadcaster's network
hiccups or a stream goes viral, the system must not fall over. What
latency do you commit to, what protocol and topology does that force, and
what breaks first?**

That forces explicit reasoning on five axes:

- **Latency vs. reach vs. cost — the triangle.** This is *the*
  trade-off, and unlike most it's a three-way tension, not a binary.
  Sub-second interactivity (WebRTC) means per-viewer connection state
  and per-viewer egress — you can serve thousands, not millions, and
  the cost is brutal. Standard HLS means segments cached at CDN edges —
  you serve millions at >95% cache-hit ratio and near-zero marginal
  cost, but you pay 10–30s of latency. LL-HLS is 2–5s. **You cannot
  have all three; the candidate must pick a corner for the product and
  defend it.**
- **One ingest → N renditions → millions of viewers.** The fan-out
  happens twice: once in the *transcode* (one source becomes an ABR
  ladder of 4–6 renditions × segment formats) and once in
  *distribution* (one origin object becomes millions of edge hits). Both
  fan-outs have a cost story and a failure story.
- **Cache-hit ratio is the whole egress bill.** A live stream is the
  *ideal* CDN workload — every viewer of a stream wants the same
  segment at nearly the same time. If your cache-hit ratio is 99%+ the
  origin is idle; if request coalescing fails and a viral stream
  stampedes the origin, you melt it. The L6 sees that the hit ratio is
  not an optimization — it's the difference between a $10k bill and a
  $1M bill.
- **Control plane vs. data plane.** Stream-session management, ABR
  manifest generation, and viewer auth are the control plane; the media
  bytes are the data plane. An ingest-side control blip must not kill
  in-flight playback that's already being served from CDN edges. The L6
  states this seam explicitly.
- **Real-time degradation.** The broadcaster's uplink is the weakest
  link in the chain and the one you don't control. When it degrades you
  adapt the *source* bitrate (or drop a rendition) rather than buffer
  unboundedly — the ingest-side congestion story most candidates skip.

### What "Hire" looks like at each level

**L5 Hire.** Commits to numbers by minute 10 (concurrent viewers,
concurrent ingest streams, glass-to-glass latency target, ABR ladder
bitrates, segment duration, cache-hit-ratio target). Names the
ingest→transcode→package→CDN pipeline cleanly and justifies each hop
(RTMP/SRT in, ABR transcode because viewer networks vary, HLS/DASH
segments because they're CDN-cacheable). Picks a latency tier *with a
reason* tied to the product. Knows the CDN cache-hit ratio drives egress
cost. Handles "ingest node dies" and "transcode overloads" calmly when
asked.

**L6 Hire.** All of the above, plus: **drives the room** (narrates the
budget, pre-ranks the deep dives off the NFRs). **Commits a
glass-to-glass latency target in the first 10 minutes and derives the
protocol/topology from it** — not the other way around — and names *what
would flip the choice*. Proposes the **multi-tier cache hierarchy with
origin shield + request coalescing** *before* being asked how a viral
stream is handled, and works the **egress cost math** showing why the
cache-hit ratio is the dominator. States the **CAP commitment**
explicitly (playback is AP, eventually-consistent segment availability;
DVR/VOD conversion is async). Volunteers the **tiered topology** —
WebRTC sub-second for the few who need interactivity, HLS/CDN for the
long tail — *and the cost reason you can't serve millions over WebRTC*.
Surfaces the **control-plane/data-plane split** so an ingest blip
doesn't drop viewers. Names what they'd own vs. delegate.

### Classic downlevel traps

1. **"Put it on a CDN" with no latency commitment.** The modal answer.
   When pushed — "the product is interactive Q&A; is 25s of latency
   acceptable?" — they either don't see that standard HLS makes
   interactivity impossible, or they bolt WebRTC on without seeing it
   won't reach the audience. Either way the packet writes itself: *did
   not derive the protocol from a committed latency target.*
2. **WebRTC for everything.** "WebRTC, it's sub-second." When asked
   "now 2 million concurrent viewers," they have no answer because
   per-viewer connection state and per-viewer egress don't cache and
   don't fan out at a CDN. The inverse trap of #1.
3. **No request coalescing / origin-stampede blindness.** "The CDN
   caches it." When a stream goes viral and 500k viewers all miss the
   cache on the same just-published segment simultaneously, the origin
   takes 500k concurrent fills and dies. Missing the
   coalescing/origin-shield tier is an L5-ceiling signal, exactly like
   missing the local cache in the rate-limiter.
4. **Unbounded buffering on uplink degradation.** When the
   broadcaster's network drops, they "buffer until it recovers" —
   adding latency that never comes back and eventually OOMing the
   ingest node. The L6 adapts the *source* bitrate instead.
5. **Transcode cost treated as free.** One 1080p60 source → a 5-rung
   ABR ladder is ~4–6 CPU cores of real-time transcode *per concurrent
   stream*. At tens of thousands of concurrent streams this is a
   massive compute fleet and the *second* cost dominator. Ignoring it is
   an L6 cost-blindness flag.

---

## 2. The 60-minute plan

Minute-by-minute. What you say, what you listen for, when you push back
vs. stay quiet.

### 0–5 min — Intro

**Say:** *"I'm <name>, L7 on <unrelated infra team>. 60-second bio, then:
design a live video streaming system — think Twitch or YouTube Live. A
broadcaster goes live; viewers watch. Drive it however you like; I'll
interject."*

**Listen for:** do they restate and sit with the ambiguity, or
immediately draw RTMP→transcode→CDN boxes? The L6 tell is asking the
*product* question first: *"What's the interactivity expectation — is
this a one-to-many broadcast where 20 seconds of delay is fine, or
interactive where the broadcaster reacts to viewers in real time? That
single answer picks my whole protocol stack."* That question *is* the
question.
**Push back when:** they whiteboard before scoping. Stay quiet otherwise.

### 5–15 min — Requirements & scope

**Say:** almost nothing. If asked "scale?" → *"Hot streams hit millions
concurrent; the distribution is a power law — most streams have dozens,
a few have millions. You tell me the numbers."* If asked "what latency?"
→ *"You tell me what the product needs, then defend it."* If asked "do
we do recommendations / chat / VOD?" → *"Live playback is the core. Tell
me what you'd cut and why."*

**Listen for:**
- Tight functional commit: broadcaster ingest, transcode to ABR ladder,
  package into segments, distribute to viewers, adaptive playback. Bonus
  for explicitly cutting recommendations, monetization, and (carefully)
  scoping chat as a *separate side channel* (which becomes deep dive
  fodder — stream↔metadata sync).
- NFRs **with numbers**: concurrent viewers (peak on a hot stream),
  concurrent ingest streams, **glass-to-glass latency target by tier**,
  ABR ladder bitrates, segment duration, cache-hit-ratio target,
  startup time, rebuffer ratio.

**Push back when:**
- "Low latency" with no number → *"Glass-to-glass — how many seconds
  from the broadcaster's camera to the viewer's screen? And does the
  product survive your number?"*
- They name a latency but don't tie the protocol to it → *"You said 2
  seconds. RTMP-to-HLS gives you 15. What protocol gets you to 2, and
  what does it cost you?"*
- "Millions of viewers over WebRTC" → *"What's the per-viewer state and
  egress cost? Multiply it out."*

### 15–25 min — Capacity + high-level design

**Say:** mostly silent. If they skip math, *"Before we draw — what does
the egress math say, and what's the dominator?"*

**Listen for:**
- Worked numbers: peak egress = concurrent viewers × selected bitrate;
  transcode compute = concurrent streams × cores/stream; origin fill
  rate = (1 − cache-hit-ratio) × edge requests; segment store size.
- **The numbers that decide the architecture:** (a) egress at viewer
  scale is enormous and *only* survivable at >95% cache-hit ratio —
  this justifies the multi-tier cache + coalescing; (b) the latency
  target dictates the protocol, which dictates the topology.
- Box diagram: broadcaster → ingest (RTMP/SRT) → transcode (ABR ladder)
  → packager (segments/parts) → origin → origin shield → CDN edge →
  viewer. WebRTC path drawn *separately* for the interactive tier.

**Push back when:**
- 12 boxes, none on the hot path → *"Which hops are in the
  glass-to-glass budget? Spend your latency, second by second."*
- Reflexive "just use a CDN" → *"What's your cache-hit ratio, and what
  happens to the origin when it's 80% instead of 99%?"*

### 25–45 min — Deep dives (the diagnostic zone)

Three **mandatory** dives (this question has exactly three):

1. **Ingest + transcode pipeline.** Ask: *"Broadcaster's OBS pushes a
   1080p60 stream. Walk me from that packet to a cacheable segment.
   How many renditions, what's the compute, and what happens when their
   uplink drops to 1 Mbps mid-stream?"*
2. **Distribution / fan-out at viewer scale.** Ask: *"This stream goes
   viral — 0 to 1 million viewers in 90 seconds. Walk me through the
   request path. What's your cache-hit ratio, and what stops the origin
   from being stampeded on every new segment?"* This is where
   origin-shield + request coalescing must appear. If it doesn't, that's
   a finding.
3. **The latency-vs-reach trade-off.** Ask: *"Commit a glass-to-glass
   latency target for this product and defend the protocol. Now the
   product team says it needs to be interactive — the host answers
   viewer questions live. What changes, and what does it cost?"*

**Listen for at L6:** committed latency budget broken down by hop;
LL-HLS vs WebRTC vs HLS picked *for the product* with the flip
condition named; tiered topology (WebRTC talent layer + HLS long tail);
origin-shield coalescing with a cache-hit number; source-bitrate
adaptation on uplink degradation; >95% cache-hit-ratio target with the
egress-cost consequence.

**Push back hard** on "buffer until the network recovers" (*"how much
RAM, and does the latency ever come back?"*), on "WebRTC scales fine"
(*"per-viewer egress × 2M viewers — show me the number"*), on "the CDN
handles the viral spike" (*"500k simultaneous cache-misses on a fresh
segment — what's the origin doing?"*).

### 45–55 min — Evolution / curveball

Pick **one**:
- *"A CDN region goes dark for 10 minutes during a championship match.
  Walk me through what happens to viewers in that region, minute by
  minute."* (Multi-CDN failover; player-side retry; AP playback.)
- *"The product adds a live scoreboard and AI captions that must line up
  with the video frame. They travel a faster, separate path. How do you
  keep them in sync?"* (Stream↔metadata sync — PTS/timestamp alignment;
  the high-leverage angle most candidates miss.)
- *"10× — the hottest stream goes from 1M to 10M concurrent. What breaks
  first?"* (Egress, edge fan-out; the cache architecture should *not*
  need to change — that's the point.)

**Listen for:** seam identification, not redesign. L6 names the 2–3 knobs
and the migration path.

### 55–60 min — Wrap

**Say:** *"That's time. What would you do differently with 15 more
minutes? Then — questions for me?"*

**Still scoring:** self-aware retro ("I didn't get to per-title encoding
or the DVR window") and what they ask.

---

## 3. Probing prompts (the kit)

Pre-loaded, with the signal each hunts. Drop verbatim; use silence after.

| Prompt | Signal hunted |
|---|---|
| *"Glass-to-glass latency target — commit a number of seconds."* | Forces the central trade-off into the open. A number here is load-bearing; everything downstream derives from it. |
| *"Is this product interactive, or one-to-many broadcast?"* | The product question that picks the protocol. L6 asks it first, unprompted. |
| *"You said 2 seconds — what protocol, and why not standard HLS?"* | LL-HLS vs HLS vs WebRTC chosen *because of* the latency budget, not recalled. |
| *"Concurrent viewers on a hot stream vs. concurrent ingest streams."* | Workload-shape grounding. Power-law fan-out: millions of viewers, far fewer streams. |
| *"One 1080p60 source → how many renditions, and what's the compute?"* | ABR ladder + ~4–6 cores/stream real-time transcode. The first cost dominator's seed. |
| *"Broadcaster's uplink drops to 1 Mbps mid-stream. What happens?"* | Source-bitrate adaptation / rendition drop, NOT unbounded buffering. |
| *"Segment duration — 6s, 2s, or 200ms parts? What does it buy you?"* | Latency-vs-overhead trade-off; LL-HLS parts vs standard segments. |
| *"Viral spike: 0→1M viewers in 90s. What's the request path?"* | Multi-tier cache + origin shield + request coalescing. The whole distribution dive. |
| *"What's your cache-hit ratio, and what's the origin doing at 95%?"* | >95% target; sees the hit ratio as the egress-cost lever, not an optimization. |
| *"500k viewers miss the cache on the same fresh segment. Origin?"* | Request coalescing — collapse N concurrent fills into one origin fetch. |
| *"Now it must be interactive — host answers viewers live. What changes?"* | Tiered topology: WebRTC for the few, HLS for the many; names the cost reason. |
| *"Per-viewer cost: WebRTC vs CDN. Multiply it out for 2M viewers."* | Why WebRTC can't be the long-tail path; egress + connection state. |
| *"Live scoreboard / captions on a faster side path. Keep them synced?"* | Stream↔metadata sync via PTS/timestamp alignment; bounded re-sync. |
| *"Ingest control plane blips. Do in-flight viewers drop?"* | Control-plane/data-plane separation; CDN-served playback survives. |
| *"CDN region goes dark mid-event. Viewers in that region?"* | Multi-CDN / multi-region failover; AP playback; player retry. |
| *"Monthly cost at your viewer scale. Name the dominator."* | L6 marker. CDN egress, then transcode compute. Worked, not hand-waved. |

---

## 4. Where to dig deeper (interviewer's deep-dive picks)

All three are **mandatory** for this question. For each: phrasing, L5 vs
L6 shape, anti-signal, packet quote.

### Deep dive A — Ingest + transcode pipeline

**Phrasing.** *"The broadcaster's OBS pushes a 1080p60 stream to you.
Walk me from that packet to a cacheable segment a viewer can request.
How many renditions, what's the compute cost, and what happens when
their uplink degrades to 1 Mbps mid-stream?"*

**Strong L5 answer.** Names the pipeline cleanly: broadcaster encodes and
pushes over **RTMP** (or **SRT** for lossy networks — SRT does
retransmission and is better over the public internet) to a
geographically near **ingest server**. The ingest server terminates the
push, demuxes, and hands frames to a **transcoder** that produces an
**ABR ladder** — e.g. 1080p (~6 Mbps), 720p (~3 Mbps), 480p (~1.5
Mbps), 360p (~0.8 Mbps), plus a 240p (~0.4 Mbps) floor — so viewers on
different networks can adapt. Each rendition is **packaged into segments**
(2–6s for HLS/DASH; fMP4/CMAF so one set of segments serves both HLS and
DASH) with a manifest/playlist, written to the origin. Knows transcode is
expensive — roughly **4–6 CPU cores per concurrent 1080p60 source** for
a 5-rung ladder, or a hardware/GPU encoder. On uplink degradation: the
broadcaster's encoder should drop its source bitrate.

**Strong L6 answer.** All of the above, plus the moves that earn the
level:

- **Transcode is a fan-out with a real fleet cost, stated as the second
  cost dominator.** At, say, 50k concurrent streams × ~5 cores = ~250k
  cores of real-time transcode. They name the levers: hardware/ASIC
  encoders (NVENC, dedicated transcode chips) at ~5–10× the density of
  software x264; **per-title / content-aware encoding** to drop the
  ladder's top rungs on low-motion content; and — critically — **only
  transcode renditions someone is watching** (lazily spin up lower
  rungs, or for cold/tiny streams *passthrough* the source rendition and
  skip transcode entirely until viewership justifies the ladder).
- **Backpressure on uplink degradation, done right.** When the
  broadcaster's network drops, you do **not** buffer unboundedly on the
  ingest side — that adds latency that never recovers and eventually
  OOMs the node. Instead: SRT/RTMP congestion signals propagate back to
  the broadcaster's encoder, which **adapts its source bitrate down**
  (or the platform sheds the top rungs of the ladder for that stream).
  The viewer-side ABR then naturally settles to a lower rung. The L6
  names the bound: ingest buffer is a small fixed window (e.g. 1–2s);
  past that you drop frames or step the source down, never grow the
  buffer.
- **The packager produces both standard segments and LL-HLS partial
  segments** if the latency tier demands it — the same encoded frames,
  chunked into ~200–500ms **parts** announced in the playlist before the
  full segment closes (chunked transfer / `EXT-X-PART`), so a player can
  start a part before the 6s segment is complete. This is the seam that
  turns a 15s pipeline into a 2–5s one without re-architecting.
- **Soft-state ingest registry + graceful drain.** Each live stream has
  an ingest *session* (TTL'd, heartbeated) in a registry mapping
  `stream_key → ingest_node`. On a planned drain, the node finishes its
  current segment, the broadcaster's encoder reconnects (RTMP reconnect /
  SRT failover) to a new node, and the manifest continuity is preserved
  with a discontinuity marker. The session is *soft state* — losing the
  registry forces a reconnect, not a lost broadcast.

**Anti-signal.** "Transcode to the ladder, done" with no compute cost; or
"buffer until the uplink recovers" with no bound; or treating one
ingest = one fixed full ladder regardless of viewership. → Packet:
*"Treated transcode as free and proposed unbounded ingest buffering on
uplink degradation; did not see source-bitrate adaptation."*

**Packet quote (Hire).**
> *"Walked RTMP/SRT ingest → ABR-ladder transcode (named ~5 cores per
> 1080p60 source as the second cost dominator) → CMAF segmenting. On
> uplink degradation, adapted the source bitrate with a bounded ingest
> buffer rather than buffering unboundedly. Volunteered lazy
> per-rendition transcode and per-title encoding as the compute levers,
> and LL-HLS partial segments as the latency seam. Unprompted."*

### Deep dive B — Distribution / fan-out at viewer scale

**Phrasing.** *"This stream goes viral — 0 to 1 million concurrent
viewers in 90 seconds. Walk me through the request path for a segment.
What's your cache-hit ratio, and what stops the origin from being
stampeded every time a new segment publishes?"*

**Strong L5 answer.** Segments are static, immutable objects, so they're
**CDN-cacheable**. Viewers fetch the manifest, then pull segments from
the nearest **CDN edge**. Because all viewers of a stream want the same
segment at nearly the same time, the cache-hit ratio is very high — one
origin fetch serves the whole edge's viewers. Names a target like **>95%
cache-hit ratio**. Knows the CDN, not the origin, absorbs the viewer
fan-out, and that this is why egress (not origin compute) dominates.

**Strong L6 answer.** All of the above, plus the named mechanism that
makes virality survivable:

- **Multi-tier cache hierarchy with an origin shield.** Edge → regional
  mid-tier → **origin shield** (a single designated cache layer in front
  of the origin) → origin. Without the shield, every one of hundreds of
  edge POPs that misses goes to the origin independently; *with* it, edge
  misses collapse at the regional tier and the shield, so the origin sees
  ~1 fill per segment per shield, not per edge.
- **Request coalescing (cache-fill collapsing) is the load-bearing
  primitive.** When a fresh segment publishes and 500k viewers behind one
  edge all request it within the same ~100ms — all missing the cache —
  the edge must collapse those N concurrent misses into **one** origin
  fetch and fan the response back to all waiters. (Nginx
  `proxy_cache_lock`, Varnish request coalescing, Cloudflare "concurrent
  streaming acceleration" — the candidate should name the *behavior* even
  if not the product.) Without coalescing, a viral segment is a 500k-RPS
  origin stampede on *every* new segment. The L6 calls this out as the
  difference between a healthy origin and a melted one.
- **The cache-hit-ratio math is the egress bill, worked.** At 99%+
  hit ratio the origin egress is ~1/100th of viewer egress; the
  expensive egress is *edge → viewer*, which is what you pay the CDN for.
  The candidate ties the >95% target directly to dollars (see §6.11):
  improving hit ratio from, say, 90% to 99% can cut origin egress and
  origin compute by ~10×, and a poorly-tuned hit ratio is the single
  fastest way to a runaway bill.
- **Segment cacheability discipline.** Long-ish `Cache-Control` /
  immutable segments (the bytes never change once written); short TTL on
  the *manifest* (it updates as the stream grows). Don't put per-viewer
  query params on segment URLs (cache-buster = cache-killer); push auth
  to the manifest/token, not the segment path. For LL-HLS, the partial
  segments and blocking-playlist-reload requests need their own
  cacheability story (parts are short-lived, the playlist is
  long-polled).

**Anti-signal.** "The CDN caches it, so we're fine" with no
origin-shield/coalescing tier, no hit-ratio number, and no awareness of
the same-segment stampede. → Packet: *"Relied on 'the CDN handles it';
when pushed on 500k simultaneous cache-misses on a fresh segment, had no
coalescing or origin-shield mechanism — the origin stampede was a blind
spot."*

**Packet quote (Strong Hire).**
> *"Multi-tier cache: edge → mid-tier → origin shield → origin, with
> request coalescing collapsing N simultaneous misses on a fresh segment
> into one origin fill — explicitly the defense against a per-segment
> origin stampede on a viral stream. Targeted >95% (ideally 99%+)
> cache-hit ratio and tied it directly to the egress bill, showing a ~10×
> origin-cost swing. Kept segments immutable/cacheable and pushed auth to
> the token, not the path. Unprompted."*

### Deep dive C — The latency-vs-reach trade-off (commit a target, defend it)

**Phrasing.** *"Commit a glass-to-glass latency target for this product
and defend the protocol that follows. Now the product team says it must
be interactive — the host answers viewer questions live and reacts in
real time. What changes, and what does it cost you?"*

**Strong L5 answer.** Names the three tiers and their latencies
correctly:
- **Standard HLS/DASH:** ~10–30s glass-to-glass (driven by segment
  duration × playlist buffer — a 6s segment with a 3-segment buffer is
  ~18s). Cheap, CDN-cached, scales to millions. Right for VOD-like
  broadcast where latency doesn't matter.
- **LL-HLS / LL-DASH:** ~2–5s, via **partial segments** (~200–500ms
  parts) announced via chunked transfer and blocking playlist reloads.
  Still HTTP/CDN-cacheable, so it still scales to millions — the
  negotiated middle.
- **WebRTC:** **sub-second (<1s, often 50–150ms)**, interactive, but a
  *stateful per-viewer connection* (the same media-transport stack as
  real-time calling).

Picks a tier for the product with a reason — e.g. "sports broadcast
tolerates LL-HLS at 3s; interactive Q&A needs WebRTC."

**Strong L6 answer.** All of the above, plus the move that earns the
level: **commits a target, derives the topology, and tiers it.**

- **Glass-to-glass budget, broken down.** For an LL-HLS target of ~3s:
  encode+package ~0.5s, ingest+origin+CDN propagation ~0.5–1s, player
  buffer (a few parts) ~1.5–2s. They *spend the budget hop by hop* so
  the number is defended, not asserted.
- **Why you can't serve millions over WebRTC — the cost reason, with the
  number.** WebRTC fan-out is **SFU-style**: every viewer is a stateful
  peer connection with per-viewer encryption (DTLS-SRTP), congestion
  control, and per-viewer egress out of a media server. A single SFU
  node handles ~hundreds to low-thousands of receive-only viewers;
  scaling to millions means a tree of relay SFUs and *per-viewer* egress
  that doesn't cache. Industry data: CDN-backed broadcast held sub-4s
  for 40k+ concurrent at roughly **1/6 the marginal cost of a pure SFU**
  at that scale — and that gap widens at millions. So **WebRTC doesn't
  fan out at a CDN**; it's an O(viewers) cost, not O(streams).
- **Therefore: tier the topology.** WebRTC (sub-second) for the *few*
  who genuinely need interactivity — the host plus a handful of
  on-stream guests/questioners (the "talent layer"). LL-HLS/CDN
  (2–5s) for the *long tail* of millions of passive viewers. A guest who
  gets "pulled on stage" is promoted from the HLS tier to a WebRTC
  connection; the rest watch the HLS mix. This is the same insight as
  the SFU-for-the-room / CDN-for-the-broadcast split in video calling.
- **Names what flips the choice, explicitly.** If the product's
  interactivity requirement applies to *everyone* (e.g. a small
  paid masterclass of 200 where every attendee can unmute), WebRTC for
  all is viable and correct — the audience is small enough. If the
  audience is millions and the interactivity is one-to-few (host +
  questioners), tier it. If latency tolerance relaxes to 10s+, drop to
  standard HLS and shed the LL-HLS complexity. The flip condition is
  **audience size × who-needs-interactivity**, and the candidate states
  it as a rule, not a vibe.
- **CAP commitment on playback.** Playback is **AP** — a viewer always
  gets *some* playable segment (possibly slightly stale, possibly a
  lower rung), never a hard error, because availability beats freshness
  for a passive viewer. Segment availability is eventually consistent
  across edges. DVR/VOD conversion (turning the live stream into a
  rewindable/permanent asset) is **async** — it happens off the hot path
  and doesn't gate live playback.

**Anti-signal.** Picks a latency tier with no number, or picks WebRTC
for a million-viewer broadcast and can't multiply out the cost, or names
the three tiers but won't *commit* one to the product ("it depends"
without following through). → Packet: *"Listed HLS/LL-HLS/WebRTC but
would not commit a latency target or derive a topology; when pushed on
interactivity at scale, proposed WebRTC for all million viewers without
a cost check."*

**Packet quote (Hire L6).**
> *"Committed ~3s glass-to-glass via LL-HLS, spending the budget hop by
> hop. Derived the topology from the latency target, not the reverse.
> For the interactive requirement, tiered it: WebRTC sub-second for the
> host + on-stage questioners (the talent layer), LL-HLS/CDN for the
> millions in the tail — and justified it with the ~6× cost gap and the
> fact that WebRTC is O(viewers), not O(streams). Named the flip
> condition (audience size × who-needs-interactivity) as a rule. Stated
> AP playback with async DVR/VOD. Unprompted."*

---

## 5. Watch-outs / common traps

### Candidate-side (anti-signals)

- **No committed latency target.** "Low latency" with no seconds, or a
  protocol picked before a latency number exists. The whole question is
  derive-from-the-target; skipping it is the cardinal sin.
- **WebRTC-for-millions.** Can't multiply out per-viewer egress;
  doesn't see that WebRTC is O(viewers) and doesn't cache at a CDN.
- **Origin-stampede blindness.** "The CDN handles it" with no
  origin-shield/coalescing tier; melts the origin on the first viral
  segment.
- **Unbounded ingest buffering.** Buffers a degrading uplink instead of
  adapting the source bitrate; adds latency that never recovers.
- **Transcode treated as free.** No core-count-per-stream, no fleet
  cost, no per-title / lazy-rendition levers.
- **No cache-hit-ratio number.** Egress is the bill and the hit ratio is
  the knob; not naming a target (>95%) is L6 cost-blindness.
- **Control plane and data plane fused.** An ingest/session-management
  blip drops in-flight viewers because playback wasn't decoupled to the
  CDN.
- **Latency-vs-reach as "it depends" with no commit.** Names the tiers,
  refuses to pick one for the product. Performing knowledge.
- **No multi-CDN / failover story.** Single CDN as a SPOF for a
  championship-match-scale event.

### Interviewer-side (your own traps)

- **Letting them dwell on codec/protocol trivia.** H.264 vs AV1, RTMP
  vs SRT minutiae — interesting, not the signal. By minute 30 force the
  latency commit and the viral-fan-out scenario.
- **Leading them to origin-shield/coalescing.** Tempting because it's the
  elegant answer to the stampede. Don't. If they get there alone, that's
  the L6 finding; if you hand it over, the packet won't write
  convincingly.
- **Not driving to the "viral spike" scenario.** Mandatory. If
  unprompted by minute 40, push.
- **Over-rewarding "we'll use a CDN."** A CDN is not a signal. "A CDN
  *because* segments are immutable and every viewer wants the same one,
  with an origin shield and request coalescing to hold a 99% hit ratio
  through a viral spike" *is*.
- **Eating their 3-minute question window.** Still scoring on
  Googleyness.

---

## 6. The golden answer (what a strong L6 candidate would produce)

The L6-quality walk-through, structured the way I'd expect to hear it.
Numbers explicit, trade-offs committed. The product chosen for the
walk-through: **a live sports/event platform with an interactive Q&A
overlay** — broad enough to force the tiered-topology answer.

### 6.1 Functional requirements (committed scope)

v1: a **broadcaster goes live** (push ingest over RTMP/SRT); the system
**transcodes** to an ABR ladder; **packages** into CDN-cacheable
segments (and LL-HLS parts); **distributes** to millions of concurrent
**viewers** who get **adaptive playback** (the player picks a rung from
network conditions); a small **interactive tier** (host + on-stage
questioners) gets sub-second two-way via WebRTC; the live stream is
**converted to a DVR/VOD asset** asynchronously.

**Out of scope v1, said out loud:** recommendations / discovery; chat
(scoped as a separate side channel — but I'll cover stream↔metadata sync
as it bites here); monetization / ads; DRM (mentioned, deferred);
content moderation pipeline (real, separate system).

### 6.2 Non-functional requirements (with numbers)

| Metric | Target | Reasoning |
|---|---|---|
| Peak concurrent viewers (hot stream) | **2M** on one stream | Power-law: most streams have dozens; a few have millions. The fan-out is sized for the tail. |
| Concurrent ingest streams | **~50k** | Far fewer streams than viewers. Drives the transcode fleet, not the egress. |
| Glass-to-glass latency (broadcast tier) | **~3s** (LL-HLS) | The committed target. Sports tolerates 3s; it's the negotiated middle of the triangle. |
| Glass-to-glass latency (interactive tier) | **<1s** (WebRTC) | Host ↔ questioner two-way; only the few who need it. |
| ABR ladder | 1080p60 ~6 Mbps / 720p ~3 / 480p ~1.5 / 360p ~0.8 / 240p ~0.4 | Viewer networks vary 10×; the ladder is the adaptation surface. |
| Segment / part duration | 4s segments, **~330ms LL-HLS parts** | Parts give the 3s target; full segments keep cacheability. |
| CDN cache-hit ratio | **>95%, target 99%+** | This is the egress bill. The single most important number for cost. |
| Player startup time | **<2s** | Abandonment climbs fast past this. |
| Rebuffer ratio | **<0.5%** of watch time | The core quality-of-experience SLO. |
| Availability — playback | **99.99%** | If viewers can't watch, the product is down. |
| Availability — ingest | **99.9%** | A broadcaster reconnect is recoverable; viewer drop is not. |
| Consistency | **AP playback** (eventually-consistent segments); **async** DVR/VOD | Stated CAP commit. |

### 6.3 Capacity estimation (worked)

- **Peak viewer egress (the dominator).** 2M viewers on one hot stream;
  assume an average sustained rung of ~3 Mbps (most viewers aren't on
  1080p). 2M × 3 Mbps = **6 Tbps** of edge egress for that one stream at
  peak. Across the platform (sum of all streams) call it ~10–15 Tbps
  peak. **This is the bill.** The CDN absorbs it at the edge; the origin
  must not.
- **Origin egress (what we actually pay to fill).** At 99% cache-hit
  ratio, origin egress = ~1% of edge requests for *unique* segment fills
  ≈ a few fills per segment per shield per stream — **megabits, not
  terabits.** The two-orders-of-magnitude gap between 6 Tbps edge and
  ~origin-fill is *the entire reason* the hit ratio is the headline
  number.
- **Transcode compute (the second dominator).** 50k concurrent streams ×
  ~5 cores per 1080p60 5-rung ladder = **~250k cores** of real-time
  transcode at the naive ceiling. Levers cut this hard: hardware
  encoders (~5–10× density), lazy per-rendition transcode (don't encode
  rungs nobody watches), passthrough for cold/tiny streams. Realistic
  steady-state is a large but bounded fleet.
- **Segment store (hot window).** Live needs only a rolling DVR window —
  say 2 minutes hot per stream. 50k streams × 5 rungs × (2 min × bitrate)
  ≈ tens of TB hot, on object storage with a CDN in front. The full VOD
  asset (async) is a separate, cheaper cold-storage problem.
- **Interactive (WebRTC) tier.** Host + ≤10 on-stage at a time per
  stream — a handful of SFU connections per stream, negligible next to
  the HLS fan-out. *Intentionally* tiny, because it's the expensive
  per-viewer path.

**Numbers that changed a design choice:**
- 6 Tbps edge egress at 99% hit ratio vs. a melted origin at 90% →
  multi-tier cache + origin shield + request coalescing is non-optional.
- 3s latency target → LL-HLS parts (not standard HLS, not WebRTC) for
  the broadcast tier.
- ~250k naive transcode cores → lazy/per-title encoding and hardware
  encoders are first-class, not afterthoughts.
- WebRTC is O(viewers) → it's the talent layer only, never the tail.

### 6.4 API design

```
# Control plane (stream lifecycle)
POST /v1/streams                         { title, settings } → { stream_id, stream_key, ingest_url }
POST /v1/streams/:id/start               (ingest server registers session) → 200
POST /v1/streams/:id/stop                → 200 (triggers async DVR/VOD finalize)
GET  /v1/streams/:id                     → { state, viewer_count, renditions[] }

# Ingest (broadcaster → ingest server)
rtmp://ingest.<region>.cdn/live/<stream_key>      (RTMP push)
srt://ingest.<region>.cdn?streamid=<stream_key>   (SRT push, lossy-network preferred)

# Playback (viewer, data plane — hot path, all CDN-cacheable)
GET  /hls/:stream_id/master.m3u8         (manifest: lists rungs; short TTL)
GET  /hls/:stream_id/:rung/playlist.m3u8 (media playlist; LL-HLS blocking reload)
GET  /hls/:stream_id/:rung/:seg.m4s      (segment; IMMUTABLE, long cache)
GET  /hls/:stream_id/:rung/:seg.part     (LL-HLS partial segment; short-lived)

# Interactive tier (the few)
POST /v1/streams/:id/join-stage          → WebRTC offer/answer (SFU); SDP exchange
```

Auth lives in a short-lived **playback token** on the manifest request,
**not** on segment URLs (per-viewer query params would shatter the
cache).

### 6.5 Data model

- **`streams`** (control plane, durable RDBMS/Spanner): `stream_id`,
  `broadcaster_id`, `stream_key` (secret), `state`
  (idle|live|ending|vod), `created_at`, `region`, `settings`.
- **`ingest_sessions`** (soft state, TTL'd registry — Redis-shaped):
  `stream_key → {ingest_node, started_at, heartbeat}`. Lost registry =
  forced reconnect, not lost broadcast.
- **`viewer_sessions`** (soft state, TTL'd, sampled/approximate): used
  for the live viewer count and per-region routing; never on the segment
  hot path.
- **Segments & manifests** (object storage + CDN): immutable segment
  objects; mutable, short-TTL manifests. The rolling DVR window is a
  retention policy on the bucket.
- **`metadata_track`** (for stream↔overlay sync, deep dive in §6.10):
  `(stream_id, pts, type, payload)` — scoreboard updates, captions,
  reactions, each stamped with the **presentation timestamp (PTS)** of
  the video frame they belong to.

### 6.6 High-level architecture

```
  BROADCASTER (OBS / encoder)
        │  RTMP / SRT push  (source: 1080p60 ~6 Mbps)
        ▼
  ┌───────────────────┐     ingest session registry (soft state, TTL)
  │  INGEST SERVER     │◄──► stream_key → ingest_node  (heartbeat, drain)
  │  (regional, near   │
  │   broadcaster)     │
  └─────────┬──────────┘
            │ frames
            ▼
  ┌───────────────────┐   ~4–6 cores / 1080p60 source (2nd cost dominator)
  │  TRANSCODER        │   lazy per-rendition · per-title · HW encoders
  │  → ABR ladder      │   1080p/720p/480p/360p/240p
  └─────────┬──────────┘
            │ encoded renditions
            ▼
  ┌───────────────────┐   fMP4 / CMAF: one segment set serves HLS + DASH
  │  PACKAGER          │   4s segments + ~330ms LL-HLS PARTS
  │  → segments+parts  │   writes immutable objects + updates manifest
  └─────────┬──────────┘
            │ PUT
            ▼
  ┌───────────────────┐
  │  ORIGIN (object    │   <── DATA PLANE (media bytes)
  │  store, DVR window)│        CONTROL PLANE (stream lifecycle, auth,
  └─────────┬──────────┘        manifest gen) is SEPARATE — an ingest/
            │ fill (rare)       control blip does NOT drop CDN-served viewers
            ▼
  ┌───────────────────┐   request COALESCING: N simultaneous misses on a
  │  ORIGIN SHIELD     │   fresh segment → ONE origin fetch, fanned back
  └─────────┬──────────┘
            ▼
  ┌───────────────────┐
  │  CDN MID-TIER      │   regional cache (further coalescing)
  └─────────┬──────────┘
            ▼
  ┌───────────────────┐   >95% (target 99%+) cache-hit ratio
  │  CDN EDGE POPs     │   edge → viewer egress = THE BILL (~6 Tbps/stream)
  └─────────┬──────────┘
            │ HLS/LL-HLS (3s glass-to-glass)
            ▼
   MILLIONS OF VIEWERS (the long tail, AP playback)

  ── interactive tier (the FEW) ───────────────────────────
  HOST + on-stage questioners ──► WebRTC SFU (<1s, O(viewers),
                                  per-viewer state — NEVER the tail)
```

The design's whole point: **broadcast fan-out is O(streams) on the CDN**
(cheap, cacheable, scales to millions), **interactivity is O(viewers) on
WebRTC** (expensive, stateful, kept tiny), and the **control plane is
decoupled from the data plane** so an ingest blip can't drop in-flight
viewers.

### 6.7 The latency commitment, defended (the heart of the design)

**Decision: ~3s glass-to-glass via LL-HLS for the broadcast tier; <1s
via WebRTC for the interactive talent layer.**

Budget, spent hop by hop for the 3s target:
- encode + package into a part: ~0.5s
- ingest → origin → shield → edge propagation: ~0.5–1s
- player buffer (a few ~330ms parts): ~1.5–2s

**Why not standard HLS:** 6s segments × a 3-segment buffer ≈ 18s —
violates the interactive-overlay product. **Why not WebRTC for the
broadcast tier:** O(viewers) cost; doesn't cache at a CDN; at 2M viewers
the per-viewer egress and connection state are ~6× the cost of CDN
broadcast and don't fan out. **What flips it:** if interactivity were
required for *all* viewers and the audience were small (a 200-person
masterclass), WebRTC-for-all is correct; if latency tolerance relaxed to
10s+, drop to standard HLS and shed LL-HLS complexity. The flip rule is
**audience size × who-needs-interactivity.**

**CAP commit, stated:** playback is **AP** — a viewer always gets a
playable (possibly slightly stale, possibly lower-rung) segment, never a
hard error. Segment availability is eventually consistent across edges.
DVR/VOD finalization is **async**, off the hot path.

### 6.8 Ingest + transcode (see deep dive A)

- RTMP/SRT ingest to a regional node; SRT preferred over lossy public
  internet (retransmission).
- ABR-ladder transcode, ~5 cores/1080p60 source — the **second cost
  dominator**; cut with hardware encoders, **lazy per-rendition**
  transcode (don't encode rungs nobody watches), **per-title** encoding,
  and **passthrough** for cold streams.
- **Backpressure:** on uplink degradation, adapt the *source* bitrate /
  shed top rungs with a **bounded** ingest buffer (1–2s) — never buffer
  unboundedly.
- CMAF segments + LL-HLS parts from one encode (serves HLS and DASH).
- Soft-state ingest registry; graceful drain via reconnect + manifest
  discontinuity marker.

### 6.9 Distribution / fan-out (see deep dive B)

- Multi-tier cache: edge → mid-tier → **origin shield** → origin.
- **Request coalescing** collapses N simultaneous misses on a fresh
  segment into one origin fill — the defense against a per-segment
  viral stampede.
- Immutable segments (long cache) + short-TTL manifest; auth on the
  token, never on the segment path.
- **>95% (target 99%+) cache-hit ratio** — the egress-cost lever.

### 6.10 Stream ↔ out-of-band metadata synchronization (the high-leverage angle)

The scoreboard, captions, and reactions travel a **separate, faster
path** (a websocket/pub-sub side channel) than the video (LL-HLS, ~3s).
If you naively render them on arrival, the "GOAL!" overlay fires 3
seconds before the video shows the goal — a broken experience.

The fix: **align on PTS (presentation timestamp).** Every video frame
carries a PTS; every metadata event is **stamped with the PTS of the
frame it belongs to** at the source (or a wall-clock + a known offset).
The player holds metadata events in a small queue and **renders each one
when the video playhead reaches its PTS** — so the overlay matches the
frame, regardless of which path arrived first. Re-sync is **bounded**:
if the side channel lags or the player seeks, metadata older than the
playhead is dropped (log + skip, not replay), and the queue is capped.
AI captions/transcription work identically — the caption is stamped with
the PTS of the audio it transcribes and surfaced at that playhead. This
is the angle most candidates miss, and it's a clean L6 tell.

### 6.11 Cost (back-of-envelope, monthly)

The two dominators, in order: **CDN egress, then transcode compute.**

Take a large event: 2M peak concurrent × ~3 Mbps × 3 hours. Egress =
2M × 3 Mbps × 3 h = 2e6 × 3e6 bits/s × 10,800 s ≈ **8.1 exabits ≈ ~1.0
PB** for the event (edge → viewer). At a blended CDN egress rate of
~**$0.02–0.04/GB** at committed volume (CloudFront-class list is
~$0.035–0.085/GB; large streamers negotiate well below list), 1.0 PB ≈
1.0e6 GB × $0.03 ≈ **~$30k for that one 3-hour event's egress.** A
platform running many such events monthly lands in the **$1M–$10M/mo**
egress range — overwhelmingly the bill.

| Component | Notes | Relative |
|---|---|---|
| **CDN egress (edge→viewer)** | viewers × bitrate × hours × $/GB; ~PB-scale | **Dominator (~80–90%)** |
| **Transcode compute** | ~250k cores naive, cut by HW/lazy/per-title | Second (~10–15%) |
| Origin egress + storage | ~1% of edge at 99% hit ratio; rolling DVR window | <5% |
| Control plane + WebRTC tier | stream metadata; tiny SFU fleet | <2% |

**Why cache-hit ratio moves the dollar figure most:** drop from 99% to
90% hit ratio and origin egress + origin compute roughly **10×** (now
10% of requests fill from origin instead of 1%) — published CloudFront
data shows a 60%→85% improvement on a 100 TB/mo distribution saves
~$2.7k/mo; at PB scale the same delta is six figures. **Why the ABR
ladder moves it:** every viewer pushed to a lower rung is linearly less
egress — per-title encoding and a sane default rung are direct cost
levers, not just quality knobs.

### 6.12 Multi-region / consistency

CAP commits, said out loud: **playback AP; control plane CP-ish
(strongly consistent stream state); segment availability eventually
consistent.**

- **Ingest:** in the broadcaster's region (lowest first-hop latency).
- **Distribution:** global CDN; **origin shield per region** so each
  region's edges coalesce to a regional shield, not the home origin
  cross-continent.
- **Multi-CDN:** at championship-match scale, run ≥2 CDNs with
  **client-side or DNS-steered failover** — the player retries an
  alternate CDN host on errors. A CDN region outage degrades to the
  alternate; viewers in the dead region see a brief rebuffer, then
  recover (AP — they get a playable segment, not an error).
- **Control plane:** stream lifecycle state is strongly consistent
  (one authoritative record per stream); it's low-QPS and off the
  viewer hot path, so the consistency cost is affordable.
- **DVR/VOD:** the live→VOD conversion is async and replicated lazily;
  a viewer in EU may not see the just-finalized VOD in US for seconds —
  acceptable.

### 6.13 Failure modes & blast radius

| Failure | Effect | Mitigation / policy |
|---|---|---|
| Ingest node dies mid-stream | Broadcast interrupted | Broadcaster encoder **auto-reconnects** (RTMP reconnect / SRT failover) to another ingest node; manifest continues with a discontinuity marker; viewers rebuffer ~1–2s, don't drop. Soft-state registry re-binds. |
| Transcode overload | Renditions fall behind / rebuffer | Shed top rungs (drop 1080p first); autoscale the transcode fleet; lazy-encode only watched rungs; passthrough cold streams to free cores. |
| **Origin stampede on viral stream** | Origin melts on each fresh segment | **Request coalescing** at edge + mid-tier + origin shield: N simultaneous misses → 1 origin fill. The headline distribution defense. |
| CDN region outage | Viewers in region lose the stream | **Multi-CDN failover** (DNS/client retry to alternate); origin shield in surviving regions; AP playback degrades gracefully. |
| Broadcaster uplink degradation | Source quality drops / latency risk | **Adapt source bitrate / shed rungs**, bounded ingest buffer (1–2s); never buffer unboundedly. Viewer ABR settles lower. |
| Control plane (session mgmt) blip | Can't start/stop streams, auth hiccups | Data plane is **decoupled** — in-flight viewers keep playing from CDN; new joins may briefly fail. Fail the *control* path, not playback. |

**Fail-open vs fail-closed, per path:** *playback* fails open (a viewer
keeps watching a cached segment even if the control plane / origin is
briefly unreachable — availability beats freshness); *ingest auth and
new-stream creation* fail closed (don't let an unauthenticated push go
live). This split is the L6 commit — the same shape as the rate-limiter's
per-endpoint policy.

**SLO/error budget.** 99.99% playback → 4.32 min/mo. Page on rebuffer
ratio breaching 0.5% and on cache-hit ratio dropping below 95% (the
early warning for an egress-cost and origin-stampede incident).

### 6.14 Evolution at 10× (1M → 10M concurrent on the hottest stream)

- **Distribution:** unchanged in *shape* — the CDN edge fan-out is
  exactly what scales linearly; add edge capacity and the cache
  architecture holds. **This is the point of the design.** The hit ratio
  *improves* at higher concurrency (more viewers behind each edge = more
  cache reuse).
- **Transcode:** unchanged — transcode is O(streams), not O(viewers);
  10× viewers on one stream is *zero* extra transcode. (10× more
  *streams* would grow the fleet linearly.)
- **Origin shield:** widen the coalescing tier; the named seam is
  partition the shield by stream if a single hot stream's fills
  concentrate.
- **WebRTC tier:** unchanged — the talent layer is still a handful.
- **Cost:** egress scales ~linearly with viewer-bytes; the lever is the
  CDN rate negotiation and the ABR-ladder default rung, not the
  architecture.

**What does not change:** the latency commitment, the protocol tiering,
the cache hierarchy, the control/data-plane split, the AP playback
commit. The seams named at v1 are the seams at 10×.

### 6.15 What I'd own vs. delegate

I'd personally own the **latency/protocol contract** (the
glass-to-glass budget and the LL-HLS/WebRTC tiering rule) and the
**cache-hierarchy + coalescing design** (they're the cost-critical
invariants the whole platform's economics ride on). I'd delegate the
**transcode fleet** to the team that already runs our media-processing /
encoder infrastructure, the **CDN integration + multi-CDN failover** to
the edge/traffic team, and the **WebRTC SFU tier** to the real-time-media
team (it's the same media-transport stack as voice/video calling — see
the related guide). The **stream↔metadata sync** is a natural handoff to
whoever owns the live-events side-channel/chat product.

---

## 7. Signals scorecard

Left column is packet-quotable transcript evidence. Right is the level
call.

| Evidence | Call |
|---|---|
| No latency target after two prompts; "put it on a CDN, highly scalable" with no numbers; no cache-hit-ratio awareness. | **Strong No Hire** |
| "RTMP → transcode → CDN, done." When pushed on a 1M-viewer interactive product, bolted WebRTC on for everyone with no cost check, or insisted standard HLS was fine for interactivity. Didn't see the triangle. | **No Hire** |
| Named the pipeline and the three latency tiers correctly, but wouldn't commit a target ("it depends"); relied on "the CDN handles it" with no origin-shield/coalescing when asked about a viral spike. Saw the pieces, not the trade-off. | **Lean No Hire** |
| Committed concurrent viewers, ingest streams, a glass-to-glass target, ABR ladder, segment duration, and a >95% cache-hit target by minute 10. Picked LL-HLS (or WebRTC) for the product with a reason. Named transcode as a real compute cost. Handled ingest-node death and uplink degradation when asked. Didn't reach request coalescing or the tiered topology unprompted. | **Hire L5** |
| All of L5-Hire, **plus**: arrived at multi-tier cache + origin shield + request coalescing when prompted on the viral spike; tied cache-hit ratio to the egress bill; correct source-bitrate-adaptation instinct on uplink degradation; some cost reasoning. | **Hire L5 / Lean L6** |
| All of the above **unprompted**, **plus**: committed a glass-to-glass target and **derived the protocol/topology from it**; volunteered **origin shield + request coalescing** as the viral-stampede defense before being asked; **tiered the topology** (WebRTC talent layer + HLS/CDN long tail) with the ~6× cost gap and the O(viewers)-vs-O(streams) framing; named the **flip condition** (audience × who-needs-interactivity); stated **AP playback / async DVR-VOD**; worked the **egress cost math** and named CDN egress then transcode as the dominators; surfaced the **control/data-plane split**. | **Hire L6** |
| Everything in L6, **plus**: volunteered **stream↔metadata PTS-sync** for the scoreboard/caption overlay with bounded re-sync; named **lazy per-rendition + per-title transcode** as the compute levers and defended the bounded-buffer backpressure against my "why not just buffer" pushback; designed **multi-CDN failover** for the region-outage curveball; named what they'd **own (latency/protocol contract, cache hierarchy) vs. delegate (transcode fleet, CDN integration, SFU tier)**; closed with a self-aware retro. | **Strong Hire L6** |

---

## Sources used in preparing this guide

- Hello Interview / DesignGurus — *Design a Live Video Streaming
  Service* (ingest → transcode → CDN pipeline, 45-min interview shape):
  designgurus.substack.com/p/design-live-video-streaming-service
- Apple — *HTTP Live Streaming (HLS)* spec & the **Low-Latency HLS**
  extension (partial segments / `EXT-X-PART`, blocking playlist reload,
  ~2–5s latency): developer.apple.com/streaming/ and RFC 8216
  (datatracker.ietf.org/doc/html/rfc8216)
- AWS Media Blog — *Demystifying Apple Low-Latency HLS (ALHLS)* (parts,
  chunked transfer, latency math vs standard HLS):
  aws.amazon.com/blogs/media/alhls-apple-low-latency-http-live-streaming-explained/
- Mux — *An update on Low-Latency HLS live streaming* (LL-HLS in
  production, part sizing, player buffer): mux.com/blog/low-latency-hls-part-2
- Cloudinary — *Low-Latency HLS, CMAF, and WebRTC: Which Is Best?*
  (the latency-vs-reach triangle across protocols):
  cloudinary.com/guides/live-streaming-video/low-latency-hls-ll-hls-cmaf-and-webrtc-which-is-best
- Daily.co — *Video live streaming: notes on RTMP, HLS, and WebRTC*
  (ingest protocols, glass-to-glass latency by protocol):
  daily.co/blog/video-live-streaming/
- Twitch Engineering — *Live Video Transmuxing/Transcoding: FFmpeg vs
  Twitch Transcoder* (real-time ABR-ladder transcode cost,
  ~cores per 1080p60 source): blog.twitch.tv/en/2017/10/10/live-video-transmuxing-transcoding-f-fmpeg-vs-twitch-transcoder-part-i-489c1c125f28/
- Ant Media / Red5 — *WebRTC Scalability* and *SFU vs MCU vs XDN*
  (SFU per-node viewer limits, why WebRTC is O(viewers), CDN-backed
  broadcast ~1/6 the cost of pure SFU at 40k+):
  antmedia.io/webrtc-scalability/ and red5.net/blog/webrtc-architecture-p2p-sfu-mcu-xdn/
- AWS CloudFront pricing + cache-hit-ratio guides (egress $/GB tiers,
  origin shield, hit-ratio → origin-cost math):
  aws.amazon.com/cloudfront/pricing/ and
  cloudcostkit.com/guides/aws-cloudfront-cache-hit-rate/
- Satya Deep Maheshwari / systemdr — *Designing a Live Streaming
  Platform: From Ingest to CDN* (origin shield, request coalescing,
  cache-hit-ratio as the egress lever):
  satyadeepmaheshwari.medium.com/designing-a-live-streaming-platform-from-ingest-to-cdn-e03c7a2ce6e4

---

*End of guide. Related:* `12-voice-video-calling.md` *(the WebRTC
media-transport stack — SFU fan-out, per-viewer connection state, and
congestion control — that this guide reuses for the sub-second
interactive tier; the latency-vs-reach tiering here is the broadcast-scale
extension of that question's many-participant fan-out problem).*
