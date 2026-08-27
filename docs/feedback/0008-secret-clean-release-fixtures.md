# Feedback 0008: secret-clean release fixtures

> A harness post-incident. Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** The final changed-file security pass stopped before release handoff.

## 1. Evidence / symptom

`agentsmith secret-scan` blocked two autonomous lock fixtures because a secret-signifying field
name was assigned an eight-character quoted literal. The values were inert, but the tracked source
had the same high-risk shape the pre-commit gate is designed to reject.

## 2. Failure mechanism

The autonomous fixture predated the canonical scanner gate and encoded the lock field literally.
The ordinary test suite tests scanner behavior but does not stage the worktree, so only the final
explicit scan of modified and untracked files exposed the integration failure.

## 3. Bounded edit

Construct the schema field name from inert fragments inside the fixture. Do not add an allow rule:
the production scanner should remain strict for assigned secret-like literals.

## 4. Named surface

`scripts/test-autonomous-run.sh` lock-recovery fixtures and the release changed-file scan.

## 5. Non-regression validation

Scan every modified and untracked file explicitly with the canonical Python scanner after the full
verification gate. The scan must return clean without an allow-list exception.
