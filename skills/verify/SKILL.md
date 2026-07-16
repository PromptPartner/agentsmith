---
name: verify
description: Answer "is this shippable / done?" with evidence before a commit or PR — fires on "verify", "is this done", "ready to ship?", pre-commit or pre-PR. Part of the Agentsmith harness; runs the project's verify phases and never claims "passing" without showing the output (R5).
---

# Verify — evidence before "done"

"Verified" is not a feeling; it's output you can point at. Never claim passing without showing it
(R5 + verification-before-completion).

## When this fires
"verify" / "is this done / shippable / ready to merge?" / just before a commit or PR.

## Fast path — if `./scripts/verify.sh` exists
1. Run `./scripts/verify.sh` (runs every phase in `.harness/verify.conf`, stops at the first
   failure). `--list` shows the phases; `--only <tag>` iterates just one.
2. On a failure: read the label + command it printed, explain in plain language what broke, and
   point at that phase's line in `.harness/verify.conf` to fix or refine.
3. Report the actual pass/fail output — not a summary of intent.

## Fallback — no runner or no conf
1. Say so plainly, and look at `.harness/verify.conf.example` for the intended phases.
2. Run the obvious checks for this project directly and show their output: build, test, lint,
   link/render check, a dry-run. For non-code work, "verify" = open the artifact and confirm it
   renders / the numbers reconcile / the links resolve.
3. If nothing is wired yet, propose the phases this project needs and offer to write
   `.harness/verify.conf` — but still run the checks by hand this time.

## Report
State each check and its evidence: "build ok, 42 tests green, lint clean" — with the output, not
"should pass". Anything skipped is "deferred: reason", never silence.
