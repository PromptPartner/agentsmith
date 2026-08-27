# Feedback 0005: omitted and stale migration suites

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** The configured gate could be mostly green while omitted suites held 45 failures, mixing
  real migration gaps with assertions for retired implementations.

## 1. Evidence / symptom

Before-state results: assembly `21/22`, tracker consent `10/17`, operator identity `14/14` with
PowerShell skipped, and platform install `73/110`. None of those suites appeared in
`.harness/verify.conf`; the platform failures included retired RTK and copied-hook behavior.

## 2. Failure mechanism

The Python migration changed the implementation boundary without a coverage map. Suites were
excluded wholesale instead of classifying each assertion as retained, ported, or retired.

## 3. Bounded edit

Port every retained invariant to the shared Python conformance suite, remove obsolete assertions
only after mapping coverage, then add the repaired suites to local verification and the CI matrix.

## 4. Named surface

`scripts/test-agent-conformance.py`, repaired focused suites, `.harness/verify.conf`, and CI workflow
files.

## 5. Non-regression validation

`docs/research/platform-install-coverage-map.md` classifies every former platform group. Strict
conformance now reports `101 passed, 0 gaps, 0 failed`; consent reports four passing behavioral
tests; assembly reports `23 passed, 0 failed`; operator identity remains in the local gate; and
atomic state, scanner, consent, and conformance run in the Ubuntu/macOS/Windows matrix. The two
obsolete platform suites were removed only after those mappings and replacements existed.
