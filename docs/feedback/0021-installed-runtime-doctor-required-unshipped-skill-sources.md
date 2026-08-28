# Feedback 0021: installed runtime doctor required unshipped skill sources

> A harness post-incident. Keep this small, specific, and traceable to the observed failure.

- **Date:** 2026-08-28
- **Status:** applied
- **Cost:** The updater's apply-time health check passed, but invoking `doctor --strict` through the
  installed project runtime crashed instead of inspecting the updated installation.

## 1. Evidence / symptom

The legacy Claude migration fixture applied successfully. A subsequent invocation of
`.agentsmith/agentsmith.py doctor --agent claude --strict` raised `FileNotFoundError` while reading
`.agentsmith/skills`. Project runtime installation copies the runtime and registry, not bundled skill
source directories. Apply-time doctor did not expose this because it runs from the complete staged
release checkout.

## 2. Failure mechanism

`inspect_skills()` assumed `ROOT/skills` always exists. That is true in a source checkout and false
for the installed project runtime, so verification covered a different runtime shape than operators
actually invoke.

## 3. Bounded edit

When bundled skill sources exist, retain the exact source comparison. When they do not, classify
installed skills against the schema-v1 manifest's managed-file paths and hashes. Treat directories
without inventory as foreign rather than crashing.

## 4. Named surface

- Production: `agentsmith.py`, `inspect_skills()`.
- Deterministic guard: the legacy Claude plan/apply fixture in `scripts/test-update.py` invokes the
  installed runtime's strict doctor after apply.

## 5. Non-regression validation

`test_legacy_claude_project_capabilities_survive_plan_apply_and_strict_health` now exercises plan,
apply, installed runtime, and strict doctor. It fails with the prior `FileNotFoundError` and passes
with the inventory fallback.
