# Feedback 0023: update inventoried foreign skill trees

> A harness post-incident. The point is not to fix THIS bug — it is to change the
> SYSTEM so this CLASS of mistake is less likely next time (core/60). Keep it small,
> specific, and traceable to the incident. Never delete this; archive if obsolete (R9).

- **Date:** 2026-08-30
- **Status:** applied
- **Fixed release:** unreleased
- **Cost:** The third stable release in the legacy global update chain still could not complete
  a plan. Once skill detection and global MCP ownership were corrected, the updater entered a
  third-party skill's Python virtual environment and rejected its normal `lib64 -> lib` link.

## 1. Evidence / symptom

A pre-manifest Claude global installation has skills only under `~/.claude/skills`, plus a
third-party `excalidraw-diagram` skill containing a Linux virtual environment. Although that skill
is not bundled or managed by AgentSmith, `update plan --global` recursively inventories it and
fails with `Update refused to follow symbolic link .../.venv/lib64`.

The regression fixture reproduced that exact failure before the production edit. The foreign
skill contained one regular file and the contained `lib64 -> lib` directory link; planning exited
2 before writing a plan.

## 2. Failure mechanism

Capability detection answered whether any skill root existed, while fingerprinting recursively
walked the entire root. It did not reuse the managed/stale/foreign classification already used by
inspection. The read-only inventory also reused the write-target path guard, which rejects every
link rather than enforcing the actual read boundary: the resolved path must remain inside its
declared root.

Filtering foreign trees alone exposed a second ownership edge: a future release could introduce a
bundled name that collides with a foreign directory. If the foreign top-level name is absent from
the staging shadow, the candidate installer sees it as free and proposes replacing the user's
files.

## 3. Bounded edit

Use one skill-directory classifier for inspection and update inventory. Fingerprint only managed
or stale bundled names, and use a read-only containment helper that ignores contained link aliases
but rejects links resolving outside the root. Keep the unconditional link rejection on paths the
updater may write.

Authenticate foreign top-level names separately from fingerprints and materialize only empty
collision sentinels in the staging shadow. This preserves candidate-name collisions without
reading or copying foreign contents. Reconstructed legacy owned-skill fingerprints become the
schema-v1 manifest baseline so post-update health can require owned inventory in every required
skill root.

## 4. Named surface

- Ownership and containment: `safe_inventory_path()`, `inventory_files()`,
  `classify_skill_directories()`, and `installation_fingerprints()` in `agentsmith.py`.
- Explicit plan/apply boundary: authenticated `foreign_skill_directories` plan metadata and
  `preserve_foreign_skill_collisions()` in `agentsmith.py`; schema version remains 1.
- Deterministic guards: legacy global, contained/escaping link, future-name collision, manifest,
  and post-update health fixtures in `scripts/test-update.py`.
- Documentation correction: `skills/RECOMMENDED.md` and `config/plugins.md` no longer describe
  the unbundled `excalidraw-diagram` skill as built in.

## 5. Non-regression validation

The released behavior failed first at the contained `lib64 -> lib` link. With the bounded edit,
all 41 updater tests pass, including the real legacy global Claude + foreign MCP + foreign
virtual-environment shape, internal versus escaping links, existing same-name collisions, a newly
bundled collision across two consecutive source releases, customized owned skills, authenticated
apply, foreign-byte preservation, complete managed-file health, and per-root managed inventory.

The full 19-phase verification gate passes, including compile, conformance, updater, assembly,
secret, leak, hook, and runtime checks. A fresh independent review found two follow-up gaps—the
second-release ownership classification and auxiliary managed-file health check—which received
their own failing fixtures and fixes. The reviewer's final pass found no remaining code or test
issues.
