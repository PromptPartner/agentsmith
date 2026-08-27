# Feedback 0006: effective global and project context duplication

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** Operators could unknowingly load two managed copies of the universal core while doctor
  reported only one project file and no effective token duplication.

## 1. Evidence / symptom

At `de6a354`, `doctor_capability()` inspected only `<target>/AGENTS.md` for every agent and returned
`state=declared` for skills, MCP, hooks, and runtime. It did not resolve global or nested
instructions, generator metadata, fingerprints, token cost, or duplicate cores.

## 2. Failure mechanism

Doctor reflected registry declarations rather than the client’s effective installed state. The
installer supported `--profile-only`, but diagnostics could not show why or when it was useful.

## 3. Bounded edit

Resolve each selected agent’s actual global/project/nested sources and installed capabilities,
report fingerprints and combined/duplicate token estimates, and warn—without rewriting—on duplicate
managed cores and contradictory metadata.

## 4. Named surface

`agentsmith.py` doctor resolvers/text+JSON rendering; shared Python conformance fixtures;
doctor/help/troubleshooting documentation.

## 5. Non-regression validation

`scripts/test-doctor.py` now observes full-project, layered, unmanaged, nested, missing-global,
Unicode/space-path, duplicate-core, missing-copy, conflicting-metadata, trusted expanded-surface,
and stable JSON states. Safety mapping and foreign JSON/TOML preservation remain covered by strict
conformance. The doctor fixture reported four passing behavioral tests after all four failed against
the declaration-only implementation.
