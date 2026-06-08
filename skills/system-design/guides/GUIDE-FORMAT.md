# Interview-Guide Format Spec

> The contract every guide in this `guides/` directory follows. Read this
> before authoring a new guide. A guide that doesn't match this shape is wrong,
> no matter how good its content.

The guides are written **from the interviewer's chair** for a 1-hour senior/staff
(Google L5/L6-calibrated) system-design round. They are run-the-round playbooks
with a baked-in golden answer — not candidate study notes, not templates to read
aloud. Voice: a Senior Staff engineer who has heard hundreds of attempts and has
internal calibration on what good looks like.

The two persona docs are the calibration source of truth:
- `../personas/interviewer.md` — what the interviewer scores, the packet, the
  L5-vs-L6 bar, signals/anti-signals.
- `../personas/candidate.md` — how a prepared candidate runs the hour; the
  signals they try to produce.

---

## The 7-section structure (mandatory, in this order)

Every guide is a single markdown file named `NN-slug.md`. Header:

```
# Question N: <Human Title> (<one-line archetype tag>)

> 1–4 line interviewer's-framing blurb. Name the archetype this is the
> anchor for, and why its calibration value is judgment-under-constraint,
> not knowledge recall.
```

### 1. Why this question (interviewer's framing)
- 3–6 bullets on what the question *actually* tests (the deltas that separate
  levels, not the surface topic).
- `### What "Hire" looks like at each level` — an **L5 Hire** paragraph and an
  **L6 Hire** paragraph (L6 = "all of the above, plus…"). The L6 delta is the
  single most load-bearing thing on the page.
- `### Classic downlevel traps` — a numbered list (3–5) of the specific moves
  that sink candidates, each with the packet consequence.

### 2. The 60-minute plan
Time-sliced, using the canonical budget: `0–5 Intro · 5–15 Requirements & scope ·
15–25 Capacity + high-level design · 25–45 Deep dives · 45–55 Evolution /
curveball · 55–60 Wrap`. For each slice give three things: **Say** (verbatim
lines), **Listen for** (the signal), **Push back when** (the trigger + the line).
Mark which deep dives are *mandatory* vs candidate-chosen.

### 3. Probing prompts (the kit)
A table: `| Prompt | Signal hunted |` (12–16 rows). Each prompt is a line the
interviewer can drop verbatim; each maps to one specific signal it hunts.

### 4. Where to dig deeper (interviewer's deep-dive picks)
2–3 deep dives (label them A / B / C). For **each**:
- **Phrasing** — the exact question the interviewer asks.
- **Strong L5 answer** — what a competent L5 produces.
- **Strong L6 answer** — "all of the above, plus…" with the numbers, named
  mechanisms, and the move that earns the level.
- **Anti-signal** — the answer that flags a downlevel.
- **Packet quote** — the verbatim sentence the interviewer would write.

### 5. Watch-outs / common traps
Two sub-lists: **Candidate-side** (anti-signals) and **Interviewer-side** (your
own traps — over-prompting, letting them dwell, not driving to the mandatory
scenario, etc.).

### 6. The golden answer (what a strong L6 candidate would produce)
The reference walk-through, numbered `6.1`, `6.2`, … Include at minimum:
functional requirements (committed scope, out-of-scope cuts named aloud);
non-functional requirements **with numbers** (a table); capacity estimation
(worked; call out *which* numbers changed a decision); API design (code block);
data model; high-level architecture (**ASCII diagram**); the mandatory deep-dive
components in full depth; multi-region / consistency commitments (CAP choices out
loud); cost (back-of-envelope $/month, name the dominator); failure modes & blast
radius (table); evolution at 10× (seams that change vs don't).

### 7. Signals scorecard
A table mapping packet-quotable evidence → level call (`Strong No Hire` /
`No Hire` / `Lean No Hire` / `Hire L5` / `Hire L5 / Lean L6` / `Hire L6` /
`Strong Hire L6`). Left column is transcript evidence; right is the call.

### Sources
Bulleted, with URLs. Mix of canonical interview resources, primary papers/specs
where relevant (RFCs for protocol questions), and practitioner accounts.

---

## Voice & calibration rules (true for all guides)

1. **The packet is the test.** Every deep dive ends in a packet-quotable
   sentence. Optimize content for what the interviewer can write down: specific
   numbers, named trade-offs, committed decisions.
2. **Numbers, always.** QPS, p99, payload bytes, TTLs, cache hit rate, $/month.
3. **Commit, then defend.** The golden answer never says "it depends" without
   following through to a defended choice and naming what would flip it.
4. **L5 vs L6 is the spine.** Every section carries the delta. L6 = drives the
   room, volunteers ops/cost/abuse/evolution unprompted, states CAP commitments,
   names what they'd delegate vs own.
5. **Address what breaks first.** Failure domain, blast radius, rollback,
   fail-open vs fail-closed — proactively, not as a min-55 footnote.
6. **Specifics beat products.** "We need X because Y at Z scale," never "we'd use
   <branded product>" without the cost/trade-off.

## Formatting conventions
- Single `.md` file per question, named `NN-slug.md`.
- ASCII box-and-arrow diagrams for architecture (match existing guides).
- Tables for: NFR/numbers, probing-prompt kit, failure modes, scorecard.
- Hard-wrap prose to roughly the width of the existing guides for readability;
  tables and code blocks run full width.
- Close with a one-line pointer to the next/related guide if natural.

---

## Extending the library

Each new guide should be **canonical** (a clean reference design framed around a
well-known product archetype) and **calibrated to L5/L6**. Frame around the
fundamentals, not a vendor; mention concrete products only as justified examples,
paired with the trade-off they buy. When a guide leans on a reusable primitive
(see `../recipes/design-patterns.md`), distill the *pattern* — never reproduce
any organization's confidential specifics. After a new guide lands, add it to
`README.md` and update the archetype map.
