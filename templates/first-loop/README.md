# First Verified Loop demo

The goal is simple: the launch-readiness command must report `READY` only when every required check
passes. The baseline deliberately uses `any` instead of `all`, so one passing check hides one failed
check.

1. Run `agentsmith status` to understand the active setup.
2. Run `agentsmith verify` to observe the named failing test.
3. Complete only the task in `ACCEPTED_TASK.md`, then run the visible command and verification again.

## Optional local Git checkpoint

A Git checkpoint is a local snapshot you can return to if the exercise goes wrong. No remote is
configured, no network access occurs, and nothing is published. If Git is available and you
explicitly choose this recovery exercise, run these commands before editing `readiness.py`:

```text
git init
git add .
git commit -m "first-loop intentional red baseline"
```

Git may ask for a local author identity before the commit. Do not change global Git configuration
for this demo. After an unwanted edit, inspect `git diff` first; `git restore readiness.py` then
returns only that named file to the local checkpoint. It does not affect a parent directory.

For the continuity exercise, run `agentsmith handoff first-verified-loop`, stop the session, and use
`agentsmith resume` in a fresh session. The demo is disposable: rollback means deleting only the
explicit demo directory you selected, never a parent directory.
