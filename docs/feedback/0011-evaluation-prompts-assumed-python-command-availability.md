# Feedback 0011: evaluation prompts assumed python command availability

> A harness post-incident. Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** One of four authorized subscription calibration calls could not exercise the intended denial behavior.

## 1. Evidence / symptom

The Codex `denied-action-no-retry` calibration called `python tools/denied_action.py` exactly once,
but this host provides `python3`, not `python`. The shell returned 127 before the fixture wrote its
attempt log, so the sample measured command availability rather than behavior after a denied action.

## 2. Failure mechanism

Three scenario prompts hard-coded an unqualified `python` command even though the evaluator itself
already knows the interpreter that launched it. Fake-client tests bypassed the prompt command and
therefore could not detect the mismatch.

## 3. Bounded edit

Render denial and verification prompts with the evaluator's `sys.executable`, quoted for the host
platform. Keep fixture execution otherwise unchanged.

## 4. Named surface

`evaluate.py` prompt rendering, covered by the existing `evaluation-runner` verification phase.

## 5. Non-regression validation

`scripts/test-evaluate.py` now checks all three Python-backed scenarios name the active interpreter
and contain no `Run python ` fallback. The test failed against the calibration implementation and
passed after the bounded edit; the complete deterministic evaluator suite passes 10 tests.
