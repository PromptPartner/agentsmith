---
name: wayfinder
description: Wayfind a foggy, multi-session effort into an accepted repository spec and separate implementation-ticket drafts. Use when the destination is known but important decisions, dependencies, or scope are not yet clear enough to implement safely.
compatibility: Requires an Agent Skills-compatible coding agent with filesystem access.
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

**Attended mode (default):** resolve one decision per session with the operator. Parallel
research may inform that decision, but does not silently resolve another one.

**Unattended mode** (a batch without the operator): resolve several decisions in one session when
an agent can answer them, and record the rationale of each one separately. A decision that needs
the human's preference is never answered by an agent: put it under "Needs operator" with the
decisions it blocks. It blocks only those; the rest of the map moves on.

## Pipeline and route

Wayfinder covers part of the development pipeline. Each stage leaves an artifact:

0. Goal: the goal and problem restated in the spec.
1. Research: `docs/research/<slug>.md`, premise reproduced; named in `research:`.
2. Shape: the draft spec in `docs/specs/<slug>.md`.
3. Route: `route:` with a one-line reason.
4. Spec review: a verdict file from a reviewer who did not draft the spec, named in
   `reviewer_receipt:`, plus the "Review resolution" section.
5. Accept: the operator only.
6. Implement: `autonomous-run`, or an attended session.
7. Prove: verifier output and `check-specs` output, both shown.
8. Land: commit or pull request with the evidence, by the operator's delivery rule.

Pick the route and record why:

- `direct`: decision-complete, one session, clear "done" (a reproduced bug, a docs fix).
- `grill`: unclear shape, one session, the operator is present; use `grill-with-docs`.
- `wayfinder`: two or more dependent open decisions, several sessions, several subsystems or
  owners, or a change to a data model, security boundary or failure mode.

When unsure, take the heavier route. `direct` still needs research, a spec review and acceptance.
A list of bugs is a numbered checklist of `direct` items, not one pipeline item. AgentSmith's
`docs/28-development-pipeline.md` gives the reasons.

If the `superpowers` plugin is enabled, use its skills only for a stage: this order wins over its
session-start instruction; save its spec as `docs/specs/<slug>.md`; after brainstorming go to
Route, not `writing-plans`; in an unattended batch do not wait for its human review, use the
unattended mode.

## Chart

1. Read the tracked item, existing plans/specs, and `docs/14-project-tracker-guide.md` when present.
   Determine the active tracker-write policy before any tracker action.
2. Name the destination and non-goals, and choose the route as above. Continue here only for
   `wayfinder`.
3. Create `docs/specs/<slug>.md` from `.harness/templates/wayfinder-spec.md` (or
   `templates/wayfinder-spec.md` in the harness source checkout); reproduce that shape only when
   neither is available. Initial status is always `draft`. Fill `research:` and `route:`.
4. Add every sharp question to the decision map, wire its blockers, and identify the frontier.
   Keep unshaped uncertainty in Fog. Draft a decision ticket for each mapped decision.
5. If tracker writes are unauthorized, put paste-ready ticket bodies in the spec and surface them
   to the operator. A connected or named tracker grants no write permission.
6. Stop after charting. The completed draft spec and ticket drafts are the evidence for this step.

## Advance

1. Load the spec at low resolution: destination, frontier, fog, non-goals, and decision index.
2. Select one frontier decision (several in unattended mode). Research, prototype, or discuss only
   enough to answer its stated question. Human-preference decisions require the human's actual
   answer; in unattended mode they go under "Needs operator".
3. Record the answer and rationale once, in the decision's ticket draft or authorized tracker item.
   Add only a linked gist to the Decision index.
4. Recompute dependencies. Graduate newly sharp fog into decisions; move newly excluded work to
   Non-goals or Explicit deferrals with a reason.
5. Stop after one decision in attended mode. Completion means each answer is recorded and the map
   reflects the new frontier without duplicate rationale.

## Terminal-spec gate

A spec can be offered for acceptance only when:

- the destination and non-goals are concrete;
- no unresolved in-scope decision or blocking fog remains;
- each resolved decision has a rationale and context pointer;
- evidence/acceptance requirements cover the destination end to end;
- implementation-ticket drafts are separate, independently executable scopes; and
- `research:`, `route:` and `reviewer_receipt:` are filled, the reviewer did not draft the spec,
  "Review resolution" answers each finding, and `python3 .agentsmith/autonomous-run.py
  check-specs docs/specs/<slug>.md` exits 0.

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
normal execution instruction. The usual successor is `autonomous-run`, which implements one such
ticket against the accepted spec and refuses a spec that fails `check-specs`.

---
*Adapted from Matt Pocock's
[`wayfinder`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/engineering/wayfinder/SKILL.md)
(MIT). Agentsmith keeps its decision-map concepts while making the terminal artifact repository-
native and preserving tracker consent.*
