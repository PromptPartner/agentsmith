# Feedback 0002: cautious documentation versus trusted runtime default

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** Fresh installs and ordinary managed updates could grant bypass/no-approval execution
  even though the operator-facing safety and troubleshooting guidance called cautious the default.

## 1. Evidence / symptom

At `de6a354`, `add_common_install_flags()` defaulted `--safety` to `trusted`. The wizard did not ask
for safety. `INSTALL.md` acknowledged a trusted migration default while `docs/15-safety-model.md`
and `docs/17-troubleshooting.md` described cautious as the default.

## 2. Failure mechanism

Documentation and runtime evolved independently, and the conformance suite tested only explicit
safety choices. Omitted input had no regression assertion, so the higher-risk mapping became the
silent normal path.

## 3. Bounded edit

Default omitted safety to cautious, add the cautious-default wizard choice, warn and back up when a
managed trusted setting migrates, and retain trusted only as an explicit flag.

## 4. Named surface

`agentsmith.py` install parsing/wizard/native reconciliation; shared Python conformance tests;
installation, safety, troubleshooting, and CLI help documentation.

## 5. Non-regression validation

Fresh/update x Claude/Codex fixtures must assert implicit cautious and explicit trusted mappings,
foreign-content preservation, dry-run isolation, idempotence, malformed-choice rejection, and
parseable JSON/TOML. Observed red at `85 passed, 4 failed` on the prior implementation; observed
green on 2026-08-26 at `89 passed, 0 gaps, 0 failed` with
`python3 scripts/test-agent-conformance.py --strict`.
