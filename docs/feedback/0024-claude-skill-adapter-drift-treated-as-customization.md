# Feedback 0024: claude skill adapter drift treated as customization

> A harness post-incident. The point is not to fix THIS bug — it's to change the
> SYSTEM so this CLASS of mistake is less likely next time (core/60). Keep it small,
> specific, and traceable to the incident. Never delete this; archive if obsolete (R9).

- **Date:** 2026-08-31
- **Status:** applied
- **Fixed release:** `v0.2.5`
- **Cost:** A Claude report and a second planning pass were needed to catch a stale runtime adapter that Doctor called managed.

## 1. Evidence / symptom
An AgentSmith update refreshed `.agents/skills`, but left the AgentSmith-owned
`.claude/skills` copy unchanged. Claude discovers the latter, so it continued to execute stale
guidance. The existing regression test asserted those stale bytes and strict Doctor still exited
successfully.

## 2. Failure mechanism
The ownership classifier applied one recorded-hash customization policy to both the canonical
skill root and Claude's derived adapter. Update staging therefore preserved adapter divergence as
if it were a supported user customization. Doctor also merged both roots into one `stale` or
`managed` result without checking byte identity between them.

Independent review exposed two related seams: install did not reject a symlinked adapter root, so
copies could escape the install root; and plan/apply could replace files but could not delete an
authenticated adapter-only file. Symlinks inside a skill were also absent from snapshot equality.

## 3. Bounded edit
Make ownership role-aware: preserve recorded canonical customizations, always regenerate owned
Claude adapters from effective canonical bytes, and never touch names absent from canonical
ownership. Make strict Doctor reject adapter divergence while reporting canonical customization
separately.

## 4. Named surface
`agentsmith.py` skill installation, staged update ownership, post-update health, and Doctor;
`config/agents.json` plus its schema for discovery-versus-management paths; deterministic
regressions in `scripts/test-update.py`, `scripts/test-doctor.py`, and
`scripts/test-agent-conformance.py`. Root containment uses `safe_update_path()` before skill
writes; authenticated plan and rollback schemas now support adapter deletions; directory snapshots
include link identity without following links.

## 5. Non-regression validation

The changed legacy project regression first failed because its authenticated plan contained no
Claude adapter replacement. It now passes and verifies the before hash, byte-identical canonical
and adapter content after apply, candidate-release content, rollback-receipt hash, and exact old
adapter bytes after rollback.

The updater's 41 tests, Doctor's 8 tests, strict 104-check conformance suite, and 9 registry tests
pass. Added cases cover project and global reinstall, canonical customization, adapter divergence,
foreign skill and virtual-environment preservation, force-independent synchronization, strict
Doctor failure, legacy global/project staged updates, and rollback.

An independent adversarial pass then reproduced an external-write escape, a non-migratable extra
adapter file, and invisible contained-link drift. Each received a failing regression before the
fix; all three focused regressions now pass. The full gate and secret scan are rerun after these
review fixes before release handoff.

Residual: staged update does not encode symlink deletion plus exact symlink restoration in its
rollback receipt. Such drift is now visible to strict Doctor; update fails closed and rolls back,
while ordinary reinstall repairs it. The bounded follow-up is recorded in `KNOWN-ISSUES.md` rather
than widening this change into a receipt-schema migration.
