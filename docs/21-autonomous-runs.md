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

Run `python3 .agentsmith/autonomous-run.py prepare --run-id <id> --spec docs/specs/<name>.md
--ticket <implementation-ticket> --maker-model <model> --checker-model <model>` in an installed
consumer project. It uses
`.harness/templates/autonomous-run.json`; the source checkout uses `scripts/autonomous-run.py`
and `templates/autonomous-run.json`. The manifest pins
the spec hash, ticket, base ref, maker/checker runtime and model, path boundary, verifier, attempt
cap, wall-clock budget, and git/external-write policy. It must be reviewed and committed before
`start` will accept it. Both roles require explicit model and effort settings. `prepare` refuses to write a
manifest while a model or effort is blank or a placeholder (`<...>`, `REPLACE-WITH...`,
`TO-FILL`, `TODO`, `TBD`, `CHANGEME`, `PLACEHOLDER`, `FIXME`) and names each field to fill;
`start` refuses the same values. `scope.resources` optionally names local coordination keys such as
`port:3000`, `db:local/test`, or `service:redis`; omit it in an older manifest or use an empty list
when the run reserves none.

**Rework.** When a finished run needs another pass, prepare a new run with the operator's note:

```text
python3 .agentsmith/autonomous-run.py prepare --run-id <new-id> --spec docs/specs/<name>.md \
  --ticket <ticket> --rework-of <finished-run-id> --note <file in the repository>
```

The run it reworks must be finished (`accepted`, `escalated` or `interrupted`), and it is never
reopened: a rework is always a new run with a new ID. The manifest pins the note by path and
SHA-256 in `rework`, and `start` and `resume` refuse when the note changed after `prepare`.
The maker receives the note through its prompt, marked as a rework of the earlier run. A note
may be at most 16 KB.

## What runs overnight

`python3 .agentsmith/autonomous-run.py start <manifest>` creates a sibling git worktree on an
`agentsmith/<run-id>` branch. Each attempt is a fresh maker process. The maker must leave atomic
local commits and a clean tree, then emit a schema-shaped receipt. The controller independently
checks the commit, receipt, changed and ignored paths, fast-forward history, refs, config, hooks,
existing Git objects, and other worktrees' administration. The receipt's `changed_paths` must
equal the controller's own list, in which a moved file appears twice: under its old path and
under its new path. Both must be inside the allowed scope. The list holds plain file names, so a
name with a non-ASCII character is written as it is, without the quotes and escapes of Git's
default listing. Scope and protection rules are matched against those plain names. It then
creates a disposable detached
worktree at that exact commit: the deterministic verifier and fresh checker run there, never in
the maker's retained worktree.

Before verification, the controller rejects edits to `.agentsmith/`, `.harness/`, workflow files,
known launchers, the accepted spec, and existing baseline tests. Broad allowed scope does not
waive this gate. Moving or renaming a protected file counts as changing it. New regression tests
may be added. Include additional project acceptance inputs
as globs in `verify.protected_paths` in the reviewed manifest. Protected changes require separate
operator review outside this run; the controller has no self-approval override.

Agent instructions are protected in the same way, because the checker runs in a worktree at the
candidate commit and its client loads them from there. A maker that edits them would write
instructions for its own judge. The rule covers a file named `AGENTS.md`, `AGENTS.override.md`,
`CLAUDE.md`, `CLAUDE.local.md` or `GEMINI.md`, and anything inside a `.claude/`, `.codex/`,
`.agents/` or `.cursor/` folder (settings, hooks, skills, subagents, rules). It applies at any
depth, not only at the root: Claude Code loads a nested `CLAUDE.md` when it reads files in that
folder, and it finds nested `.claude/skills`. Names match ignoring case, because macOS and Windows
open `claude.md` when a client asks for `CLAUDE.md`. Adding, editing, deleting and moving all
count. Symbolic links count too, in the base and in the candidate: when `AGENTS.md` links to
`src/rules.txt`, or `.claude` links to a folder, the target is protected like the instruction
file itself, through chains of links. Adding, retargeting or removing a link that points at a
protected file is refused. An untouched link such as `CLAUDE.md -> AGENTS.md` keeps working. A
link that points outside the repository is not followed; keep instruction files inside it. If a task really needs one of these files changed, for example documentation that happens
to be named `AGENTS.md`, make that change yourself in a reviewed commit, then start the run from
that commit. Neither `scope.allowed_paths` nor any other manifest field can allow it: the operator
approves scope, and scope must not be able to widen what a maker may tell its checker.

Controller verification writes the raw exit code and stdout/stderr to `attempt-N-verify.txt` and
an adjacent JSON receipt. That receipt binds the candidate and base commits, spec and manifest
hashes, verification policy and configuration hashes, controller/launcher hashes, output hash,
and checker receipt hash. A checker acceptance with empty evidence or unresolved findings does
not accept a candidate. Besides trying to falsify the acceptance criteria, the checker is told
to reject a change that is larger than the stated problem needs, and a red test that failed for
the wrong reason (a stub, an import error or an earlier gate instead of the bug's own failure
message). Role exit codes are retained separately from structured receipts.

**An acceptance must cite its evidence.** When the verifier finishes, the controller records by
hash every file the checker may cite: this attempt's output log, `attempt-N-verify.txt`, and the
files the verifier left in the disposable worktree that Git ignores (up to 200, each up to 8 MB).
The list is `evidence_files` in the verification receipt. A checker that accepts writes each
`evidence` item as `criterion :: file[:line] :: excerpt`. The line is optional and counts from the
start of the file. The excerpt is text copied exactly from that file; when a line is given, it
must appear within two lines of it. An excerpt needs at least 12 visible characters besides the
`exit=`, `STDOUT:` and `STDERR:` lines that the controller writes into every log, so a verify
command must print what it checked (a test runner's summary, for example); one that prints
nothing leaves a checker nothing to cite. These rules are a heuristic floor, not proof that the
excerpt supports the criterion. Before acceptance, a check without any model reads every item.
The acceptance is not trusted when it has no evidence item at all, or when an item has no
citation, quotes too little, names a file that this attempt's verifier did not produce (for
example a file from another attempt), cites a line past the end, or quotes text that is not
there. It is not trusted either when any recorded file, cited or not, no longer matches its
hash: a process the verifier started may have kept writing after it finished. That is a
checker defect. The attempt is then reworked like a
rejection: the defect is recorded as a `checker_defect` event and as `checker_defect` in the
verification receipt, and the next maker is told that the acceptance was not trusted. A rejection
needs no citations. The receipt shape does not change, so a stored receipt stays valid, and a
checker whose evidence already uses this form passes as it is.

Acceptance is bound to the exact commit the checks passed. Just before it records `accepted`,
the controller confirms that the run branch and the run worktree's `HEAD` still point at that
commit and that the worktree is clean, and it reads both commit IDs again after that clean
check, because a commit can land while the check runs. A commit that lands after the verifier started, for
example from a process a role left running, refuses acceptance: the run escalates and names the
checked commit and where the branch is now. `accepted_commit` in the run state, the
`run_accepted` event and `candidate_commit` in the verification receipt all name that one commit.

**Checker calibration.** `python3 .agentsmith/autonomous-run.py calibrate <manifest>` tests the
checker that the manifest names (`roles.checker`: client, model and effort) on two built-in
candidates with known answers. The clean candidate implements a small spec correctly and must be
accepted with valid citations. The other candidate has an injected defect: its own test passes,
so the verifier cannot see the defect, but the code breaks the spec, and the checker must reject
it. Each candidate goes through the real verifier sandbox and the real checker launch. The command
writes a calibration receipt to the repository's Git folder, under `agentsmith-calibrations/`. The
receipt records the status, the date, the client and its version, the model, the effort, the hash
of the checker prompt template, each candidate's verdict and the spend. The status is `passed`
(both verdicts right), `failed` (a wrong verdict, an acceptance whose citations do not hold, or a
receipt that does not name the candidate) or `error` (the client could not run). The exit code is
0, 1 or 2 to match. `--max-usd` (default 1.0) caps Claude spend, `--max-tokens` (default 400,000)
caps Codex tokens and `--wall-minutes` (default 20) caps time. Every later run records the latest
calibration for its checker client, model, effort and prompt hash as `checker_calibration` in its
verification receipt, or `{"status": "none"}` when none matches. A changed prompt template needs a
new calibration. This is a record only: no run waits for or depends on a calibration yet. Roles
cannot write the calibration folder. In a measured run on 2026-11-06, a small model (`haiku` at low
effort) failed calibration because its receipts did not name the candidate commit.

**The run receipt records the risk tier.** At acceptance the controller classifies the change from
the base commit to the accepted commit, as `agentsmith risk classify` does (see
[the risk map](29-risk-map.md)), with the policy committed at the base, so a candidate that edits
`.harness/risk-policy.json` is still judged by the policy it started from. The verification
receipt and the run state record `risk`: the computed tier, the lenses, the policy blob, the base
and accepted commits, and the tier recorded. A manifest may declare `risk_tier` (`A`, `B`, `C` or
`human`); it can only raise the computed tier, never lower it. `status <id>` prints `risk_tier`,
`status --all-terminal` lists each accepted run with its tier, and `agentsmith graph status` shows
each completed child's tier. The tier is a report: it changes no decision. If the classification
cannot run, for example because the policy at the base is invalid, the run records the tier
`human` with the error and continues.

Trusted state stays in the controller's shared run directory. Each native role receives explicit
write restrictions for that directory, the original contract, and the controller/launcher source
folders. Codex uses a strict named filesystem permissions profile: the maker can write its
worktree, shared Git directory, and its active worktree administration directory, with more
specific read-only rules for trusted paths. Claude
uses `sandbox.filesystem.denyWrite` for shell tools and absolute `Edit` deny rules for its built-in
file tools. Checker worktrees remain read-only to model tools. The client writes its structured
output to a temporary exchange directory; only the controller copies the parsed receipt into
trusted state. An outer Seatbelt wrapper is unsuitable because macOS rejects nested sandbox
initialization. See [Codex permissions](https://learn.chatgpt.com/docs/permissions) and
[Claude sandboxing](https://code.claude.com/docs/en/sandboxing).

This protects trusted files from model tools using the declared native sandbox. The native client
and host remain trusted; hostile same-user processes and mutually untrusted makers sharing Git
need stronger isolation. Custom verification inputs still require explicit protected paths.
Native integration and Linux containment remain pilot gates. Missing verification configuration
is represented by a null hash rather than an invented receipt.

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

Worktrees isolate tracked files, not every local dependency. Before creating a branch, worktree, or
run state, the controller compares each live run's declared scope under a short repository-wide
coordination lock. It derives a conservative literal prefix from each `allowed_paths` glob: parent
and child prefixes conflict, and a pattern with no literal prefix reserves the whole repository.
An exact shared resource key also conflicts. These declarations coordinate cooperating AgentSmith
runs; they do not bind a port or isolate a database at the operating-system level. Concurrent
worktrees also share writable Git metadata needed for local commits. The controller verifies live
peer identity before accounting for peer Git artifacts, but this is collision coordination, not
adversarial isolation: do not run mutually untrusted makers concurrently in one repository.

**Guard Git metadata writes.** Every linked worktree shares one set of refs and worktree records.
A `git worktree remove`, `git worktree prune`, branch delete or history rewrite in any checkout
can break a run that is still live, or one that has stopped but is not finished, and its work is
then lost or must be redone. `status --all-terminal` is a read-only guard with three exits:

| Exit | Meaning | What to do |
|---|---|---|
| `0` | every run and graph in this repository is terminal (or none exists) | go ahead |
| `1` | a run or graph is live, or stopped without finishing; each is named | wait, `stop`, or `resume` it first |
| `2` | it cannot prove every run and graph is terminal: a file is unreadable, not where or what the controller writes, or has a status it does not know | stop and inspect; treat as live |

Chain it in front of every Git metadata write, so the write runs only on exit 0:

```text
python3 .agentsmith/autonomous-run.py status --all-terminal && git worktree remove <path>
```

Only `accepted`, `escalated` and `interrupted` runs and `completed`, `failed`, `stopped` and
`blocked` graphs count as terminal, once no controller or role process for them is live. A run
folder that holds files but no state (for example a lock left by a start that crashed) is
undetermined: inspect it and remove it by hand before the guard can answer 0.

Every budget is explicit. `limits.wall_minutes` must be a positive whole number of minutes, and
`limits.max_attempts` a whole number from 1 to 3. Each runtime that a role uses needs its own
cap: `limits.codex_goal_tokens` (a positive whole number of tokens) when a role runs Codex, and
`limits.claude_max_usd` (a positive number of US dollars) when a role runs Claude. A zero, a
negative number, text, or a missing cap refuses at `prepare`, `start` and `resume`; in v0.5.0 and
earlier, zero or a missing cap meant "no cap", so update older manifests before you start them.
To run without a token or USD cap, write the string `"unbounded"` for that cap and say who chose
it and why in `limits.budget_rationale`; without that text the controller refuses. The wall clock
has no unbounded choice, because it is the one cap that stops every role while it runs. A work
graph is stricter: each child needs numeric caps for both runtimes.

Where each cap is enforced:

| Cap | Before a role | While a role runs | After a role |
|---|---|---|---|
| `wall_minutes` | refuses when no time is left | the controller ends the role's process group at the deadline | the run escalates |
| `claude_max_usd` | refuses a Claude role when nothing is left | Claude Code stops at the remaining allowance (`--max-budget-usd`) | escalates when reported spend is over the cap |
| `codex_goal_tokens` | refuses a Codex role when nothing is left | not enforced: `codex exec` documents no hard token switch, and the goal budget in the maker prompt is advisory | escalates when reported tokens are over the cap |

So a Codex role can overshoot its cap once, by whatever it spends in that one role, before the
controller stops the run. The controller accumulates usage reported by both CLIs and its persisted
state remains authoritative, so resume cannot reset time or reported spend. Calibrate the Codex
limit in an attended run before treating it as a precise cost control, and bound a single Codex
role with `wall_minutes`.

### Sizing the budget

A cap that is too low stops a run that is still making progress, and the controller stops at
the first report over the cap, even when it is over by 1%. Size each run, do not reuse one
number:

1. Put the work in a size class by the lines it should change: **S** up to about 350, **M** up
   to about 800, **L** up to about 2,500. Above that (**XL**), split the work first.
2. Measure. After an accepted run, `status <id>` shows `codex_tokens_used` and
   `claude_cost_usd`. Set the cap for a class from the highest usage you have seen for an
   accepted run of that class.
3. Keep at least 20% headroom above that number.
4. Write the reason in `limits.budget_rationale`: the size class, the measurement it rests on,
   and who set it. `status` prints it, so a later reader knows who authorized the limit.

When a maker finishes but its report crosses a cap, the controller first keeps its receipt and
candidate checkpoint, then escalates. `resume` then verifies and checks that same candidate
instead of starting a new maker. Each cap stops only the runtime that spends it: a Claude
checker can still check a candidate whose Codex maker used up the Codex cap, while a Codex
checker would be refused.

The template default of 2,500,000 Codex tokens is a starting point for one small change, not a
measurement; until you have your own numbers, run one attended small run first. Keep
`max_attempts` at 3: the token and USD caps bound spend, and fewer attempts only turn
recoverable rejections into escalations.

Claude receives a fail-closed sandbox configuration with no allowed network domains. The verifier
runs with a credential-free environment, no network, no access to other home-directory file data,
and no writes outside the disposable worktree. Read-only Git metadata remains visible so Git-based
checks work. macOS uses the built-in sandbox; Linux requires `bubblewrap`. On any other host—or
Linux without `bwrap`—verification exits closed instead of silently running unrestricted.

No temporary or cache folder is shared between the maker and a later role. Tools keep caches and
startup files in the home, temporary and XDG folders (pip, npm, uv, Go, Cargo, Gradle, a
`.gitconfig`, a Python user `site-packages`), and a maker can write the shared temporary folders.
Content planted there would run inside the verifier, which is how one sandboxed role can reach
another. So each run of the verifier gets its own `HOME`, `TMPDIR`, `XDG_CACHE_HOME`,
`XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_STATE_HOME` in a new folder under `/tmp`, writable
only by that verifier and removed afterwards. Before, the verifier used the fixed home
`/tmp/agentsmith-verifier-home` and the controller's `TMPDIR`. Each checker gets the same kind of
fresh folder for `TMPDIR`, `TEMP`, `TMP`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`,
`XDG_STATE_HOME` and `CLAUDE_CODE_TMPDIR`. The last one matters because Claude Code's sandboxed
shell otherwise uses one temporary folder per user, `/tmp/claude-<uid>`, for every role. The
checker keeps its real `HOME`, because Claude Code and Codex sign in from it. So the tool caches it
would find under `HOME` are pointed at the fresh folder too: npm, pnpm, Yarn, Bun, pip, uv, the
Python user folder, Cargo, Go, Gradle and Maven, and `GIT_CONFIG_GLOBAL` is an empty file instead
of `~/.gitconfig`. A real `claude -p` (Claude Code 2.1.318) and a real `codex exec` (Codex 0.165.0)
signed in and answered with this environment. What remains: a tool that is not on that list still
reads its files under the real `HOME`. The maker's sandbox cannot write `HOME` (it may write only
its worktree, Git metadata and temporary folders), so this matters only if something else writes
there. The maker keeps its usual folders, so it can use the caches you already have. On Windows the
verifier already runs with its home and temporary folders in the disposable worktree and a
temporary AppContainer profile. Limits: these folders are fresh, not secret, so a process that a
role left running in the background could still find one; and the macOS verifier can still write
`/tmp` itself.
Codex checkers use a named read-only filesystem profile with no additional write roots.
Their native sandbox permission is distinct from the later mutation checks. Checkers inspect deterministic verifier
evidence and may run read-only probes; checks needing output files run through the verifier.
Both roles start fresh; their receipts, not conversational memory, are the handoff.
The autonomous controller and `agentsmith evaluate` share the same immutable native-launch helper
for command construction, structured-output parsing, usage extraction, sandbox settings, and the
subprocess environment allowlist; neither runner imports the other's mutable state machine. Codex
and Claude roles receive the controller's effective `core.autocrlf` value plus `gc.auto=0` and
`maintenance.auto=false` as process-local Git overrides. This keeps their commits and the
controller's clean-worktree check on the same text-conversion rule, while suppressing
role-triggered automatic repacking between the controller's protected Git snapshots. Explicit or
external maintenance may still trip the fail-closed object-store guard. Git documents
[automatic maintenance after writing commands](https://git-scm.com/docs/git-maintenance#_description).
Codex
invocations use a temporary client home containing a same-filesystem authentication bridge to the
validated ChatGPT login plus minimal no-telemetry configuration. The bridge preserves one OAuth
refresh state and is removed after the process exits; global instructions, user settings, hooks,
plugins, apps, and MCP servers never enter the role environment, and non-ChatGPT authentication
fails closed.

Claude role settings explicitly set `disableAllHooks: true`, exclude user/project setting sources,
and supply an empty strict MCP configuration. The [Claude hook reference](https://code.claude.com/docs/en/hooks)
documents the session override. Managed host policy remains part of the trusted native-client boundary;
generated settings are offline evidence, not proof of native tool denial.

### Infrastructure failures and the circuit breaker

A role can fail for a reason that says nothing about the work: the client lost its network
connection, its sign-in expired, the service was overloaded, its sandbox did not start, or the
client crashed. When a role exits without a receipt and the failure matches a short, fixed list,
the controller relaunches the same role in the same attempt, so the failure does not use up one
of the three attempts. The list (`INFRASTRUCTURE_FAILURES` in the controller) is matched only
against the client's standard error and its own error records (a Codex `error` or `turn.failed`
event, a Claude `result` marked `is_error`), never against model or tool output. A client killed by
a signal it did not get from the controller also counts. Anything not on the list is an ordinary
failure and escalates as before.

The breaker stops the run, as `escalated`, when the same failure happens twice in a row or after
three infrastructure failures in a row. The message names the failure and says that no attempt
was spent; the state records it as `infrastructure_stop`, and the events file has one
`infrastructure_failure` event per failure. A maker is relaunched only from the same clean start:
if the failed maker moved `HEAD` or left changes, the run escalates for review instead. Fix the
cause, then `resume`; resuming starts the count again and reruns the same attempt, so the
failure still costs no attempt. In a work graph, a child stopped this way
halts new child launches (see [parallel work graphs](24-parallel-work-graphs.md)).

Permission denials are counted when a Claude role ends: Claude Code lists the tool calls it
denied in its final result (`permission_denials`), and the controller records the number in the
role's exit record. A Claude checker that accepts after even one denied call is not trusted. A
read-only checker has no allowed use for an edit, a write, network or a connector, so a denial
means its investigation left its contract. The controller treats that as the infrastructure
failure `permission-denials` and starts a fresh checker. The same result twice in a row stops the
run. A checker that rejects keeps its rejection. A maker's denials are only recorded, because the
verifier and the checker still judge its candidate. The verifier is a plain shell command with no
tool permissions, so it has no denials to report. Two gaps remain. Nothing stops a role while it
runs, because Claude reports single denials only in streamed output (`stream-json`), which these
roles do not use. And Codex documents no denial event, so Codex roles are not covered.

## Operations and recovery

The controller and manifest template are scaffolded only for `software-dev` projects in v1; the
Wayfinder spec flow remains available to every work type.

**Kill switch.** While the file `.harness/AUTONOMY_PAUSED` exists, in the checkout you run from
or in the main checkout, `prepare`, `start` and `resume` refuse, and so do `agentsmith graph
start` and `graph resume`. The refusal names the file. A run that is already live keeps running;
use `stop <id>` to end it. Delete the file to allow new work again. The name matches ignoring
case (`autonomy_paused` also pauses) on every filesystem, so the rule does not depend on the disk. Each
refusal is recorded as an `autonomy_pause_refused` event in `agentsmith-factory/events.jsonl` in
the Git folder, which `agentsmith factory readiness` reads as evidence that the switch works. Roles
cannot write that folder, and the Git checks around each role allow only appends to its known
logs there: a new file, a link, or a rewritten log refuses the run. Leave it untracked: graph
validation ignores exactly this path, so `graph status` still works while autonomy is paused.

`status <id>` reads controller state from the repository's git-common directory. `start` and
`resume` hold one per-run lifecycle lock, so a second live controller is refused; a dead owner's
lock is reclaimed only after its PID is demonstrably gone. Resume also checks the original spec
file against its committed contract, using Git text normalization so Windows line endings remain valid. While starting or resuming, the short
repository coordination lock serializes the live-scope scan and lifecycle-state transition, then
releases before model execution. A conflict names the other run and overlapping path prefix or
resource. On Windows, lock acquisition and release retry brief file-sharing denials from
competing readers; a persistent denial still fails closed. Malformed live scope fails closed;
a demonstrably dead
controller and a stopped run do
not block new work. `stop <id>` atomically writes a stop
request, terminates the active process group and signals the controller, then waits up to five seconds for the controller
to persist `interrupted`. The controller's signal handler only records the stop and ends the
active process group; it never raises, because an exception from a signal handler can land
inside library code. The controller acts on the stop at its next safe point:
- while a role or verifier runs, checked every half second; a process that ignores the signal
  is then killed;
- a saved stage checkpoint;
- the moment before the acceptance or attempt-cap record;
- a wait for a Git phase or the coordination lock.

It never acts inside a Git call or a lock release.
`stop` never writes `state.json` itself. If the controller has already died,
the request remains in place and `resume` reconciles the interruption after acquiring the stale
lock. A run that has already recorded `accepted` or `escalated` keeps that result: a stop that
arrives later changes nothing, and `stop` reports the finished result instead.

`resume <id>` works only when the committed manifest, accepted spec, base commit, recorded branch,
and worktree still match and the worktree is clean. A changed contract requires a new run ID rather
than silently moving the goalposts. The original deadline and accumulated Claude/Codex usage remain
authoritative across every resume; pausing does not reset either budget.

The durable `stage` distinguishes making, candidate validation, verification, checking, and retry.
If a completed maker candidate was checkpointed, resume revalidates its exact commit, receipt,
scope, protected inputs, and Git transition, reruns verification, and launches a fresh checker
within the same attempt. It removes an abandoned checker worktree only after proving its generated
path, repository, and candidate identity. When a stop interrupted that removal after the checker
folder was gone, resume also removes the checker's leftover entry under `.git/worktrees`, but only
when the entry is unlocked and names the missing folder. An unfinished maker that advanced HEAD
without a validated receipt requires operator review; a dirty worktree or a surviving role process
group blocks recovery. Legacy checking states without a candidate checkpoint also require review.

Raw stdout/stderr stream to durable files; launch and exit records retain process IDs and exit
codes. Repeated verification/checker invocations archive their earlier artifacts under `archive/`.
After a hard crash, emitted usage is replayed once from the retained log. `usage_accounting_incomplete`
marks that any unreported spend remains unknown. The checker/verification budget reserve and the
full native-client crash/timeout pilot remain separate foundation gates. Process groups cover
ordinary descendants; detached daemons and hostile process interference require host-level isolation.
Native Windows starts fail closed until native role containment is qualified; standalone Windows
verifier support is unchanged.

An accepted run prints the branch, commit, worktree, and evidence for human review. An escalated
run prints the exact boundary that stopped it. Nothing leaves the machine until the operator
separately authorizes the relevant external action.

### Hidden acceptance tests (opt-in)

A run can add acceptance tests that neither role ever sees. They must be written by a person and
kept in a private local clone outside the repository and outside the run worktree. Name them in
the manifest:

```json
"hidden_tests": {"repo": "/absolute/path/to/private-tests", "commit": "<full commit sha>",
                 "command": ["python3", "{hidden}/run_hidden.py", "{token}"], "tiers": ["C"]}
```

`prepare`, `start` and `resume` refuse when the clone is missing or inside the repository or run
worktree, when the commit does not exist there, or when a field is malformed. The clone must be a
standalone repository: its Git folder inside it, not a worktree of the run's repository, and no
objects borrowed from or lent to another repository (`objects/info/alternates`). Otherwise the
hidden commit's objects would sit where a maker can read them with `git show`. The hidden commit may hold
only plain files and folders. No message that a run saves names a hidden file: if the suite
cannot be prepared, the run records "hidden acceptance tests could not be prepared" with a
short reference, and you see the detail by running `git archive` on the clone yourself. When the verifier
passes and the run's risk tier (computed as at acceptance) is in `tiers`, the controller copies
the candidate's files and that commit's files into two separate folders in a fresh temporary
folder and runs `command` in the verifier sandbox, with the candidate's copy as its working
folder. `{hidden}` names the hidden suite's folder, which the run can read but not write, and no
candidate file can join it; a candidate path under `.agentsmith-hidden-tests/` is refused like
other protected inputs. `{token}` is a random token made for this run, and the command must pass
it to the hidden harness. The run passes only when the command exits 0 and prints
`AGENTSMITH-HIDDEN-PASS <token>` on a line of its own, which the harness does when every hidden
test ran. This stops a candidate that ends the test process early with success, but candidate code
that the tests import runs in the same process and could read the token from its arguments: the
marker is a guard against accidents and early exits, not a boundary against a deliberate attack.
The hidden run may write only its own copy and its private home and temporary folders, all
removed afterwards: unlike the ordinary macOS verifier, it may not write the shared `/tmp`, so
code the hidden tests run cannot leave the suite where a later maker could read it.
Neither copy is a worktree that a role sees. The verification receipt records `hidden_tests`: `pass`, `fail` or
`skipped` (with the tier and the listed tiers), the commit, the exit code, the time taken and a
hash of the output. The output itself is not stored anywhere a role can read it.

Hidden tests can only reject. A failure rejects the attempt without running the checker, and the
next maker is told only that the hidden acceptance tests failed and to re-read the acceptance
criteria, never the path, the tests or their output. A pass still needs the verifier and the
checker. Both roles are denied reading the clone (Codex with a `none` filesystem rule, Claude
with `denyRead` and `Read` deny rules). The manifest, which the maker's worktree contains, still
names the clone's path and commit, so keep the clone private on this machine. This is opt-in and
measured: the time each run spends on hidden tests is in its receipt, so you can decide whether
they earn their cost.

## Landing an accepted run

The controller never pushes, opens a pull request or merges, and no role has network access or
credentials. Landing is an attended step that the operator approves (see the autonomous-run
skill). `deliver` prepares it:

```text
python3 .agentsmith/autonomous-run.py deliver <run-id> --dry-run [--json]
```

It refuses, and names every reason, unless all of these hold:

- the run is `accepted`, and its branch `agentsmith/<run-id>` still points at the accepted commit;
- the verification receipt names that commit, the checker receipt still matches its recorded
  hash and accepts that commit, and the receipt records that the citations were checked;
- the verifier log still matches its recorded hash, and the citations that quote it still hold
  (files the verifier left in its disposable worktree are gone; they were checked at acceptance);
- the run manifest is unchanged since the run started;
- the base branch (`--base-branch`, by default the remote's `HEAD`) has been fetched, and the
  accepted diff still applies to it (`git merge-tree`, Git 2.38 or later).

It then recomputes the risk tier from the base commit with the base policy, and the recorded tier
can only rise: the result is the highest of the recorded, recomputed and declared tiers. It
reports how many commits the accepted commit is behind the base branch. It prints the exact push
command, `git push origin <accepted-commit>:refs/heads/agentsmith/<run-id>`, and a pull-request
title and body built only from receipts:

- the tier and its lenses;
- the verifier and checker evidence;
- the checker calibration status;
- the budgets used;
- the base staleness;
- the eligibility line.

Text that a model wrote, the maker summary and the checker evidence, sits in code blocks, so no
link, Markdown or `@`-mention in it takes effect. The body names no local path.

### Auto-merge eligibility

The body ends with one line, bound to the exact head commit:

```text
Auto-merge eligible: yes|no for <sha> — tier A: met; no floor path: met; ...
```

It lists six facts, each `met` or `unmet` with the reason:

1. the tier is A;
2. no changed path is on the risk map's fixed floor;
3. the checker accepted with valid citations;
4. a passing calibration matches this checker (client, model, effort and prompt);
5. the head equals the accepted commit;
6. CI is green for this commit.

The answer is `yes` only when all six are met. At dry-run time there is no CI yet, so the last
fact reads `pending CI` and the answer is `no`. After CI, run
`deliver <run-id> --eligibility --sha <sha>`: it repeats every check, reads CI with
`agentsmith ci watch` (or a saved `ci watch --json` report given with `--ci-report`), and prints
the line and body again. The line is information only: a human merges, and nothing in this
release merges automatically.

### A future auto-merge trial (not switched on)

Nothing in this release merges automatically. The eligibility line collects the data that a later,
separately approved trial would need. Such a trial must name every one of these parameters before
it starts:

- **One area:** a single path glob, such as `docs/**`, and the risk tier that applies to it. Changes
  outside the area are never eligible.
- **A dated window:** a start and an end date. When the window ends, the trial stops unless it is
  approved again.
- **Data first:** at least four weeks of eligibility lines recorded for that area before the trial
  starts, with no escaped defect in the area in that time: a defect found after merge in a change
  that the line called eligible.
- **A kill switch:** while `.harness/AUTOMERGE_PAUSED` exists, nothing merges automatically. It
  mirrors `.harness/AUTONOMY_PAUSED` and belongs to the operator.
- **An automatic rollback rule:** a revert pull request is opened when the default branch turns red
  after an automatic merge, or when a defect is traced to an automatically merged change; the
  trial then pauses until the operator reviews it.

Until such a trial is approved and built, a human merges every pull request.

## Parallel work graphs

`agentsmith graph validate --graph <repository-relative-json>` checks a clean, committed graph and
its exact manifest bytes. `agentsmith graph status --graph <repository-relative-json>` derives a
stable ready set and explains each node's prerequisite, scope conflict, child state, or missing
dependency checkpoint. Both commands are read-only. `start` dispatches local finite runs, `stop`
and `resume` retain their original limits, `integrate` verifies a local combined candidate, and
`cleanup --preview` inventories exact artifacts before `cleanup --apply` removes only clean
graph-owned checkpoint worktrees. None of these commands pushes or merges to a protected branch.
See [parallel work graphs](24-parallel-work-graphs.md) for the full lifecycle and failure gates.

Before relying on this unattended, run one report-only fixture, observe one complete maker/checker
cycle, and test `stop`. Autonomy is earned using the same ladder as the autonomous-loops profile.
The [accepted native-client qualification contract](26-native-qualification-contract.md) defines the bounded
host/client containment and crash/timeout matrix, required evidence and unresolved pilot gates.
The [offline qualification recorders](25-native-qualification.md) freeze required variants and raw
evidence. Fixture completeness and passing native inference results are separate gates.

The installed controller is refreshed on reinstall; existing project manifest drafts are
preserved. Installation refuses symbolic links in the controller or manifest-template destination
paths before copying runtime payloads.

Before `start` creates a branch, worktree or state, it runs one trivial command for each role
under the operating-system sandbox that role's shell commands use (Seatbelt on macOS,
bubblewrap on Linux), with the role's write access: the maker may write the checkout, the
checker may not. It then runs one command through the verifier sandbox, in a throwaway
repository. `graph start` runs that verifier probe once before it dispatches any child, and its
children keep only the per-role probes: on Windows the verifier probe is slow and holds a
machine-wide lock, and one probe per child made parallel roots wait for each other. If any of them cannot
run, for example because host policy forbids a nested sandbox, `start` refuses and names the
role and the reason, before any model spend. This proves the sandbox starts on this host; it
does not prove a native client's own tool policy, which the qualification contract covers.

Native role preflight currently permits macOS with `sandbox-exec` and Linux with `bubblewrap`.
Windows has a separate AppContainer verifier, but native role trusted-state containment is
unsupported and production role launches are refused. Provider-free Windows graph fixtures
substitute only the role preflight and keep the real Git/verifier checks; their results cannot
qualify native model tools.
