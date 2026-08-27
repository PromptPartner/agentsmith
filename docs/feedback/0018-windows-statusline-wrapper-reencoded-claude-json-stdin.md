# Feedback 0018: Windows statusline wrapper reencoded Claude JSON stdin

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** Two statusline fixtures failed in the second authorized Windows CI run.

## 1. Evidence / symptom

GitHub Actions run `33076498947` rendered the fallback `user@host:path` statusline instead of the
fixture model name. A separate collision test expected the Python renderer in Claude's command even
though Windows intentionally points Claude at an owned PowerShell wrapper.

## 2. Failure mechanism

The wrapper read Claude's JSON into a PowerShell string and piped it to Python, allowing the native
pipeline to re-encode stdin so the renderer could not parse the payload. The collision assertion was
a platform-invalid test assumption rather than an ownership defect.

## 3. Bounded edit

Invoke the Python renderer directly from the file-based wrapper so it inherits Claude's raw stdin.
On Windows, assert wrapper command ownership separately from the collision-safe renderer path and
cover both files through idempotence and uninstall.

## 4. Named surface

`agentsmith.py` Claude Windows statusline wrapper generation and `scripts/test-statusline.py`
ownership/lifecycle fixtures.

## 5. Non-regression validation

The statusline suite still covers fresh defaults, explicit choices, foreign collisions, dry-run,
idempotence, doctor diagnostics, and uninstall. It passes 6/6 locally; the replacement Windows matrix
is the real stdin/rendering check.
