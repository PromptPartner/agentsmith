# Feedback 0027: installed context nudge ignored documented threshold contract

> A harness post-incident. The point is not to fix THIS bug — it's to change the
> SYSTEM so this CLASS of mistake is less likely next time (core/60). Keep it small,
> specific, and traceable to the incident. Never delete this; archive if obsolete (R9).

- **Date:** 2026-09-17
- **Status:** applied
- **Cost:** The documented and tested hook was not the hook normal installations executed. Users
  could receive a generic reminder on every Claude Stop event while threshold, freshness, and
  once-per-session behavior remained untested in the installed Python runtime.

## 1. Evidence / symptom

`install_hooks()` registered `python .../.agentsmith/agentsmith.py hook context-budget-nudge`.
`cmd_hook()` returned `additionalContext` for every invocation and did not read a session signal,
threshold, freshness bound, or marker. The detailed behavior and regression suite instead targeted
the legacy `hooks/context-budget-nudge.sh` file.

## 2. Failure mechanism

The hook migration replaced the installed shell command with the cross-platform Python runtime,
but the behavioral tests stayed attached to the old implementation. Installation tests asserted
that a command was present, not that the installed command consumed the status-line signal and
returned the documented Stop schema. Documentation therefore agreed with a passing test that did
not exercise the production path.

## 3. Bounded edit

Make the Python runtime the tested contract: no default percentage, explicit threshold opt-in,
fresh per-session signal, once-per-session marker, and top-level Stop `decision`/`reason`. Retain
the legacy shell test for manual installations, but add an end-to-end test that installs the
runtime, invokes the installed status line, and passes its signal to the installed Stop command.

## 4. Named surface

`agentsmith.py` (`context_budget_nudge` and `cmd_hook`),
`scripts/test-context-budget-nudge.py`, `scripts/test-context-budget-nudge.sh`, and the
`context-budget-runtime` phase in `.harness/verify.conf`. User-facing behavior is synchronized in
the hook/status-line documentation and the context-policy research note.

## 5. Non-regression validation

Before the runtime change, `python3 scripts/test-context-budget-nudge.py` failed seven assertions:
the unconfigured, below-threshold, invalid, malformed, and stale cases all emitted the generic
reminder. After the change, five cross-platform tests pass, including an actual install → status
line → installed Stop command trace. The legacy suite also passes 11 checks. The documentation
guard rejects the former universal/default phrases on operational surfaces.
