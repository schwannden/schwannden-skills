# Design Rubric — the shared quality bar

Every mode holds a design to these nine dimensions. Keep pushing on a dimension
until it is either addressed concretely or explicitly cut. A cut is a valid
answer; silence is not.

| # | Dimension | The bar | A weak answer sounds like |
|---|-----------|---------|---------------------------|
| 1 | **Scope committed** | Functional + non-functional requirements; non-functionals carry numbers; out-of-scope items named aloud. | "It should be scalable and secure." |
| 2 | **Capacity grounded** | Worked from real numbers; names *which* number changed a design decision. | "We'll handle a lot of traffic." |
| 3 | **Consistency / CAP** | The trade-off stated as a committed choice (AP vs CP) per data path. | "It depends." (with no follow-through) |
| 4 | **Failure & blast radius** | Fail-open vs fail-closed per path, blast radius named, rollback path. | "We'll add retries." |
| 5 | **Security** | Trust boundaries; SSRF/open-redirect; account-takeover; what is delegated vs owned. | "We'll use HTTPS and auth." |
| 6 | **Cost** | Back-of-envelope $/mo with a named dominator. | (cost never mentioned) |
| 7 | **Operability** | SLOs, observability (metrics/logs), deployment + rollback, on-call burden. | "We'll add monitoring later." |
| 8 | **Evolution at 10×** | Which seams change vs stay; what to own vs delegate to another team. | "We'd rebuild it." |
| 9 | **Fundamentals over products** | "X because Y at Z scale," not a bare service name. | "We'd use <branded product>." (no why) |

## Readiness verdict (Review / Rubber-duck / Autopilot)

Close every design with one verdict, always concrete:

- **`ship-ready`** — every dimension addressed or deliberately cut; no open risk
  that would surprise on-call.
- **`needs-deep-dive`** — sound direction, but list the specific dimensions still
  open as named, actionable gaps (e.g. "revocation propagation SLA unquantified",
  "no cost dominator named").
- **`blocked`** — a named blocker makes the current direction unsafe to build
  (e.g. "routing takes caller-supplied hosts → SSRF"; "stateless tokens with no
  revocation path").

A verdict without named items is not a verdict. Each gap/blocker must point at a
dimension and say what would close it.

## Interview scorecard (Interview mode)

In a mock round, the nine dimensions map onto a level call. The unit of evidence
is a **packet-quotable sentence** — a specific number, a named trade-off, a
committed decision the interviewer could write down verbatim. Vague impressions
("seemed to understand sharding") do not count.

The spine is **L5 vs L6**. The same design earns different levels:

- **L5 Hire** — commits to numbers unprompted; clean high-level design with
  justified technology choices; goes deep on 2–3 components without being asked;
  discusses failure modes for them.
- **L6 Hire** — all of the above, **plus** *drives the room* (no looking for
  guidance), volunteers operability/cost/abuse/evolution unprompted, states CAP
  commitments per path, and names what they'd own vs delegate to another team.

| Transcript evidence | Call |
|---|---|
| Hand-waves scale; names products without trade-offs; no failure thinking. | **Strong No Hire** |
| Clean diagram but stays shallow on the hard component; ops/cost absent. | **No Hire** |
| Solid components but had to be driven; numbers thin; no evolution story. | **Lean No Hire** |
| Commits to numbers, justifies tech, deep-dives 2–3 components, names failure modes. | **Hire L5** |
| All of L5, plus surfaces one of {cost trade-off, blast radius, migration/rollout} unprompted. | **Hire L5 / Lean L6** |
| Drives the room; CAP per path; ops + cost + abuse volunteered; names own-vs-delegate. | **Hire L6** |
| All of L6, fluent under pushback (integrates/defends with a number/asks), and reframes scope at 10×. | **Strong Hire L6** |

A level call without packet-quotable evidence is not a call. Anchor each call to
a sentence from the transcript.
