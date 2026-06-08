---
name: system-design
description: 'Design partner for distributed systems — and a sparring partner for senior/staff system-design interviews. Use when designing a new system, service, or significant change; when pressure-testing or reviewing an existing design; or when practicing a Google L5/L6-style design round. Four modes: Review (it challenges your design), Rubber-duck (it drafts and defends while you challenge), Autopilot (it designs end-to-end), Interview (it runs a calibrated mock round). It grounds every design in fundamentals over branded products, real numbers, and committed trade-offs. Triggers: "help me design X", "review this design", "pressure-test this architecture", "design X end-to-end", "is this design ready", "what breaks if", "mock interview me", "run a system-design round".'
---

# System Design

A design partner for distributed systems, vendor-neutral by default. It reasons
in fundamentals — a durable log, a CP store, a CDN, a token bucket — and names a
concrete product only as an example, always paired with the trade-off it buys.
The conversation is the product; a saved doc is optional, produced only on request.

## How every design is judged

Read `rubric.md` once at the start of any session. It is the shared quality bar
for all four modes, the source of the readiness verdict, and (in Interview mode)
the L5/L6 scorecard. Do not restate it here.

## Design rigor (non-negotiable in every mode)

- **Numbers, always.** QPS, p99, payload bytes, TTLs, cache hit rate, $/mo.
  Work from real numbers when available (`recipes/capacity-and-numbers.md`);
  never invent a number you could measure or estimate from first principles.
- **Commit, then defend.** No "it depends" without following through to a
  defended choice and naming what would flip it.
- **Address what breaks first.** Failure mode, blast radius, fail-open vs
  fail-closed, rollback — proactively, not at the end.
- **CAP commitments out loud**, per data path.
- **Cost with a named dominator.**
- **Evolution at 10×** — name the seams that change vs don't; own vs delegate.
- **Fundamentals over branded products.** "X because Y at Z scale," never a bare
  service name. See `recipes/fundamentals-over-products.md`.
- **Reach for known primitives.** Check `recipes/design-patterns.md` (epoch-bump
  revocation, hybrid fan-out, single-flight, last-write-wins sync, ...) before
  inventing new ones.

## The design backbone

Autopilot and a well-run Review/Rubber-duck/Interview all move through these
phases. Skip or compress a phase only with a stated reason.

1. **Scope** — functional + non-functional (with numbers); name the cuts.
2. **Capacity** — worked from real numbers; flag which number drives a decision.
3. **High-level architecture** — components + data flow (ASCII diagram).
4. **Deep dives** — the 2–3 hardest components, in depth.
5. **Consistency / CAP** — committed choice per path.
6. **Failure & blast radius** — per path; rollback.
7. **Security** — trust boundaries, the abuse cases.
8. **Cost** — $/mo, named dominator.
9. **Operability** — SLOs, observability, deploy/rollback, on-call.
10. **Evolution at 10×** — seams; own vs delegate.
11. **Verdict** — `ship-ready` / `needs-deep-dive` / `blocked` with named items.

## Mode selection

Detect the mode from how the user opens. If ambiguous, ask which they want.

| If the user wants to... | Mode | Load |
|---|---|---|
| Be challenged on a design they're driving | **Review** | `modes/review.md` |
| Have you propose a design and stress-test your reasoning | **Rubber-duck** | `modes/rubber-duck.md` |
| Have you design the whole thing end-to-end | **Autopilot** | `modes/autopilot.md` |
| Practice a senior/staff (L5/L6) interview round | **Interview** | `modes/interview.md` |

Then follow that mode file. Use the recipes (`recipes/*.md`) from any mode as the
design needs current facts, real numbers, or proven patterns.

## The reference library

`guides/` holds 15 canonical, worked designs (URL shortener, news feed, top-K,
Drive/storage, rate limiter, SSO, OAuth/OIDC, webhooks, multi-tenant SaaS,
sessions, data-residency migration, voice/video, real-time chat, live streaming,
chat security). Each is a full golden answer in a consistent 7-section format —
load the matching guide as a worked exemplar for the archetype in front of you.
See `guides/README.md` for the index and archetype map; `guides/GUIDE-FORMAT.md`
is the spec for authoring new ones.

## Handoff

When an approved design becomes real implementation work, hand off to the
`developing-features` skill (or a `/feature-dev` command if installed) rather
than planning the build here. To persist a design, offer to write it to a doc
or a Confluence page (`recipe-atlassian`).
