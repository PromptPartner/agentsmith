# Research: adapting Wayfinder for Agentsmith

> Source assessment captured 2026-08-25. Keep under `docs/research/`; archive rather than delete
> if superseded (R9).

## Source inspected

- Matt Pocock's [`skills` repository](https://github.com/mattpocock/skills), commit
  `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`.
- The upstream
  [`wayfinder` skill](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/engineering/wayfinder/SKILL.md)
  and [maintainer guide](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/docs/engineering/wayfinder.md).

## Decision

**Adapt, do not adopt wholesale.** Keep destination, decision map, frontier, fog, linked decision
index, and one-decision-per-session. Package them as one dynamic skill so the universal static
surface does not grow.

Agentsmith deliberately changes the terminal seam:

- the repository owns the complete cross-runtime spec;
- the operator alone changes a draft to accepted;
- decision tickets resolve questions, while separate implementation tickets deliver the result;
- tracker availability never grants write consent; and
- the active work profile defines verification for coding and non-coding destinations.

## Gaps that prevented direct adoption

Upstream ships no Linear consent recipe, treats structural completion as sufficient without
Agentsmith's independent evaluation requirement, permits notes that could be interpreted as
self-authorizing execution, and routes downstream conversion mainly toward software tests and
vertical code slices. Those assumptions do not transfer safely to a universal coding/non-coding
harness.

The adapted behavior is implemented in `skills/wayfinder/SKILL.md`; its terminal artifact is
`templates/wayfinder-spec.md`, and `scripts/test-wayfinder-spec.sh` guards the boundary.
