# Finite autonomous runs

An autonomous run is the missing middle between an attended session and a recurring loop. It is a
finite, approved implementation ticket that can run for hours without a person watching every
turn. A loop watches forever; a run stops at one accepted local result or one explicit escalation.

## The contract before the controller

Planning and execution meet at two artifacts:

1. an accepted Wayfinder terminal spec under `docs/specs/`; and
2. a separate implementation ticket whose scope is one executable unit from that spec.

The agent may write a draft spec, but it cannot accept its own spec. Starting the controller is a
separate human action. If Linear writes are not authorized, the ticket remains a paste-ready draft
until the operator posts it; naming Linear never grants the run a connector.

Copy `templates/autonomous-run.json` through the controller's `prepare` command. The manifest pins
the spec hash, ticket, base ref, maker/checker runtime and model, path boundary, verifier, attempt
cap, wall-clock budget, and git/external-write policy. It must be reviewed and committed before
`start` will accept it.

## What runs overnight

`scripts/autonomous-run.py start <manifest>` creates a sibling git worktree on an
`agentsmith/<run-id>` branch. Each attempt is a fresh maker process. The maker must leave atomic
local commits and a clean tree, then emit a schema-shaped receipt. The controller independently
checks the commit, receipt, changed and ignored paths, fast-forward history, refs, config, hooks,
existing Git objects, and other worktrees' administration. It then creates a disposable detached
worktree at that exact commit: the deterministic verifier and fresh checker run there, never in
the maker's retained worktree.

The role map is data, not policy. Claude/Fable planning → Codex making → Claude checking and Claude
making → Codex checking use the same protocol. Planning is normally attended; the overnight run
begins only after the spec and implementation ticket are accepted.

The v1 boundary is deliberately narrow:

- local coding work only;
- native Claude/Codex headless CLIs, no orchestration framework;
- sandboxed workspace writes and no runtime connectors;
- local commits, no push/PR/merge/history rewrite;
- no Linear or other external-system writes;
- maximum three attempts, then escalation;
- one immutable wall-clock deadline across stop/resume;
- no automatic context-percentage rollover.

Codex receives the manifest objective and remaining native goal token budget. Claude receives only
the remaining run-wide USD allowance. The controller accumulates usage reported by both CLIs and
its persisted state remains authoritative, so resume cannot reset time or reported spend. Codex's
CLI has no controller-enforced hard token switch; its native goal is the in-runtime cap, and the
controller stops after reported usage crosses the manifest ceiling. Calibrate that limit in an
attended run before treating it as a precise cost control.

Claude receives a fail-closed sandbox configuration with no allowed network domains. The verifier
runs with a credential-free environment, no network, no access to other home-directory file data,
and no writes outside the disposable worktree. Read-only Git metadata remains visible so Git-based
checks work. macOS uses the built-in sandbox; Linux requires `bubblewrap`. On any other host—or
Linux without `bwrap`—verification exits closed instead of silently running unrestricted.
Both roles start fresh; their receipts, not conversational memory, are the handoff.
The autonomous controller and `agentsmith evaluate` share the same immutable native-launch helper
for command construction, structured-output parsing, usage extraction, sandbox settings, and the
subprocess environment allowlist; neither runner imports the other's mutable state machine. Codex
invocations use a temporary client home containing a same-filesystem authentication bridge to the
validated ChatGPT login plus minimal no-telemetry configuration. The bridge preserves one OAuth
refresh state and is removed after the process exits; global instructions, user settings, hooks,
plugins, apps, and MCP servers never enter the role environment, and non-ChatGPT authentication
fails closed.

## Operations and recovery

The controller and manifest template are scaffolded only for `software-dev` projects in v1; the
Wayfinder spec flow remains available to every work type.

`status <id>` reads controller state from the repository's git-common directory. `start` and
`resume` hold one per-run lifecycle lock, so a second live controller is refused; a dead owner's
lock is reclaimed only after its PID is demonstrably gone. `stop <id>` atomically writes a stop
request, signals the active controller and child, then waits up to five seconds for the controller
to persist `interrupted`. It never writes `state.json` itself. If the controller has already died,
the request remains in place and `resume` reconciles the interruption after acquiring the stale
lock.

`resume <id>` works only when the committed manifest, accepted spec, base commit, recorded branch,
and worktree still match and the worktree is clean. A changed contract requires a new run ID rather
than silently moving the goalposts. The original deadline and accumulated Claude/Codex usage remain
authoritative across every resume; pausing does not reset either budget.

An accepted run prints the branch, commit, worktree, and evidence for human review. An escalated
run prints the exact boundary that stopped it. Nothing leaves the machine until the operator
separately authorizes the relevant external action.

Before relying on this unattended, run one report-only fixture, observe one complete maker/checker
cycle, and test `stop`. Autonomy is earned using the same ladder as the autonomous-loops profile.
