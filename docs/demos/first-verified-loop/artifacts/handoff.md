# Handoff — first-verified-loop — <handoff-time>

**Branch:** proof/first-loop   **HEAD:** <git-commit>   **Uncommitted files:** 12

## Recovery checkpoint

- **Exact objective:** Correct the failed readiness check and retain its evidence.
- **Repository / worktree:** $DEMO
- **Protected-state hashes:** baseline commit <git-commit>
- **Branch / commit:** proof/first-loop / <git-commit>
- **External identifiers:** none
- **Completed verification:** receipt .harness/evidence/public-proof/receipt.json passed all three phases
- **Active external operation:** none
- **Next read-only recovery command:** `agentsmith status --target $DEMO`
- **Remaining authorized writes:** none
- **Stop conditions:** stop before any Git or file mutation
- **Skipped validation:** native operating-system matrix remains CI evidence

## What shipped this session

The failed partial readiness check now reaches the visible command as NOT READY.

## What is still pending

Independent review of the public demonstration.

## Deviations from the plan / decisions made (don't re-litigate)

None.

## Exact next step

Run the saved read-only status command.

## Gotchas a fresh session would otherwise re-derive

The receipt and dirty readiness.py are intentional evidence from the bounded fix.

---
## Kickoff prompt for a fresh chat
```
Resume the bounded readiness proof from this handoff. Inspect the receipt, then run only
the saved read-only status command. Do not change Git or repository state.
```
