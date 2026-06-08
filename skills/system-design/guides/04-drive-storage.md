# Question 4: Google-Drive-like File Storage (Sharing & Versioning)

*Interviewer's guide. L6/L7 voice. Use this to run the round, not to read aloud.*

---

## 1. Why this question (interviewer's framing)

This is the **storage/indexing anchor** of the loop. The candidate cannot treat it as a CRUD app, because the file is **not the unit of storage**. A real Drive/Dropbox design is two systems glued together: an **immutable, content-addressed blob store** and a **mutable metadata store** (names, parents, ACLs, versions). The hire signal is whether the candidate sees that split *unprompted*.

What I'm actually testing:

- **Two-store reasoning.** Blobs in the database = no-hire-adjacent. Can they justify the consistency model of each store independently?
- **Chunking + dedup.** Files are sequences of content-addressed chunks. Do they get there on their own?
- **Sync protocol.** Drive's hardest piece is the desktop client knowing what changed without polling every file. Where L5s collapse and L6s shine.
- **Sharing model.** ACLs at scale = denormalization-vs-recomputation, with "shared with me" as the load-bearing case.
- **Versioning.** Free if chunking is right; quadratic if not.

### L5 vs L6 bar

**L5 hire:** splits blob from metadata, picks an object store + Spanner/sharded SQL, names chunking but waves on the algorithm, gets sharing roughly right with an ACL table, calls out resumable uploads, mentions versioning as "store a chain."

**L6 hire:** all of the above, *plus* — commits to a chunking algorithm by name (FastCDC / Rabin) and explains *why* content-defined beats fixed-size; names dedup savings as a number with intra/cross-user split (~35% blended); designs sync as a **namespace-keyed monotonic change journal**, not "client polls"; treats ACL eval as a denormalization problem with explicit invalidation; volunteers what they would *not* build (Docs-style merge, full-text in critical path); frames 10× / multi-region as *which seam moves*, not a redesign.

### Classic downlevel traps

1. Whole files in a database — instant no-hire on RRK.
2. "S3" / "Colossus" as the whole answer.
3. No chunking — upload 5GB as one PUT.
4. No sync protocol — most common L5 gap.
5. ACLs as one table queried per request; no caching, no "shared with me."
6. Versioning as "keep old copies" — quadratic storage.
7. Conflating Drive and Docs.

---

## 2. The 60-minute plan

### 0–5 min — intro

**Say.** "I'm <name>, I work on <vague storage thing>. Design a file storage and sharing service — Drive or Dropbox. Tell me what you're building." Deliberately vague. No scale, no SLOs.

**Listening for.** Do they sit with the ambiguity, or do they bolt? Do they ask "desktop sync, web, or both?" before drawing a box?

**Stay quiet.** The whole point of this phase is to see what they do without me.

### 5–15 min — requirements & scope

**Say.** Almost nothing. Answer direct questions crisply ("yes, 100M DAU; yes, web + desktop + mobile") but volunteer nothing. If they ask me to pick scope: "what would you cut and why?"

**Listening for:** concrete functional list; non-functional with numbers; explicit *scope-outs* of Docs-style collab and full-text-as-critical-path; desktop sync as first-class.

**Pushback.** If they don't bring up versioning *or* sharing by minute 12, one prompt: "anything else users expect?" If they still miss either → packet note.

### 15–25 min — estimation + storage split

**Say.** "Let's see some numbers."

**Listening for:** DAU, writes/day, avg file size (~1MB blended), size skew, read:write, storage growth/yr, peak Gbps. Then **the split**: blobs in object store, metadata in transactional store, chunk index in its own KV — each labeled with consistency model.

**Pushback.** Blobs in the metadata DB → "what's the row size?" Then watch them recover or dig deeper. Don't rescue.

### 25–45 min — deep dives (pick 2 of 3)

Three candidates: **chunking + dedup**, **sync protocol**, **sharing/permissions**. Pick the two they handwaved hardest.

**Defaults if balanced.** L5 → chunking + sharing (sync is hard; dragging through it eats clock). L6 → sync + sharing (chunking is easier with depth; sync and sharing separate L5 from L6).

**Say.** Minimalist. "Walk me through saving a file the server already has." / "100GB of shared folders — how does the client know one changed?" / "Alice→Bob's group→Carol re-shares one file to external Dan. Data model and read path."

**Pushback.** Fixed-size chunking → "1-byte insert at offset 0?" Polling → "100M clients × 100k files each, do the math." JOIN-ACL-per-request → "p99 at a billion rows?"

### 45–55 min — evolution / failures

Pick one based on the underdone thread: 10× traffic; multi-region; corrupt chunk on read; 95% upload drop; offline conflict; team-drives at 10k seats. **L6 picks the seam (1–2 components), L5 redraws.**

### 55–60 min — wrap

Three min for their questions. Still scoring. Strong: "on-call shape for the metadata team?" Weak: "promotion timeline?"

---

## 3. Probing prompts (the kit)

Each: prompt → signal / anti-signal.

**Requirements.**
1. *"Largest file?"* → 5GB/50GB + design implication. Anti: "any size."
2. *"How many versions, how long?"* → "100 or 30 days, whichever larger." Anti: "forever" with no cost.
3. *"Sharing granularity — file/folder? user/group/link?"* → asks *before* designing sharing.
4. *"Full-text content search?"* → "yes, async, not critical path." Scope discipline.

**Capacity.**
5. *"Napkin: DAU, writes/user/day, avg file size, storage/year."* → numbers used to *drive a decision*.
6. *"Read:write?"* → 5:1 to 10:1 with reason.
7. *"Peak upload Gbps, global?"* → Tbps-scale; CDN awareness.

**Storage split.**
8. *"Bytes vs metadata — where, how kept in sync?"* → "blob first, atomic metadata commit, GC orphans."
9. *"Blob-store key?"* → content hash (SHA-256); logical path lives in metadata.

**Chunking.**
10. *"Why chunk?"* → resumability + dedup + delta-sync. Anti: only resumability.
11. *"Fixed or content-defined?"* → CDC (FastCDC/Rabin) with cascading-edit reason. L5 bar: at least acknowledge the trade-off.
12. *"Chunk size? Why?"* → 4–8MB; RTT vs index cardinality.
13. *"Dedup savings — number, intra- vs cross-user?"* → ~30% intra, ~50% cross, blended ~35%. Anti: "huge."

**Sync.**
14. *"Client closed a week; shared folder changed; reconnect."* — *The* L6 question. Signal: namespace-keyed change journal, monotonic rev, client persists last-seen rev, reconnect reads delta, pulls only changed chunks. Anti: "client polls."
15. *"Push vs poll, pick one."* → long-poll/WebSocket for push, poll fallback; *one connection per client*, multiplexed. Anti: connection per file.
16. *"Two clients edit one binary offline."* → LWW + conflict copy. Anti: "we'd merge."

**Sharing.**
17. *"Alice shares a 10k-file folder with Bob. What's stored?"* → ACL on folder + parent-chain eval with cache + reverse index. Anti: ACL row per file × per user.
18. *"Bob's 'Shared with me' — query?"* → reverse-index `(user_id, namespace_id)`, event-driven. Anti: full ACL scan.
19. *"Link sharing — how?"* → long opaque token → file_id with expiry; revoke = token delete.

**Versioning & reliability.**
20. *"How is a version stored?"* → ordered list of chunk hashes; old versions hold references.
21. *"Version GC?"* → refcounted chunks; mark-sweep after retention; soft-delete window.
22. *"Durability target?"* → 11×9s via Reed-Solomon + cross-region + scrub.
23. *"Metadata outage?"* → read-only (cached metadata + blob store); uploads queue.
24. *"Multi-region — blobs and metadata where?"* → blobs nearest + cross-region replication; metadata Spanner; reads local, writes leader-region per namespace.
25. *"What dominates monthly cost?"* → storage > egress > metadata QPS; dedup is the lever.

---

## 4. Where to dig deeper (interviewer's picks)

Pick 2 of 3. These produce quotable packet moments.

### Deep dive A — Chunking & dedup

**Phrasing.** "User saves a 100MB file. Now they save it again after editing 1 byte at the start. What happens server-side?"

**L5 shape.** "Chunk into ~4MB blocks, hash with SHA-256, upload only new ones." Correct skeleton; gap: fixed-size chunking *breaks* on a 1-byte insert at offset 0 — every chunk shifts, every hash changes, full re-upload. L5s often don't notice.

**L6 shape.** Same skeleton, *plus*: "Content-defined chunking — FastCDC or Rabin. Avg 4MB, min 1MB, max 8MB; boundary = low-bit pattern on rolling hash. A small edit at the front invalidates the chunks immediately around it; the rest still hash identically and re-use. That's what makes delta sync viable on real networks. Trade-off: variable-size complicates range reads, but Drive's read pattern is sequential-from-zero, so we pay nothing. Dedup: ~30% intra-user, ~50% cross-user on the long tail, blended ~35%. That's the number that justifies chunk-index complexity — without dedup this is just chunked S3."

**Anti-signal.** "Compress chunks with gzip" (compression ≠ dedup). "Diff on the server" (no — diffs are client-side from the chunk-hash list).

**Packet quote.** *"Candidate proposed content-defined chunking via FastCDC at ~4MB unprompted, articulated the 1-byte-insert-cascade failure mode of fixed-size, and committed to ~35% blended dedup with intra/cross-user split."*

### Deep dive B — Sync protocol

**Phrasing.** "Desktop client closed for a week. User opens laptop, 50GB across 200 shared namespaces. What does the client do, what does the server send?"

**L5 shape.** "Client polls for changes since last sync timestamp; server returns changed files." Doesn't scale at 100M clients × 60 polls/hour × 200 namespaces. "Polls how?" → "every minute" with no math behind it.

**L6 shape.** "Each namespace — user root or shared folder — is a *change journal* with monotonic rev per mutation. Client persists `(namespace_id, last_seen_rev)` for each subscribed namespace. On reconnect, opens **one** long-poll/WebSocket multiplexing all namespaces, sends rev vector; server streams journal entries since each rev — `created@17`, `deleted@19`, `edited@22`. Edit entries carry new chunk-hash lists. Client diffs against local chunks, pulls only new chunks via CDN edge. Steady-state push: every mutation publishes to pub-sub keyed by namespace_id; subscribed clients notified in ~hundreds of ms. Poll fallback every few minutes catches missed notifications. Conflict resolution: LWW + conflict copy — explicitly *not* merging binary."

**Anti-signal.** "WebSocket per file" (non-starter at 100M × 100k). "We use Kafka" — naming a queue doesn't answer how the *client* knows.

**Packet quote.** *"Candidate designed a namespace-keyed monotonic-revision change journal with client-persisted rev vector, single multiplexed long-poll, and pub-sub fanout — unprompted. Articulated why per-file connections don't scale at 100M clients."*

### Deep dive C — Sharing & permissions

**Phrasing.** "Alice has a folder with 10k files, shares it with Bob's 500-person group. Carol, inside the group, re-shares one file with external Dan. ACL data model and read path for Dan?"

**L5 shape.** "ACL table `(node_id, principal_id, role)`. Look up ACL row for node + Dan; if missing, walk parent chain." Correct enough but doesn't address "shared with me" or invalidation.

**L6 shape.** "Two structures. **ACL graph** on each node: `node_id → [(principal, role)]` where principal = user/group/link-token. Inheritance walks parent chain; union group memberships. Eval at request time with a *path cache* — `(user, node) → role` cached tens of seconds with explicit invalidation on any ACL change in the path. **'Shared with me' reverse index** keyed by `user_id → [namespace_id]`, event-driven from share/unshare; eventually consistent (seconds) because direct link still works. Trade-off: write amplification on group share (500 rows for a 500-person group), accepted because reads are 10× writes and shared-with-me is on every home-screen render. Carol→Dan: explicit ACL entry on the file + one row in Dan's reverse index. Dan's read: token-auth → metadata fetch → ACL eval (cache hit on explicit grant) → chunk-hash list → CDN pulls. Path eval bounded by depth ≤ 20."

**Anti-signal.** "JOIN ACL on every read" — at 10M ACLs × 1M reads/sec, postmortem channel. "Cache forever" with no invalidation — stale-ACL security regressions end careers.

**Packet quote.** *"Candidate split the ACL model into authoritative graph (parent-chain eval with bounded path cache + explicit invalidation) and denormalized shared-with-me reverse index (eventually consistent, event-driven). Articulated write-amplification trade-off on group share."*

---

## 5. Watch-outs / common traps

**Candidate traps.**
- Blobs in the database; interview effectively over by minute 18.
- Fixed-size chunking with no awareness of the 1-byte-insert cascade.
- No sync protocol at all — most common L5 gap.
- ACLs as one table queried per request; no caching, no denormalization.
- Versioning never connected to chunking; quadratic storage.
- Designing Docs by accident — OT/CRDT for binary "concurrent edits."
- No GC story.
- Performing knowledge — names FastCDC but can't say *why* CDC beats fixed.
- Forgetting the client's local chunk cache; designing upload-everything protocols.

**Interviewer traps (mine).**
- Letting them spend 25 min on upload API. Prompt by minute 30 if sync hasn't started.
- Not forcing a chunk-size + dedup *number* — packet stays fuzzy, committee discounts.
- Letting them avoid sharing because it's hard.
- Over-prompting on chunking before 5 min of silence — contaminates the signal.
- Engaging on Docs collab; redirect once: "out of scope, files are opaque."
- Forgetting multi-region — Drive is global; not asking leaves L6 signal on the table.

---

## 6. The golden answer (what a strong L6 candidate produces)

What I want to see by minute 50. Strong L6 hits ~70% explicitly, the rest implied.

### Functional requirements

Upload/download up to 5GB; folder hierarchy with rename/move/soft-delete (30-day trash); sharing per-file and per-folder, per-user/per-group/anonymous-link with expiry, read-only and editor roles; version history (100 or 30 days, whichever larger); desktop/mobile sync with offline-edits queue; basic name search (full-content async, out of critical path).

**Out of scope (named):** real-time collab editing (Docs); cross-user binary merge; client-side E2EE in v1 (with dedup trade-off acknowledged).

### Non-functional with numbers

- 1B registered, 100M DAU, 5M peak concurrent sync clients.
- Files: avg 1MB, p50 200KB, p99 50MB, max 5GB. Avg user ~30k files, ~100GB stored.
- Workload: 10:1 r:w; ~500M mutations/day → ~6k writes/sec avg, ~30k peak; reads ~60k/sec avg, ~300k peak.
- Latency: metadata p99 < 200ms; chunk first-byte p99 < 300ms (CDN edge).
- Durability: 11×9s blobs (erasure + cross-region + scrub).
- Availability: 99.95% API; 99.9% sync notification; metadata outage → read-only, not full outage.
- Storage: with ~35% dedup, ~65% of nominal — tens of EB at steady state.

### Capacity (napkin)

- New bytes/day: 500M × 1MB = 500TB raw → ~325TB net → ~120PB/year.
- Reads: 5M concurrent × ~10 chunk reads/min = ~830k/sec; CDN absorbs most, origin ~100k/sec.
- Metadata QPS: ~10× mutations → ~300k peak.
- Chunk index: ~30B unique chunks → ~30TB index, sharded on hash prefix.

### High-level architecture

```
                            +------------------+
                            |   CDN / Edge     |  <-- chunk read acceleration
                            +--------+---------+
                                     ^
              clients (web / desktop / mobile)
                  |   |   |
                  v   v   v
            +-----------------+        +---------------------+
            |  API Gateway    |<------>|  Auth / Identity    |
            |  (REST + gRPC)  |        +---------------------+
            +--------+--------+
                     |
        +------------+------------+-------------------+
        |                         |                   |
        v                         v                   v
 +-------------+        +------------------+   +----------------+
 |  Metadata   |        |  Chunk Service   |   |  Sync Notif    |
 |  Service    |        |  (upload /       |   |  Service       |
 |  (Spanner)  |        |   download /     |   |  (WebSocket /  |
 +------+------+        |   chunk index)   |   |   long-poll)   |
        |               +---------+--------+   +-------+--------+
        v                         v                    v
 +-------------+        +------------------+   +------------------+
 |  Metadata   |        |  Blob Store      |   |  Pub-Sub Fanout  |
 |  Spanner    |        |  (Colossus / S3) |   |  (per-namespace) |
 +-------------+        +------------------+   +------------------+
        |                         ^
        v                         |
 +-------------+                  |
 |  Chunk Idx  |------------------+
 |  KV (sharded)|  (hash -> blob location, refcount)
 +-------------+

 Async pipelines: search indexer | GC sweeper | shared-with-me index updater
```

### Storage split

- **Blob store** (Colossus / S3-shaped): immutable content-addressed chunks. Key = SHA-256. Reed-Solomon (e.g. 6+3) across racks; cross-region async replication.
- **Metadata store** (Spanner): the file system. Tables: `node` (file/folder), `revision` (per-mutation, with chunk-hash list), `acl`, `namespace_journal`. Strong consistency; atomic txns across `node` + `revision`.
- **Chunk index** (sharded KV — Bigtable-class): `chunk_hash → (blob_location, refcount, created_at)`. p99 < 30ms. Sharded by hash prefix.
- **Share reverse index**: `user_id → [namespace_ids]`. Event-driven from ACL changes. Eventually consistent within seconds.

### Chunking

Content-defined chunking via FastCDC (Rabin acceptable). Avg 4MB, min 1MB, max 8MB; boundary = low-bit pattern on rolling hash. SHA-256 as blob-store/chunk-index key. CDC vs fixed: 1-byte insert at offset 0 of a 1GB file invalidates ~256 fixed chunks (1GB re-upload); under CDC it invalidates 1–2 chunks. Dedup refcounted in the chunk index. Trade-off accepted: dedup precludes client-side E2EE — ship dedup default, offer E2EE as enterprise tier with 2–3× storage tax.

### Versioning

Revision = `(revision_id, file_id, parent_revision_id, chunk_hash_list, author, timestamp, size)`. New version = O(diff) bytes + O(1) metadata. **Versioning is free given dedup.** Retention: 100 or 30 days. GC: mark-and-sweep against the chunk index — refcount-- on revision delete; chunk at refcount 0 past a 7-day soft-delete → blob deletes.

### Upload protocol (resumable, dedup-aware)

```
client                                     server
  | --- POST /upload/begin {path} -------->|
  | <-- {upload_id} ---------------------- |
  |                                        |
  | (CDC chunk; SHA-256 each)              |
  | --- POST /chunks/check {hashes} ------>|
  | <-- {missing: [h3, h7, h12, ...]} ---- |  <-- already-have chunks save bandwidth
  |                                        |
  | --- PUT /chunk/h3  [bytes]          -->|
  | --- PUT /chunk/h7  [bytes]          -->|     (parallel; resumable per chunk)
  |     ...                                |
  | --- POST /upload/commit                |
  |     {chunk_hash_list, metadata,        |
  |      parent_revision_id}            -->|
  |                                        |  (atomic txn: insert revision,
  |                                        |   refcount++, publish event)
  | <-- {revision_id} -------------------- |
```

Properties: median upload = bytes-changed, not bytes-total. Each chunk PUT independent and idempotent (content-addressed). Network drop on chunk 47/200 → resume from 47. Uncommitted uploads → orphans GC'd after 24h TTL.

### Sync protocol (the L6 piece)

- **Namespace = sync unit.** User root + each shared folder root.
- **Change journal per namespace** — Spanner table partitioned by namespace_id, append-only, monotonic `rev`. Every mutation (create/edit/delete/rename/ACL change) writes one row.
- **Client persists `(namespace_id, last_seen_rev)`.** On reconnect, opens one multiplexed WebSocket; server streams journal entries since each rev.
- **Steady-state push.** After metadata commit, publish to pub-sub keyed by namespace_id. Subscribed clients notified in ~hundreds of ms; pull only the rev delta.
- **Edit deltas use chunk-hash lists.** Client diffs against local chunks, pulls only missing chunks (CDN edge).
- **Poll fallback** every few minutes catches missed notifications. Correctness insurance, not hot path.
- **One connection per client**, multiplexing all namespaces. 5M concurrent × 1 conn fits on O(thousands) of fanout nodes.
- **Offline edits.** Persist pending mutations locally; replay on reconnect. Each mutation idempotent: chunk uploads content-addressed; commits carry `parent_revision_id`.

### Sharing / permissions

- **ACL graph on each node:** rows `(principal_id, role, granted_at, granted_by)`. Principal = user / group / link-token.
- **Eval** walks parent chain; unions in group memberships. Bounded by folder depth (~20). Cached per `(user, node)` for tens of seconds with explicit invalidation on any ACL change in the path.
- **'Shared with me' reverse index** — `user_id → [namespace_id]`, event-driven from ACL events. Eventually consistent (seconds). Write amplification on group share accepted because reads 10× writes.
- **Link sharing.** Long opaque token (128 bits) → `(node_id, role, expiry, owner)`. Revoke = token delete. Token reveals nothing about file_id.
- **Group sharing.** ACL row references group_id; membership resolved via identity service. Group changes invalidate path cache, not ACL rows.

### Concurrent edits

Binary: **LWW + conflict copy preserves the loser.** Commit carries `parent_revision_id`. Metadata txn checks current head — match → commit; mismatch → commit succeeds as a *new* file in the same folder, named `Document (Bob's conflict copy 2026-05-28).docx`. Both visible. Binary merge undefined for most formats. Docs-style OT/CRDT is a different product.

### Search

Out of critical path. Pubsub event on every commit → async indexer reads chunks for indexable types (text/PDF/doc), writes to a separate search index sharded by user. Eventually consistent (seconds–minutes); query path is a separate service returning file_ids.

### Multi-region

- **Blobs** in user's primary region; async cross-region replication for durability + read-locality. CDN edge accelerates the common case.
- **Metadata** in Spanner with synchronous cross-region replication on namespace_journal — a client cannot see a notification for a rev the metadata store hasn't acknowledged. Spanner's geo-tax (tens of ms commit) is real but the alternative (eventual metadata) produces user-visible weirdness.
- **Sync notification** regionally local for connection management; cross-region pub-sub for fanout. Client connects nearest.
- **Failover.** Region loss → reads degrade to next-nearest; writes pause briefly for Spanner leader election in affected partitions (seconds of write unavailability for those namespaces, not global).

### Encryption

At rest: KMS-managed keys per shard; chunks encrypted server-side, transparent to dedup (encryption at storage layer, not chunk layer). In transit: TLS. Client-side E2EE out-of-MVP — enterprise tier accepts loss of cross-user dedup (~2–3× storage cost; we charge).

### Cost

At 100M DAU, monthly: **storage dominates** (~tens of EB × $X/GB); **egress** second (CDN-absorbed; origin is long tail); **metadata QPS** third (Spanner-class at 300k peak is real but small next to storage); sync fanout cheap per message, tail item. **Dedup is the lever** — without it storage is ~50% more, which is the line that doesn't fit on the slide.

### Failure modes & blast radius

- **Corrupt chunk on read.** SHA-256 verify; failure → fetch replica; all replicas fail → data-lost for that chunk (the 11×9s budget). Background scrub catches silent bitrot before user reads.
- **Partial upload.** Orphan chunks → 24h-TTL GC sweep deletes them.
- **Metadata outage.** Reads degrade to cache-served read-only; uploads queue client-side; writes return retry-after; sync pauses. Blob store unaffected — clients still download from cached chunk-hash lists.
- **Sync notification outage.** Clients fall back to poll. Notifications delayed by minutes, not full outage.
- **Sync loop.** Globally-unique mutation_id, `parent_revision_id` on every commit, client-side filesystem-event debounce (50–100ms).
- **Hot namespace.** namespace_journal sharded by namespace_id; hot ones get their own shards; fanout absorbs the read storm; listings paginated.

### Evolution

- **10× growth.** Chunk index re-splits on hash prefix (trivial — content-addressed). Spanner partitions split on namespace_id. Sync service scales horizontally on connection count. Seam needing care: ACL path cache memory; push more into per-region tier, watch invalidation traffic.
- **Enterprise.** Audit log to append-only store, retention policies, legal hold (suspend GC), tenant keys — all layered on metadata service, core architecture unchanged.
- **Team drives.** "Namespace owned by group instead of user." ACL graph, change journal, sync — all handle it. Add per-group quota + admin tooling.
- **Docs.** Composes cleanly — separate service using Drive as persistence for the OT log + periodic snapshots stored as Drive files.

---

## 7. Signals scorecard

| Hire / Strong Hire (quotable in packet) | No Hire / Down-level |
|---|---|
| Split blobs from metadata in the first diagram; named consistency model of each. | Files in the database, or never separated blob from metadata. |
| Committed to chunk size + algorithm by name (FastCDC / Rabin, ~4MB), unprompted. | Hand-waved chunking, or picked fixed and missed the 1-byte-insert cascade even when probed. |
| Articulated dedup savings as a number with intra-/cross-user split; used it to justify chunk-index complexity. | "We'd dedup" with no number or mechanism. |
| Designed sync as namespace-keyed monotonic change journal with client rev vector and single multiplexed connection. | "Client polls every minute" or "WebSocket per file." |
| ACL graph + denormalized 'shared with me' reverse index with explicit eventual-consistency trade-off and cache invalidation. | ACL JOIN at request time; or static cache with no invalidation. |
| Versioning as chunk-list-per-revision with refcounted GC; saw chunking makes versioning free. | "Keep old copies" / quadratic storage; no GC. |
| Volunteered failure modes (corrupt chunk, partial upload, sync loop, metadata outage) with bounded blast radius. | Waited to be asked; failures described without numbers. |
| Scoped out Docs-style merge explicitly; LWW + conflict copies for binary; explained why. | Drifted into OT/CRDT for binary; or tried to design both Drive and Docs. |
| Reasoned about cost — storage dominates, dedup is the lever, E2EE is a 2–3× storage tax. | Treated storage and egress as free. |
| On 10× or multi-region pushback, identified the 1–2 seams, not a redesign. | Started over with a new diagram. |
| Narrated plan and budget. | Drifted; surprised when time was called. |
| Calibrated disagreement: held when defensible, updated cleanly when not. | Caved on every pushback, or dug in defensively. |

---

*Closing note for the packet.* The two sentences I want to write: **"Designed content-defined chunking with FastCDC and ~35% blended dedup unprompted, justified as the cost-model lever"** and **"Designed sync as a namespace-keyed monotonic change journal with multiplexed long-poll, articulating why per-file connections don't scale at 100M clients."** Those two sentences honestly from the transcript = Hire at L6. With reservations or prompting = Hire at L5 / Lean No Hire at L6.
