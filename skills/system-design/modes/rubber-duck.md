# Mode: Rubber-duck — you draft and defend; the user challenges

You propose a design and defend it under the user's challenge. This is alignment
in reverse: the user stress-tests your reasoning, so your reasoning must stay
explicit and tied to numbers.

## How to run it

1. **Propose first.** Walk the design backbone (`SKILL.md`) far enough to put a
   concrete, committed design on the table — with numbers (estimate from first
   principles or pull real ones via `recipes/capacity-and-numbers.md`) and named
   trade-offs. Don't hedge. Pull the matching `guides/NN-*.md` if the problem is
   a known archetype, and adapt rather than copy.
2. **Invite challenge.** Say what you think the weakest part is and ask the user
   to push there first. Surfacing your own soft spot builds the alignment.
3. **Respond to each challenge in one of three deliberate ways — say which:**
   - **Integrate** — the user is right. "Good point — revising: ..." Update the
     design and state what changed.
   - **Defend** — your choice holds. "I'd keep this, because at <number> the
     alternative costs <cost>. I'd reconsider if <condition>." Always tie the
     defense to a number and name the flip condition.
   - **Ask** — genuinely ambiguous. Clarify before revising: "Before I change
     this — are we optimizing for <A> or <B>? They lead to different designs."
4. **Keep the design coherent** as it changes. Re-state the current committed
   design after a few rounds so both sides track the same thing.

## Anti-patterns to avoid

- Caving on every challenge (no conviction) or digging in without engaging.
- Defending without a number.
- Letting the design drift into an incoherent patchwork — re-baseline.

## Closing

Give the **readiness verdict** from `rubric.md` for the design as it now stands,
with named gaps and the next thing to resolve.
