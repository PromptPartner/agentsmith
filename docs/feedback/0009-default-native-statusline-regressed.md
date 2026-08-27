# Feedback 0009: default native status line regressed

> A harness post-incident. Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** The operator had to restore a missing startup affordance during the 0.2.0 release gate.

## 1. Evidence / symptom

The Batch 5 migration deliberately retired managed Claude status-line wiring, while current docs
still told operators to watch its `ctx:NN%` gauge. The operator explicitly required an active
status line whenever a supported native client has no configured choice.

## 2. Failure mechanism

The platform-suite cleanup classified copied Bash/`jq` implementation details and the user-visible
default as one obsolete contract. Removing both avoided the old cross-platform dependency but also
removed the only activation path for Claude; no replacement test asserted the outcome.

## 3. Bounded edit

Install a dependency-free Claude status line only when `statusLine` is absent, preserve every
explicit value, and track ownership for safe refresh/uninstall. Leave Codex configuration untouched
because its supported built-in line is active when `tui.status_line` is absent.

## 4. Named surface

`agentsmith.py` native install/doctor/uninstall, `config/statusline.py`, and the cross-platform
`statusline` verification phase.

## 5. Non-regression validation

`python3 scripts/test-statusline.py` proves the red-before/green-after install outcome, real helper
execution, context-signal flow, explicit-choice preservation, byte idempotence, and ownership-safe
uninstall. CI runs it on Ubuntu, macOS, and Windows.
