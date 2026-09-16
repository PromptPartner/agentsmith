---
name: grill-with-docs
description: Grill a fuzzy, single-session repository change into shared language, recorded decisions, and a handoff-ready plan. Use when the operator asks to grill or stress-test a plan or design in a repository; route multi-session uncertainty to wayfinder.
compatibility: Requires an Agent Skills-compatible coding agent with filesystem access.
---

# Grill with docs

Resolve a change's design tree with the operator while recording each answer where a fresh session
can use it. Stop at a handoff-ready plan; implementation is a separate unit of work.

## Route

- Use this workflow when a repository change is fuzzy but can be settled in one session.
- Use `wayfinder` when the destination spans sessions, has dependent decisions that need separate
  research, or cannot yet become one implementation plan.
- Use the ordinary plan flow when scope, language, and consequential choices are already settled.

## Establish the tree

1. Read the tracked item, existing plan/spec, `CONTEXT-MAP.md`, relevant `CONTEXT.md` files, ADRs,
   and the code or assets that constrain the change. Facts come from the repository; decisions come from the operator.
2. Locate the project's plan convention. Reuse an existing change plan; otherwise create one from
   `.harness/templates/plan.md`, `templates/plan.md`, or the same shape at `.planning/<slug>.md`, in
   that order of availability.
3. Map the unresolved choices as a design tree. Its **frontier** is the independent questions whose
   prerequisites are settled now.

## Work the frontier

Ask a small numbered round from the frontier. For each question, state why it matters, the real
options and trade-offs, and your recommended answer. Then wait for the operator's decisions.

After each answer round:

1. Recompute the tree. Cross-check claims against the repository and surface contradictions.
2. Record every settled decision in the plan with its original precision: boundaries, ordering,
   defaults, failure behaviour, numeric constraints, and evidence requirements.
3. Record resolved project language and qualifying ADRs before the next question round.

Repeat until the frontier is empty. A question that depends on an unresolved answer stays off the
current frontier.

## Durable artifacts

### Plan

The plan is the complete decision ledger and implementation handoff. Keep its scope, approach,
risks, verification, and done criteria current after each round. Place rationale once: in the plan
for ordinary choices, or in an ADR for a qualifying architectural choice with a link from the plan.

### Project language

When a project-specific term resolves, update the relevant `CONTEXT.md` immediately using
[`CONTEXT-FORMAT.md`](CONTEXT-FORMAT.md). A root `CONTEXT-MAP.md` selects the bounded context; without
one, use the root glossary. Create the file lazily on the first qualifying term.

### Architectural decisions

Create an ADR only when the choice passes all three gates in [`ADR-FORMAT.md`](ADR-FORMAT.md): hard
to reverse, surprising without context, and the result of a real trade-off. Create `docs/adr/`
lazily and preserve the repository's existing ADR convention when one exists.

## Completion

Offer the plan for confirmation only when the frontier is empty, every settled decision is durable,
repository contradictions are resolved or explicit, and the plan defines end-to-end evidence. The
session completes when the operator confirms shared understanding. Report the plan path, glossary
and ADR changes, and whether the next route is implementation or `wayfinder`.

---
*Adapted from Matt Pocock's `grilling`, `domain-modeling`, and `grill-with-docs` skills
([MIT](https://github.com/mattpocock/skills/blob/main/LICENSE), 2026). AgentSmith makes the workflow
self-contained and keeps every settled decision in the repository plan.*
