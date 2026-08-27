# Feedback 0014: Windows lifecycle liveness probe used POSIX signal semantics

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** The first authorized feature-branch push failed the Windows compatibility job.

## 1. Evidence / symptom

GitHub Actions run `33076131711` passed Ubuntu, macOS, and the existing guardrails but failed
`test_live_lock_refusal_release_and_stale_recovery` on Windows. Probing an absent high PID raised
`OSError: [WinError 87] The parameter is incorrect` instead of returning false.

## 2. Failure mechanism

`process_is_live()` used the POSIX `os.kill(pid, 0)` liveness idiom on every platform. Windows does
not provide those signal-zero semantics: the invalid-PID error was not a `ProcessLookupError`, and
using `os.kill()` as a probe can be destructive there.

## 3. Bounded edit

On Windows, query a process handle and its exit status through Kernel32 without sending a signal.
Treat a confirmed invalid PID as stale, but fail closed on access denial or unknown query failures
so an uncertain probe cannot steal a potentially live controller's lock. Keep the POSIX path intact.

## 4. Named surface

`scripts/autonomous-run.py` lifecycle-lock ownership and stop/recovery liveness checks, covered by
`scripts/test-autonomous-state.py` and the GitHub Actions compatibility matrix.

## 5. Non-regression validation

The liveness fixture now names both halves of the contract: the current PID is live and a selected
absent PID is not. The pre-fix Windows matrix is the red check; the targeted test, full local gate,
and replacement Windows matrix run are the green checks.
