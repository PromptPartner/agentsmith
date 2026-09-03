---
name: verify
description: Answer "is this shippable / done?" with evidence before a commit or PR — fires on "verify", "is this done", "ready to ship?", pre-commit or pre-PR. Part of the Agentsmith harness; runs the project's verify phases and never claims "passing" without showing the output (R5).
compatibility: Requires command access; the fast path requires the cross-platform Agentsmith CLI.
---

# Verify — evidence before "done"

"Verified" is not a feeling; it's output you can point at. Never claim passing without showing it
(R5 + verification-before-completion).

## When this fires
"verify" / "is this done / shippable / ready to merge?" / just before a commit or PR.

## Runtime neutrality
The verification runner and evidence standard are client-neutral. Never infer the active agent
from this skill's install path: portable canonical content may be copied into a required client
adapter such as `.claude/skills`. Use canonical `AGENTS.md` when an instruction is relevant.

## Fast path — if the Agentsmith CLI is available
1. Run `agentsmith verify` (or the installed-project shim `.agentsmith/agentsmith verify` on
   macOS/Linux and `.agentsmith\\agentsmith.cmd verify` on Windows). It runs every phase in
   `.harness/verify.conf` and stops at the first
   failure). `--list` shows the phases; `--only <tag>` iterates just one.
   Add `--record <directory>` when deterministic command evidence needs a durable local receipt.
   The destination must be new; relative paths resolve from the project target. Record mode
   redacts secret-shaped console and sidecar output before either is emitted.
2. On a failure: read the label + command it printed, explain in plain language what broke, and
   point at that phase's line in `.harness/verify.conf` to fix or refine.
3. Report the actual pass/fail output — not a summary of intent.

The v1 receipt covers deterministic commands only. Keep screenshots, videos, manual assertions,
published results, and real runtime or visual checks as separately referenced artifacts. A green
receipt does not satisfy an end-to-end gate that requires those observations.

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
