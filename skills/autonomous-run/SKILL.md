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

Use `.agentsmith/autonomous-run.py` in an installed project; the source checkout uses
`scripts/autonomous-run.py`. The installed template is
`.harness/templates/autonomous-run.json` (the harness source checkout uses
`templates/autonomous-run.json`):

```text
python3 .agentsmith/autonomous-run.py prepare --run-id <short-id> --spec docs/specs/<name>.md --ticket <implementation-ticket> --maker codex --checker claude --maker-model <model> --checker-model <model> --template .harness/templates/autonomous-run.json
```

`prepare` refuses blank or placeholder models and efforts and names the fields to fill. Ask the
operator which models to use; never invent one. Review the manifest's exact allowed/denied
paths, verifier, models, attempt cap, wall-clock limit, budgets, and optional `scope.resources` keys such as `port:3000` or
`db:local/test`. Resource keys coordinate cooperating local runs; they do not replace operating-
system port binding or database isolation. Commit the manifest before execution; the controller
refuses an uncommitted contract. Concurrent worktrees share writable Git metadata needed for local
commits, so this guard prevents accidental collisions between cooperating runs; it is not a
security boundary for mutually untrusted makers.

Before any Git metadata write in this repository (`git worktree remove` or `prune`, a branch
delete, a history rewrite), run the read-only guard and continue only on exit 0:
`python3 .agentsmith/autonomous-run.py status --all-terminal && <git command>`. Exit 1 names the
live or unfinished run; exit 2 means it cannot tell, which you treat as live.

Size budgets per run. Class the work by the lines it should change (S up to about 350, M up to
about 800, L up to about 2,500; split anything larger), cap at the highest usage measured for an
accepted run of that class plus at least 20% headroom, and write the class, the measurement and
who set it in `limits.budget_rationale`. A run stops at the first report over a cap, even by 1%; a
finished maker's candidate is checkpointed first, so `resume` can verify and check it.
Keep `max_attempts` at 3. Every runtime a role uses needs its cap (`codex_goal_tokens`,
`claude_max_usd`); zero or a missing cap refuses at `prepare` and `start`. Only the operator may
choose `"unbounded"` instead, and only with `budget_rationale` saying who chose it and why.

To rework a finished run, prepare a new run with `--rework-of <run-id> --note <file>`; the note is
pinned by hash and goes to the maker. Never reopen an accepted run.

## Start and supervise

Only after explicit operator authorization:

```text
python3 .agentsmith/autonomous-run.py start .harness/runs/<short-id>.json
```

The controller creates an isolated local branch/worktree, launches a fresh maker, validates its
receipt, scope and Git transition, then creates a disposable detached worktree for the sandboxed
deterministic verifier and a fresh checker. A rejection becomes the next maker's input. Three
failed attempts, invalid state, denied scope, immutable-deadline or reported-budget exhaustion,
Git metadata drift, protected verification edits, or checker mutation escalates instead of widening authority.
A known infrastructure failure (network, sign-in, overload, sandbox start, client crash) relaunches
the role without spending an attempt; the same failure twice in a row stops the run, and a work
graph then starts no new child. A Claude checker that accepts after a denied tool call is not
trusted and is relaunched the same way. Report the named failure; the operator fixes it and resumes. Verification
fails closed unless macOS `sandbox-exec` or Linux `bubblewrap` is available. Before creating
anything, `start` runs one trivial sandboxed command per role and one through the verifier
sandbox; if the host cannot run them, it refuses and names the role and reason.

Existing baseline tests, the accepted spec, runtime launchers, and verification policy are protected
even with broad maker scope, and moving or renaming one of them counts as changing it. So are agent
instructions at any depth (`AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`,
`GEMINI.md`, and `.claude/`, `.codex/`, `.agents/`, `.cursor/` folders), because the checker loads
them from the candidate; if a task needs one changed, the operator commits that change first. A moved
file counts as two changed paths, the old one and the new one; both must be inside the allowed
scope. Add custom acceptance inputs via `verify.protected_paths`; changing
protected inputs requires separate operator review outside this run. New regression tests remain
allowed. Both roles receive trusted-path write restrictions through their native policies; Codex uses a
strict named filesystem profile, and Claude combines Bash denyWrite with file-tool Edit denials.
Native clients and the host remain trusted. Checkers inspect the controller verifier evidence,
and an accepting checker cites it per criterion as `criterion :: file[:line] :: excerpt`; an
acceptance whose citations do not check out is a checker defect and the attempt is reworked.
At acceptance the run records the risk tier from the policy committed at the base (`status <id>`
shows `risk_tier`); a declared `risk_tier` only raises it, and the tier decides nothing yet.
Before relying on a checker client and model, run `calibrate <manifest>`: it judges a clean and a
defective built-in candidate and records the result, which later runs show as `checker_calibration`.

Before `start` creates local Git or state artifacts, and before `resume` restarts work, the
controller serializes a repository-local collision scan. Ancestor/descendant fixed prefixes from
`scope.allowed_paths` conflict; a glob with no fixed prefix reserves the repository; identical
resource keys conflict. Live malformed state fails closed, while stopped or demonstrably dead
controllers no longer reserve their scopes.

While `.harness/AUTONOMY_PAUSED` exists, `prepare`, `start` and `resume` refuse; live runs keep
running until `stop <id>`. Never create or delete that file on your own; it is the operator's.
Use `status <id>`, `stop <id>`, or `resume <id>`. Stop/resume retains the worktree and audit state.
Resume revalidates a checkpointed candidate and reruns verification/checking in the same attempt.
Dirty or unreceipted maker commits require operator review. Raw logs survive controller crashes;
earlier invocations are archived. Report `usage_accounting_incomplete` when a crash leaves
unreported spend unknown. A surviving role process group must be stopped before recovery.
An accepted run ends at a local commit for human review. Do not push, open a pull request, merge,
deploy, rewrite history, or write to Linear from the run itself; landing is the separate attended
step below, and only with the operator's yes.

## Land an accepted run (attended)

Roles have no network and no credentials, and the controller never pushes. Landing happens here,
in an attended session, with one yes from the operator:

1. Run `python3 .agentsmith/autonomous-run.py deliver <run-id> --dry-run`. If it refuses, report
   the reasons and stop.
2. Show the operator the push command, the pull-request title and body, the tier, the base
   staleness and the `Auto-merge eligible` line.
3. Ask once: "Push <accepted-sha> to agentsmith/<run-id> and open a pull request with this body?"
   Anything but a clear yes ends the step. The yes covers only this push and this pull request.
4. Push the exact accepted commit, never a moving branch name:
   `git push origin <accepted-sha>:refs/heads/agentsmith/<run-id>`.
5. Save the body to a file and open the pull request:
   `gh pr create --base <base-branch> --head agentsmith/<run-id> --title "<title>" --body-file <file>`.
6. Run `agentsmith ci watch --pr <number>` and report its one end state and next step. Do not fix,
   rerun or comment on CI from this step.
7. After a green watch, run `deliver <run-id> --eligibility --sha <accepted-sha> --pr <number>`
   and report the eligibility line. It is information only. A human merges; never merge, approve
   or enable auto-merge from this step.

## Report

Give the run ID, status, attempt count, branch/worktree, accepted commit or escalation reason, and
the actual verification evidence. State explicitly that external actions were not taken.
