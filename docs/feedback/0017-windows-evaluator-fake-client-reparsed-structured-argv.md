# Feedback 0017: Windows evaluator fake client reparsed structured argv

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** Five evaluator fixtures failed in the second authorized Windows CI run.

## 1. Evidence / symptom

GitHub Actions run `33076498947` showed every fake Claude evaluation failing while the equivalent
Codex records passed. Exit status, untracked-secret detection, interpreter quoting, and portable home
redaction assertions also diverged on Windows.

## 2. Failure mechanism

The Windows-only `.cmd` fake-client shim re-parsed Claude's inline JSON schema and other structured
arguments before Python received them. That primary failure masked the expected exit code and secret
copy behavior. Two smaller tests separately assumed POSIX command quoting and path separators.

## 3. Bounded edit

Let configured Python client fixtures launch as `[sys.executable, script]` without a shell hop, and
use the same prefix for command previews and version queries. Make prompt quoting and home redaction
follow the active platform while preserving portable normalized output.

## 4. Named surface

`native_launcher.py` native argv boundary, `evaluate.py` preview/version/redaction paths, and the
deterministic fake-client evaluator suite.

## 5. Non-regression validation

The fake `.py` client exercises all eight scenarios for both native clients, including structured
Claude schema arguments, process exit 9, and an untracked secret copy. The evaluator suite passes
12/12 locally; the replacement Windows matrix is the platform check.
