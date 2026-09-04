# Feedback 0026: Windows atomic state read hit a sharing denial

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-09-04
- **Status:** applied
- **Fixed release:** `v0.3.1`
- **Cost:** One Windows release-gate run failed after an observer could not open autonomous state
  during concurrent atomic replacements; an identical run passed, making the guard flaky.

## 1. Evidence / symptom

GitHub Actions run `33877605556`, job `101038218183`, failed
`test_concurrent_atomic_writers_never_expose_invalid_json` with
`PermissionError(13, 'Permission denied')`. The observer failed while reading the destination; it
did not observe malformed JSON. The identical push-triggered Windows job passed.

## 2. Failure mechanism

Atomic replacement already retried transient Windows sharing errors, but `load_json()` performed a
single read. Windows can briefly deny the reader access while another process replaces the file,
so valid atomic state could be reported as unreadable.

## 3. Bounded edit

Retry only Windows sharing violations 5 and 32 for at most one second when reading JSON. Preserve
immediate failure for every other operating-system error and for invalid JSON.

## 4. Named surface

`scripts/autonomous-run.py` JSON read boundary and `scripts/test-autonomous-state.py`.

## 5. Non-regression validation

The focused suite first failed because the synthetic sharing denial became `RunError`. It then
passed 15 tests after the bounded retry. The concurrent observer now exercises the production
reader, and the release remains gated by Windows CI plus the complete canonical verifier.
