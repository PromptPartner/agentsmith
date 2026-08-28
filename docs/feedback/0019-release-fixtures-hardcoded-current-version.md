# Feedback 0019: release-fixtures-hardcoded-current-version

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-28
- **Status:** applied
- **Cost:** The first `0.2.1` release-gate run failed five updater checks and produced one oversized failure trace before release preparation could continue.

## 1. Evidence / symptom

Changing `agentsmith.py` from `VERSION = "0.2.0"` to `0.2.1` made the updater suite fail four
assertions and one lookup. Tests still asserted that the installed version was `0.2.0`, treated
`v0.2.1` as a future release, and expected `0.2.1`-specific probe strings. The saved-plan test no
longer proposed a runtime replacement because its supposed candidate version equalled the runtime.

## 2. Failure mechanism

The updater fixtures encoded one release transition as literals instead of deriving the current and
next patch versions from the runtime under test. The suite proved the `0.2.0 → 0.2.1` transition,
not the updater contract across releases, so an ordinary version bump invalidated its own release
gate.

## 3. Bounded edit

Derive `CURRENT_VERSION`, `NEXT_VERSION`, their tags, and their release probe strings once from the
imported runtime. Use those values for every current-to-next fixture while retaining fixed malformed
and pre-release cases only where their literal shape is the behavior under test.

## 4. Named surface

`scripts/test-update.py`, already wired as the `update` phase in `.harness/verify.conf` and as the
stable-release updater step in the three-platform CI matrix.

## 5. Non-regression validation

With the production runtime restored to `0.2.0`, all 34 updater tests passed using the derived
`0.2.0 → 0.2.1` transition. After the production runtime was bumped, all 34 tests passed again
using the derived `0.2.1 → 0.2.2` transition, and the complete 19-phase release gate passed. Any
remaining current-release literal would recreate the missing runtime proposal or stale-version
assertion and fail that gate.
