# Feedback 0003: split Python and shell secret scanners

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** The public command, Git hook, documentation, and scanner tests exercised different
  implementations and different secret classes; one implementation also exposed matched values.

## 1. Evidence / symptom

At `de6a354`, `agentsmith secret-scan` used four Python regexes over tracked and untracked files.
`scripts/secret-scan.sh` used nine high-signal classes plus staged/whole-tree/file/stdin modes, and
its tests targeted the shell path rather than the Python command.

## 2. Failure mechanism

The cross-platform Python port added a second implementation instead of moving the existing
contract behind the new CLI. Test success therefore certified the compatibility path but not the
runtime installed by `--with-hooks`.

## 3. Bounded edit

Make the Python command canonical, preserve the nine-class interface and allow rules, redact
findings, and leave the shell script as a thin launcher only.

## 4. Named surface

`agentsmith.py` scanner/parser/hook path; `scripts/secret-scan.sh` launcher;
`scripts/test-secret-scan.sh` or its cross-platform Python replacement; hook documentation.

## 5. Non-regression validation

Runtime-assembled positive shapes, clean prose/env references, allow rules, staged deletion,
staged/`--all`/file/stdin modes, Unicode paths, foreign-hook preservation, redaction, and speed must
all exercise Python. Observed red on the split implementation: 16 failures across 10 tests.
Observed green on 2026-08-26: 10 tests passed with
`python3 scripts/test-secret-scan.py`; the POSIX launcher exercised the same Python command.
