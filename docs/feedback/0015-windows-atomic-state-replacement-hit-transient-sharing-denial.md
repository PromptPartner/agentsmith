# Feedback 0015: Windows atomic state replacement hit transient sharing denial

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** The replacement Windows CI run remained red after its liveness failure was fixed.

## 1. Evidence / symptom

GitHub Actions run `33076498947` reached the full autonomous-state suite and then raised
`PermissionError: [WinError 5] Access is denied` while one concurrent writer replaced `state.json`.
The observer and seven other writers were accessing the same destination at the time.

## 2. Failure mechanism

The temp-file-plus-`os.replace()` algorithm preserves atomic contents, but Windows can transiently
deny replacement while another thread or process has the destination open. A single unbounded
attempt turned this expected sharing race into a controller failure.

## 3. Bounded edit

Keep the same-filesystem atomic replacement, retrying only Windows access-denied/sharing-violation
errors at 10 ms intervals for at most one second. All other errors and exhausted retries still fail
loudly; POSIX behavior is unchanged.

## 4. Named surface

`scripts/autonomous-run.py` durable JSON writer, used by run state and lifecycle coordination.

## 5. Non-regression validation

A deterministic unit test injects one Windows access denial and proves the replacement is retried
once. The existing eight-writer/observer stress test proves every observed state remains parseable;
the replacement Windows matrix is the real platform check.
