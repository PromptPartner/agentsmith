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
`start` refuses the same values. Before it writes anything, `prepare` also runs the spec preflight
that `start` repeats: a schema-2 spec needs at least one acceptance criterion, edge case and
out-of-scope item (`## Acceptance and evidence`, `## Edge cases`, `## Non-goals`), and each
`` `path` `` or `` `path::symbol` `` item under `## Assumptions` must still hold at `base_ref`.
A missing section or a stale assumption is refused by name, so no role starts on a spec it cannot
test. The format is in [`docs/specs/README.md`](specs/README.md). `scope.resources` optionally names local coordination keys such as
`port:3000`, `db:local/test`, or `service:redis`; omit it in an older manifest or use an empty list
when the run reserves none.

**Rework.** When a finished run needs another pass, prepare a new run with the operator's note:

```text
python3 .agentsmith/autonomous-run.py prepare --run-id <new-id> --spec docs/specs/<name>.md \
  --ticket <ticket> --rework-of <finished-run-id> --note <file in the repository>
```

The run it reworks must be finished (`accepted`, `awaiting-human`, `escalated` or `interrupted`), and it is never
reopened: a rework is always a new run with a new ID. The manifest pins the note by path and
SHA-256 in `rework`, and `start` and `resume` refuse when the note changed after `prepare`.
The maker receives the note through its prompt, marked as a rework of the earlier run. A note
may be at most 16 KB. When the rework starts, the controller keeps the note as its own file,
`operator-feedback.md`, in the new run's folder under `agentsmith-runs/`, where no role may write.
The run state records it as `operator_feedback` (the run it reworks, the file, the note's path in
the repository and its SHA-256), and the `operator_feedback_kept` event names the same hash. So the
feedback that drove a run stays with that run, even when the note in the repository changes later.
Feedback on a held or escalated run starts a fresh attempt budget: the rework is a new run, so its
attempts and its spend start from zero, and the earlier run's state is never changed.

**Attention budget.** `prepare` refuses a new run while as many runs wait on you as the risk policy
allows, and `start` checks the same limit again before it launches anything, so runs prepared while
little waited cannot all start later and bypass it. The limit is `attention_limit` in
`.harness/risk-policy.json`, default 5 (see [risk map](29-risk-map.md)). It is a work-in-progress
limit: past the number of runs you can follow, more parallel work only adds to the queue you cannot
review. A run waits on you when [`agentsmith inbox`](31-inbox.md) lists it as `damaged`,
`escalated`, `dead`, `interrupted`, `awaiting-human` (held because the checker is not calibrated)
or `accepted` (accepted but not landed, including one whose pull request is open). A run whose state cannot be read counts: damage needs a person, so the count
fails closed. The count uses the inbox's own derivation, so the two never disagree; a running run
and a landed one do not count. The refusal names the count, the limit and the next step:

```text
error: attention budget reached: 5 runs wait on you and the limit is 5 (attention_limit in
.harness/risk-policy.json); land a waiting run (`deliver`), rework it (`prepare --rework-of
<run-id>`), or delete its run branch to drop it from the inbox; `agentsmith inbox` lists them
```

- **Land** an accepted run with `deliver` (see below): once its commit is on the base branch, it
  no longer waits.
- **Rework** a waiting run with `prepare --rework-of <run-id>`. Both `prepare` and `start` allow
  it at the limit, because it turns that run into work instead of adding one. A `dead` run must
  finish first: resume it, then rework it.
- **Delete its run branch** for a run you will neither land nor rework: remove its worktree, then
  delete its `agentsmith/<run-id>` branch. The inbox then drops it, with a warning that names it,
  and it no longer counts. There is no separate command for this.

The limit is read from the policy committed at the manifest's `base_ref` (default `HEAD`), as
that ref resolves in the main checkout of the repository, not in a linked worktree. Run branches
live in linked worktrees, so a commit on a run branch cannot raise the limit that gates new runs.
Commit a change to the limit on the base in the main checkout before it applies. An invalid value
(zero, negative, text or a fraction) is refused by name. There is no override flag: to start more
work, raise the committed limit. `resume` of a run that already started is not checked, and a
graph's child runs are not checked one by one as the graph dispatches them. The limit is soft:
two `prepare` or `start` calls at the same moment can both pass one below it.

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
`CLAUDE.md`, `CLAUDE.local.md`, `GEMINI.md` or `.mcp.json` (which can start an MCP server inside
the checker's client), and anything inside a `.claude/`, `.codex/`, `.agents/`, `.cursor/` or
`.gemini/` folder (settings, hooks, skills, subagents, rules). It applies at any
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

These checks, and the scope check, read every commit from the base to the candidate, not only the
end-to-end diff. A path that one commit adds and a later commit removes, or a protected file that
one commit edits and the next restores, is still in the history that would be pushed: a secret, or
a rewritten `AGENTS.md`, in an intermediate commit. The refusal names the path and the first commit
that touched it. Symbolic links are read in every one of those commits as well.

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

**Every role report keeps one contract.** A receipt's `summary` is the role's report. Its first
line is the one line the controller reads: `VERDICT: <STATUS>`, the receipt's status in capitals
(`COMPLETED`, `ACCEPTED`, `REJECTED` or `BLOCKED`). Then comes a `## Summary` section of 3 to 5
bullets (`- `) for a person. A maker report also has an `## Assumptions without authority`
section: one bullet for each choice the maker made that the spec and ticket did not settle, or
the single bullet `- none`. Both prompts state the contract, and the controller checks every
report against it without a model:

```text
VERDICT: COMPLETED

## Summary
- Parse an empty input as an error instead of an empty list.
- Add a red test for the empty case; it failed on the old parser's IndexError.
- Run the verify command; every phase passed.

## Assumptions without authority
- An input of only whitespace counts as empty.
```

A maker report that breaks the contract (no verdict line, a verdict that is not its status, no
summary, fewer than 3 or more than 5 bullets, or no assumptions section) fails its attempt
before a verifier or a checker is spent on it. The event is `attempt_rejected` with
`reason: report contract`, and the next maker is told what was wrong. A checker acceptance whose
report breaks the contract is a checker defect, handled like one whose citations do not hold,
and calibration counts it as a wrong verdict. A rejection stays a rejection. The receipt schema
does not change. The checker prompt does, so a calibration recorded before this contract is
stale and the checker must be calibrated again.

Before the first attempt is judged, the controller runs the verify command once on the base
commit, in a disposable worktree, and stores the result with the run as `verification_baseline`
in the run state (`baseline-verify.txt` keeps the raw output, and the events file has one
`baseline_recorded`). It does this at the first verify stage, after the first maker: the base
commit cannot change, so the result is the same, and parallel runs do not delay each other's
makers (on Windows every verifier call holds one machine-wide lock). A run that stops before
its first verification takes no baseline. A resumed run keeps a stored baseline; it is never
taken again from a later tree. Once it exists, `status <id>` shows it as `verification_baseline`:
the base commit, its `verification` (`passed`, `failed` or `incomplete`), the exit code, the
reason for an incomplete result, and the `passing` and `failing` checks. Every attempt is compared with it, not with the attempt before: a check that passed on the
base commit and fails now is listed under `regressions` in the attempt's verification receipt and
in its `attempt_rejected` event, even when an earlier attempt broke it. A check is a
`scripts/verify.sh` phase, a Python `unittest` or `pytest` test named in the output, or the verify
command as a whole. A base commit that already fails does not lower the bar: only a verify
command that exits 0 can be accepted.

Each attempt's verification is `passed`, `failed` or `incomplete`. It is `incomplete` when the
verify command timed out, or when it ran an empty suite: pytest exit code 5, or output such as
`Ran 0 tests`, `no tests ran`, `collected 0 items` or `0 tests` with no count of tests that did
run. An incomplete attempt observed nothing, so it is never a pass: the controller rejects it
without launching a checker, and the next maker reads why. A timeout therefore no longer fails
the whole run by itself; the run escalates only when no wall-clock time is left for the next
attempt. On macOS and Linux the verify command runs as `bash -o pipefail -c <command>`, so
`pytest | tee log` fails when `pytest` fails. The Windows verifier runs the command through
`cmd.exe`, which has no pipefail: `pytest | more` exits with the code of `more`, so a failing suite
would pass. On Windows, `prepare`, `start` and `resume` therefore refuse a verify command that
contains `|`, and the verifier refuses it again (exit 126, never a pass) if one reaches it. A `|`
inside quotes or escaped as `^|` is refused too: a nested shell such as `cmd /c "a | b"` or
`powershell -c "a | b"` still runs it as a pipeline. Only `||` (run the next command only on
failure) is allowed. Use a single command, or a script that exits non-zero when its tests fail.
The baseline and incomplete rules are ported from
[CodeAF](https://github.com/Agent-Field/CodeAF) (Apache-2.0): `internal/verify/baseline.go` and
`internal/seniordev/app/full_verification.go`.

Every condition applies, in this order. An `incomplete` verification is rejected before the hidden
tests and before any checker. An attempt is accepted only when its verification `passed`, it has
no regression against the baseline, and a checker accepted with evidence that the citation check
trusts; a checker defect is reworked as described above. The hidden-test tripwire is checked
separately and wins over all of these.

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
of the checker prompt template, each candidate's verdict and the spend. It also records:

- the model family and version (`model_family`, `model_version`): `claude-opus-5-5` is the family
  `claude-opus` and the version `5-5`, and a name with no version part, such as the alias `opus`,
  has an empty version;
- the held-out set by its hash (`held_out_sha256`): the labelled candidates, their spec, test and
  verify command;
- `n` (the number of cases), `pass_rate` (the share judged right) and `error_budget` (the wrong
  verdicts allowed, now 0).

The status is `passed` (wrong verdicts within the error budget), `failed` (a wrong verdict, an
acceptance whose citations do not hold, or a receipt that does not name the candidate) or `error`
(the client could not run, or no case was judged). The exit code is 0, 1 or 2 to match.
`--max-usd` (default 1.0) caps Claude spend, `--max-tokens` (default 400,000) caps Codex tokens
and `--wall-minutes` (default 20) caps time. Every later run records the latest calibration for its checker client, model family,
effort and prompt hash as `checker_calibration` in its verification receipt, or
`{"status": "none"}` when none matches. A changed prompt template needs a new calibration. The
run does not trust the record's `passed` on its own word:

- A record that names another checker reads `stale`: its `client`, `effort`,
  `checker_prompt_sha256` and `model_family` must equal the configured checker's. So does a record
  whose model version or held-out set differs from the current one, or which does not name them
  (an older record). The reason is in `stale_reason`.
- A `passed` record whose score does not bear it out reads `invalid`, with the reason in
  `invalid_reason`. The score must hold: `n` is at least 1, `cases` holds exactly `n` case
  records, the wrong verdicts are within the error budget, `pass_rate` equals the share judged
  right (rounded to three places), and `error_budget` equals the controller's own budget, so a
  record cannot raise it.
- A record that is a symbolic link, is not a regular file, or is over 1 MiB is not read: it
  reads `unreadable`, as does one that is not valid JSON. No calibration file stops or crashes
  a run.

Roles cannot write the calibration folder. In a measured run on 2026-11-06, a small model
(`haiku` at low effort) failed calibration because its receipts did not name the candidate commit.

**The checker is advisory until its calibration passes.** Only a `passed` calibration lets a
checker acceptance count. The controller reads the calibration again at the acceptance decision,
because the receipt's copy was taken before the checker ran, and the record may change while it
runs. It gates on that fresh value and writes it to the receipt's `checker_calibration`. When
every other gate passes (the verifier, the baseline comparison, the citations, the stop check and
the branch check) but the calibration is `none`, `failed`, `error`, `stale`, `invalid` or
`unreadable`, the run does not become `accepted`. It ends in the held state
`awaiting-human` and exits 3:

- `held_commit` names the candidate the checker accepted, and `reason` begins with
  `checker advisory: calibration <status>`;
- the `run_awaiting_human` event records the commit and the calibration status;
- the verification receipt records `checker_advisory: true` (an accepted run records `false`).

The run is finished for the controller: the live-run guard counts it as terminal, `stop` reports
it as finished, and `resume` refuses it, because a new attempt would replace the held candidate.
There is no approve command, so `deliver` refuses it too. The next step is the same everywhere: a
human reviews and re-runs with an explicit approval. Review the held commit, run `calibrate`
until it passes for this checker, then prepare a rework of the run (`prepare … --rework-of
<run-id> --note <file>`) and start it. The inbox lists the run as `awaiting-human`. In a work
graph, such a child is `blocked`, with its reason. Choosing another model, or escalating to a
stronger one, is not automatic.

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

Only `accepted`, `awaiting-human`, `escalated` and `interrupted` runs and `completed`, `failed`, `stopped` and
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
| `claude_max_usd` | refuses a Claude role when nothing is left, and a Claude maker when only the checking reserve is left | Claude Code stops at the remaining allowance (`--max-budget-usd`); a maker's allowance stops at the reserve | escalates when reported spend is over the cap |
| `codex_goal_tokens` | refuses a Codex role when nothing is left, and a Codex maker when only the checking reserve is left | not enforced: `codex exec` documents no hard token switch, and the goal budget in the maker prompt (the maker's share, above the reserve) is advisory | escalates when reported tokens are over the cap |

**Checking reserve.** When the maker and the checker run the same runtime, they spend one cap, and
a maker could spend what the checker needs: the run would end after a maker whose work nobody
checks. So a share of that cap is held for checking: `limits.checker_reserve`, a fraction from
0.05 to 0.5 of the cap (default 0.25). The maker may spend only what is above the reserve; the
checker may spend everything that is left. A maker that would start with nothing above the reserve
is not launched, and the run escalates with "budget reserved for checking": a budget stop, not a
model failure, so the infrastructure circuit breaker does not count it. A value outside the bounds
refuses at `prepare`, `start` and `resume`, because it would leave either too little to check or
less than half to make. When the two roles run different runtimes, each cap has one spender and
nothing is reserved. The reserve is computed from the manifest and the persisted spend, so resume
applies it exactly as before the stop. A Codex maker can still overshoot into the reserve within one
role (see below); the checker then has what is left.

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
- the moment before the acceptance or attempt-cap record, and again after the last write of the
  verification receipt, just before the run becomes `accepted` or `awaiting-human`;
- a wait for a Git phase or the coordination lock.

It never acts inside a Git call or a lock release.
`stop` never writes `state.json` itself. If the controller has already died,
the request remains in place and `resume` reconciles the interruption after acquiring the stale
lock. A run that has already recorded `accepted`, `awaiting-human` or `escalated` keeps that
result: a stop that arrives later changes nothing, and `stop` reports the finished result instead.

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
marks that any unreported spend remains unknown. The checker budget reserve is described under
budgets above; the full native-client crash/timeout pilot remains a separate foundation gate. Process groups cover
ordinary descendants; detached daemons and hostile process interference require host-level isolation.
Native Windows starts fail closed until native role containment is qualified; standalone Windows
verifier support is unchanged.

An accepted run prints the branch, commit, worktree, and evidence for human review. A run held as
`awaiting-human` prints the held commit, why the checker was advisory, and the next step. An
escalated run prints the exact boundary that stopped it. Nothing leaves the machine until the operator
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

A tripwire backs up that denial. While each maker or checker runs, the controller keeps one
extra file in the clone, with a fresh random name and a fresh random canary token as its
content, and removes it when the role ends. The suite comes from `git archive` of the hidden
commit, so this untracked file never joins it, but the controller needs write access to the
clone and refuses to launch a role without it. After the role ends, the controller looks for the
token or the file's name in the role's output, its receipt, the changes it left in its worktree
(committed, uncommitted or untracked), every commit it made with its message and patch (so a
commit it reverted later still counts), and the files Git ignores in its worktree, which are read
to their end. It records a
`hidden_test_probe` event that names the role, where the hit was and whether it was the token.
Either hit is never counted as an infrastructure failure, so the role is not relaunched, and the
role's output files keep only a hash and its receipt is not saved.

- The token anywhere means the role saw held-out content. Discarding its attempt cannot undo
  that, committed or not, so the run stops with reason `hidden-test-probe` and waits for a
  person: review the run branch and replace the hidden tests before another run.
- The file's name alone, for example in the error message of a denied read, means the sandbox
  held and nothing was learned. A role can learn the name only by trying the clone, so the
  attempt fails with reason `hidden-test-probe`. Its commits stay on the run branch, as after any
  rejection, and the next maker is told that the attempt tried to read the held-out acceptance
  tests, never the token or a hidden file.

Detection uses content, not file access times, because access times are off or relaxed on most
macOS and Linux mounts. It catches a role that shows what it read, not one that reads and stays
silent, or that changes the text before showing it; the sandbox denial stays the boundary.

## Landing an accepted run

The controller never pushes, opens a pull request or merges, and no role has network access or
credentials. Landing is an attended step that the operator approves (see the autonomous-run
skill). `deliver` prepares it:

```text
python3 .agentsmith/autonomous-run.py deliver <run-id> --dry-run [--json]
```

It refuses, and names every reason, unless all of these hold:

- the run is `accepted`, and its branch `agentsmith/<run-id>` still points at the accepted commit.
  A run that is `awaiting-human` is refused with its reason and the next step: a human reviews and
  re-runs with an explicit approval;
- the verification receipt names that commit, the checker receipt still matches its recorded
  hash and accepts that commit, and the receipt records that the citations were checked;
- the verifier log still matches its recorded hash, and the citations that quote it still hold
  (files the verifier left in its disposable worktree are gone; they were checked at acceptance);
- the run manifest is unchanged since the run started;
- the base branch (`--base-branch`, by default the remote's `HEAD`) has been fetched, and is
  fresh: `git ls-remote` (read-only) shows the remote still has it at the fetched commit. A remote
  that cannot be reached, or a base that moved since the last fetch, refuses with
  `base not fresh: … run git fetch <remote>`, because a stale copy could hide a conflict;
- the accepted diff still applies to that fresh base (`git merge-tree`, Git 2.38 or later);
- nothing the push would publish holds a likely secret. The `agentsmith secret-scan` patterns run
  over the added lines of the accepted diff, over the changes of every commit between the base and
  the accepted commit (a secret that a later commit removes is still in the pushed history), and
  over every commit message, honouring `.harness/secret-scan.allow` in your checkout. This holds
  for `--dry-run` too. Each finding names the path or commit and the line, never the value;
- every package that a manifest gains between the base and the accepted commit exists in its
  registry. `deliver` reads `package.json` (npm, `registry.npmjs.org`) and `requirements*.txt`,
  `pyproject.toml` and `Pipfile` (PyPI, `pypi.org`), and looks up each new package once, as a
  read-only request with no credentials. A package the registry does not have (404) refuses: a
  model can name a package that does not exist, and whoever registers that name later decides
  what an install runs. A requirements file is read as pip reads it: continued lines are joined,
  comments are stripped, and the files it includes with `-r` or `-c` are read too, relative to
  it; a change to an included file counts as a change to the requirements file. An existing npm
  package whose spec moves to another source (a version that becomes a Git or URL source) is
  checked like a new one. An npm alias (`npm:<target>@<range>`) is looked up as its target, and
  each entry in the manifest gets its own verdict. These are *unverified* and refuse too, because
  a check that could not run never counts as a pass: a lookup that gets no clear answer; a source
  outside the registry (a Git, URL or path dependency, a Poetry or Pipfile table with any key
  other than `version`, `extras`, `markers`, `python`, `optional`, `platform` or
  `allow-prereleases`, a `[tool.uv.sources]` entry, an editable install, another index, or any
  other requirements option); an include outside the repository or missing from it; a
  requirement or environment marker that `deliver` cannot read; a manifest that does not parse or
  does not have the shape its tool reads; and a changed `go.mod`, `Cargo.toml` or `Gemfile`, which
  `deliver` cannot check. Local `file:`, `link:` and `workspace:` npm dependencies are listed but
  not looked up. The new packages and their lookup appear in the body under Dependencies;
- when the accepted commit is behind the fresh base, the merge of the two passes verification.
  A clean `merge-tree` only proves that the diff applies; the merged code can still fail a test.
  So `deliver` runs the manifest's verify command on the merge result, in the same verifier
  sandbox as the run, after every other check has passed and before it prints anything to land.
  The merge is built in a private object folder and checked out into a throwaway folder under
  `/tmp`, which is removed afterwards. It is not a `git worktree`, because a new worktree or
  object would change the Git metadata that parallel runs compare to catch tampering; the
  repository gains nothing. A merge that fails (or whose verification is incomplete) refuses with
  `the accepted commit merged with <remote>/<base> fails verification`. The outcome, the base
  commit, the merge tree and the output hash are in the `--json` report under
  `merge_verification`, and the body's Base section says that the merge passed.

It then recomputes the risk tier with the policy at the base commit, over every path that any
commit between the base and the accepted commit touches (renames, copies and each side of a merge
included), not only the final diff: the push publishes each of those commits, so a floor path
added and removed again still counts. The recorded tier can only rise: the result is the highest of the recorded, recomputed and declared tiers. It
reports how many commits the accepted commit is behind the base branch. It prints the exact push
command, `git push origin <accepted-commit>:refs/heads/agentsmith/<run-id>`, and a pull-request
title and body built only from receipts.

The push command is for a POSIX shell (sh, bash, zsh), and every value in it is quoted. Git
accepts remote and branch names that a shell would run, such as `origin;id`, so `deliver` also
refuses a remote, run branch or base branch whose name uses anything other than letters, digits,
`.`, `_`, `-` (and `/` in a branch), or that `git check-ref-format` rejects. A name that passes
needs no quoting, so the same command also works in PowerShell. The pull-request title is the
implementation ticket and the run branch. The body holds:

- the paths that Git reports as changed;
- the tier and its lenses;
- the reviewer focus: every path above tier A, highest tier first, with the policy rules, floor
  reasons and lenses that raised it, or a line saying that every path is tier A;
- the verifier and checker evidence;
- the assumptions made without authority: the bullets under `## Assumptions without authority` in
  the accepted attempt's maker report, or "The maker's report lists none.";
- the checker calibration status. When it is not `passed` (for example, the record went stale
  after the acceptance), the body says the checker is advisory ("checker advisory");
- the models used: each role's client, model and effort as its launches recorded them in
  `attempt-N-<role>-exit.json`, with the attempts that used them;
- the budgets used;
- the new packages and their registry lookup, when a manifest gained any;
- the base staleness, and the merge verification when the accepted commit is behind the base;
- the eligibility line.

The rest of the maker's report is left out. The only text that a model wrote is the checker
evidence and the maker's assumptions, and each sits in a code block, as do the changed paths, the
reviewer-focus paths and the model names, so no link, Markdown or `@`-mention in them takes
effect. Paths inside the repository become repo-relative, and home and temporary
folders become `~` and `$TMPDIR`, so neither the text nor the `--json` report names a local path.
The secret scanner's patterns then run over the final title and body (honouring
`.harness/secret-scan.allow`), and a likely secret refuses delivery and names the field.

### Auto-merge eligibility

The body ends with one line, bound to the exact head commit:

```text
Auto-merge eligible: yes|no for <sha> — tier A: met; no floor path: met; ...
```

It lists six facts, each `met` or `unmet` with the reason:

1. the tier is A;
2. no path that any pushed commit touches is on the risk map's fixed floor;
3. the checker accepted with valid citations;
4. a passing calibration matches this checker (client, model, effort and prompt);
5. the head equals the accepted commit, and after CI the remote branch is still at it (read with
   `git ls-remote`, so a force-push shows);
6. CI is green for this commit, on the run's own branch, in the remote's GitHub repository.

The answer is `yes` only when all six are met. At dry-run time there is no CI yet, so the last
fact reads `pending CI` and the answer is `no`. After CI, run
`deliver <run-id> --eligibility --sha <sha> --pr <number>`: it repeats every check, reads CI for
that pull request with `agentsmith ci watch` (which counts only runs on the pull request's own head
branch), and prints the line and body again. A saved `ci watch --pr <number> --json` report can
stand in for `--pr` with `--ci-report <file>`; it counts only if its `sha`, `repo` and `branch`
name the accepted commit, the remote's GitHub repository and the run branch, so a report without
those fields, or from another branch or repository, leaves the CI fact unmet. The line is information only: a human merges, and nothing in this
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
