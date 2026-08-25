---
name: wayfinder
description: Wayfind a foggy, multi-session effort into an accepted repository spec and separate implementation-ticket drafts. Use when the destination is known but important decisions, dependencies, or scope are not yet clear enough to implement safely.
---

# Wayfinder

Turn uncertainty into a decision-complete spec. The map plans the route; it does not execute the
destination.

## Invariants

- **Destination:** the observable end state this effort is finding a route to.
- **Decision map:** named questions and their dependency edges. A decision produces an answer, not
  a slice of implementation.
- **Frontier:** the sharp, unresolved, unblocked decisions that can be taken next.
- **Fog:** in-scope uncertainty that cannot yet be phrased as a precise question. Fog graduates to
  a decision only when the question is sharp.
- **Decision index:** one context pointer and one-line rationale per resolved decision; the detail
  lives in its ticket or linked research artifact.
- **Non-goal:** a deliberate scope boundary. It never graduates from fog unless the destination is
  explicitly redrawn.

Resolve one decision per session. Parallel research may inform that decision, but does not silently
resolve another one.

## Chart

1. Read the tracked item, existing plans/specs, and `docs/14-project-tracker-guide.md` when present.
   Determine the active tracker-write policy before any tracker action.
2. Name the destination and non-goals. Stop if the effort is already small and decision-complete;
   use the ordinary plan flow instead.
3. Create `docs/specs/<slug>.md` from `.harness/templates/wayfinder-spec.md` (or
   `templates/wayfinder-spec.md` in the harness source checkout); reproduce that shape only when
   neither is available. Initial status is always `draft`.
4. Add every sharp question to the decision map, wire its blockers, and identify the frontier.
   Keep unshaped uncertainty in Fog. Draft a decision ticket for each mapped decision.
5. If tracker writes are unauthorized, put paste-ready ticket bodies in the spec and surface them
   to the operator. A connected or named tracker grants no write permission.
6. Stop after charting. The completed draft spec and ticket drafts are the evidence for this step.

## Advance

1. Load the spec at low resolution: destination, frontier, fog, non-goals, and decision index.
2. Select one frontier decision. Research, prototype, or discuss only enough to answer its stated
   question. Human-preference decisions require the human's actual answer.
3. Record the answer and rationale once, in the decision's ticket draft or authorized tracker item.
   Add only a linked gist to the Decision index.
4. Recompute dependencies. Graduate newly sharp fog into decisions; move newly excluded work to
   Non-goals or Explicit deferrals with a reason.
5. Stop after one decision. Completion means its answer is recorded and the map reflects the new
   frontier without duplicate rationale.

## Terminal-spec gate

A spec can be offered for acceptance only when:

- the destination and non-goals are concrete;
- no unresolved in-scope decision or blocking fog remains;
- each resolved decision has a rationale and context pointer;
- evidence/acceptance requirements cover the destination end to end; and
- implementation-ticket drafts are separate, independently executable scopes.

Present the spec as `draft` and ask the operator to accept or revise it. Only an explicit operator
acceptance may change `status` to `accepted`; record that human in `accepted_by` and the acceptance
time in `accepted_at`. An agent's own evaluation cannot accept it. Acceptance closes the decision
item and unlocks planning/execution against the separate implementation tickets.
Tracker consent still governs closing or creating items: when writes are unauthorized, provide the
close comment and implementation-ticket bodies as paste-ready drafts.

## Implementation boundary

An implementation ticket names one deliverable, its scope, dependencies, and proof. It never
inherits the decision ticket's identity. Wayfinder ends at the accepted spec and ticket drafts;
start implementation only from a separately tracked implementation ticket and the operator's
normal execution instruction.

---
*Adapted from Matt Pocock's
[`wayfinder`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/engineering/wayfinder/SKILL.md)
(MIT). Agentsmith keeps its decision-map concepts while making the terminal artifact repository-
native and preserving tracker consent.*
