# Feedback 0004: autonomous state write race

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** The configured release gate failed nondeterministically and could observe corrupt or
  stale lifecycle state when `stop` raced the controller.

## 1. Evidence / symptom

The before-state `python3 agentsmith.py verify` run failed at “stop leaves durable interrupted
state” (`41 passed, 1 failed`). The controller and `stop()` both wrote `state.json` through the
shared `state.json.tmp` path.

## 2. Failure mechanism

There was no lifecycle ownership lock. A request process and the live controller both believed
they owned the state transition, and the fixed temporary pathname made the atomic replace itself
race-prone.

## 3. Bounded edit

Use unique flushed temporary files, add a stale-aware per-run lifecycle lock, and make `stop`
request-only. Only the live controller—or `resume` after it safely acquires ownership—writes state.

## 4. Named surface

`scripts/autonomous-run.py` lifecycle and JSON write helpers;
`scripts/test-autonomous-run.sh`; `docs/21-autonomous-runs.md`.

## 5. Non-regression validation

`scripts/test-autonomous-run.sh` now covers a controller/stop collision, five repeated races,
parse-at-every-observation, exactly one interruption, dead-controller request-only behavior,
stale/live locks, dirty-worktree refusal, and immutable deadline/usage state. Before the fix the
expanded suite reported `47 passed, 6 failed`, including reproducible `JSONDecodeError: Extra data`;
after the fix it reported `56 passed, 0 failed`.
