---
name: autonomous-run
description: Prepare, start, inspect, resume, or stop a finite local overnight coding run after a human has accepted a Wayfinder terminal spec; coordinates a declared Claude/Codex maker and independent checker without pushing, merging, or writing to external systems.
compatibility: Requires Python 3.11+, git, Claude Code and Codex CLIs, plus sandbox-exec on macOS or bubblewrap on Linux.
---

# Autonomous run — bounded overnight execution

This skill is for a **finite approved implementation**, not a recurring watcher. For recurring
work use the autonomous-loops profile. For unresolved product or architecture decisions, run
Wayfinder first.

## Hard gate

Do not begin implementation unless all of these are true:

1. The terminal spec is committed under `docs/specs/` with `status: accepted`, `accepted_by`, and
   `accepted_at`. An agent may author only `status: draft`.
2. A separate implementation-ticket ID is named. The decision ticket is not executable work.
3. The operator explicitly invokes or authorizes `start`. Producing or checking a spec never
   self-authorizes implementation.

Linear and every other external system still follow the installed write-consent rule. The v1
controller has no external-write adapter at all.

## Prepare the contract

If `scripts/autonomous-run.py` exists, use it. Its installed template is
`.harness/templates/autonomous-run.json` (the harness source checkout uses
`templates/autonomous-run.json`):

```text
python3 scripts/autonomous-run.py prepare --run-id <short-id> --spec docs/specs/<name>.md --ticket <implementation-ticket> --maker codex --checker claude --template .harness/templates/autonomous-run.json
```

This only creates a manifest. Review its exact allowed/denied paths, verifier, models, attempt cap,
wall-clock limit, budgets, and optional `scope.resources` keys such as `port:3000` or
`db:local/test`. Resource keys coordinate cooperating local runs; they do not replace operating-
system port binding or database isolation. Commit the manifest before execution; the controller
refuses an uncommitted contract. Concurrent worktrees share writable Git metadata needed for local
commits, so this guard prevents accidental collisions between cooperating runs; it is not a
security boundary for mutually untrusted makers.

## Start and supervise

Only after explicit operator authorization:

```text
python3 scripts/autonomous-run.py start .harness/runs/<short-id>.json
```

The controller creates an isolated local branch/worktree, launches a fresh maker, validates its
receipt, scope and Git transition, then creates a disposable detached worktree for the sandboxed
deterministic verifier and a fresh checker. A rejection becomes the next maker's input. Three
failed attempts, invalid state, denied scope, immutable-deadline or reported-budget exhaustion,
Git metadata drift, or checker mutation escalates instead of widening authority. Verification
fails closed unless macOS `sandbox-exec` or Linux `bubblewrap` is available.

Before `start` creates local Git or state artifacts, and before `resume` restarts work, the
controller serializes a repository-local collision scan. Ancestor/descendant fixed prefixes from
`scope.allowed_paths` conflict; a glob with no fixed prefix reserves the repository; identical
resource keys conflict. Live malformed state fails closed, while stopped or demonstrably dead
controllers no longer reserve their scopes.

Use `status <id>`, `stop <id>`, or `resume <id>`. Stop/resume retains the worktree and audit state.
An accepted run ends at a local commit for human review: never push, open a PR, merge, deploy,
rewrite history, or write to Linear from this workflow.

## Report

Give the run ID, status, attempt count, branch/worktree, accepted commit or escalation reason, and
the actual verification evidence. State explicitly that external actions were not taken.
