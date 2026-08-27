# Feedback 0016: Windows doctor corrupted Unicode Git paths

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** Two doctor fixtures failed in the second authorized Windows CI run.

## 1. Evidence / symptom

GitHub Actions run `33076498947` reported a stale native hook and misclassified an unmanaged project
instruction source as managed. Both fixtures placed their repository under a Unicode temporary path.

## 2. Failure mechanism

Git emitted repository and hook paths as UTF-8, while Python's `text=True` subprocess used the active
Windows locale decoder. The corrupted repository root broke both nested-source classification and
pre-commit-hook discovery.

## 3. Bounded edit

Decode the two doctor Git path queries explicitly as UTF-8. Keep replacement decoding only as a
diagnostic fallback; all discovery and ownership rules remain unchanged.

## 4. Named surface

`agentsmith.py` doctor repository-root and hook-path discovery.

## 5. Non-regression validation

The doctor fixture disables Python UTF-8 mode and asserts the exact project and nested Unicode paths,
in addition to the original managed-state and current-hook checks. The replacement Windows matrix is
the real platform check.
