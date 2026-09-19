# FVL-08 release-readiness boundary

The local product promise is covered by the status, profile, discovery/apply, red-to-green demo,
real command, receipt, resume, documentation, lifecycle, claim-map, and security artifacts in this
bundle. The repository gate contains 25 verification phases, and the implementation remains
standard-library only, so no new runtime dependency audit applies.

Release closure is fail-closed. The wave is **not complete until** the native Linux, macOS, and
Windows jobs each produce a passing machine-readable report for the same clean Git commit and tree,
and `scripts/first-loop-release-evidence.py aggregate` accepts exactly those three reports. Workflow
logs alone are not the receipt. The aggregate artifact plus a final repository receipt and handoff,
both written after the last change, close FVL-08.

No commit, push, workflow trigger, publish, merge, or deployment is implied by this document.
