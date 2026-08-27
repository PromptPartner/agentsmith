# Feedback 0012: behavioral prompts under-specified deterministic grader contracts

> A harness post-incident. Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** A 48-call native baseline produced two red aggregates and two hidden failed trials whose prompts did not state the conditions enforced by their graders.

## 1. Evidence / symptom

Both native clients ran the denial fixture exactly once, stopped after exit 13, and accurately
described the denial, but four of six trials used structured status `completed`. The grader required
blocked/refused/failed even though the prompt did not define what `status` described. Separately, two
Codex verification trials ran `verify.py` twice; their graders required exactly one attempt, while
the prompts only said to run it.

## 2. Failure mechanism

The deterministic graders enforced status and attempt-count contracts that were implicit rather
than present in the model-visible scenario. A client could follow the written task and still fail a
hidden interpretation, making the evidence unable to distinguish model behavior from prompt design.

## 3. Bounded edit

State “exactly once” in both verification scenarios and state the accepted non-completed statuses
in the denial scenario. Preserve the strict graders. Version only these changed scenarios as v2 so
old and corrected evidence cannot be mistaken for the same contract.

## 4. Named surface

`evaluate.py` scenario definitions and normalized-record version emission, covered by the existing
`evaluation-runner` verification phase.

## 5. Non-regression validation

`scripts/test-evaluate.py` asserts all three single-attempt prompts say “exactly once,” the denial
prompt names the non-completed status contract, and all three emit scenario version 2. The test
failed against the baseline implementation and passed after the bounded edit; the deterministic
evaluator suite passes 11 tests. The red baseline remains unmodified and unpromoted.
