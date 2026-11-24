# Factory readiness, numbers and intake

`agentsmith factory` answers three questions about autonomous work in a repository:

- Is the repository ready for wider autonomy?
- What do the numbers say so far?
- Which runs need a person now? (`sweep`)

It also takes in one GitHub issue at a time as untrusted input, with your verdict on it
([intake](#intake)).

The answers are derived each time from what is already recorded: run state and `events.jsonl`,
two operator logs, the review-lens triage record, and read-only GitHub reads through `gh`. Nothing is kept as a board.
`readiness`, `numbers` and `sweep` write nothing in the repository or its Git folder and switch
nothing on.
One exception, isolated: the checker preflight in `readiness` runs one command through the verifier
sandbox in a throwaway folder that it creates in the system temporary folder and removes again.

```sh
agentsmith factory readiness --manifest .harness/runs/<run-id>.json [--base origin/main] [--json]
agentsmith factory numbers [--since 2026-10-01] [--json]
agentsmith factory sweep [--stall-minutes 30] [--base main] [--json]
agentsmith factory export <folder>
agentsmith factory defect add <merged-commit-sha> --tier B [--note "what broke"]
agentsmith factory minutes add <run-id> <minutes>
agentsmith factory intake <issue> [--verdict ACCEPT|ACCEPT-RESCOPED|NEEDS-INFO|REJECT] [--draft-spec <path>] [--json]
```

`--target <repository>` points any of them at another checkout. CI is read for the GitHub
repository of that checkout's `origin` remote, never for the folder you run the command from.
Without `gh`, when it is not signed in, or when `origin` is not on GitHub, the checks and numbers
that need CI say so, and the rest still run.

## Readiness

Each check passes, fails or warns, with its evidence, and a check that does not pass names the
next step. A warning names a risk that does not hold readiness back. The exit status is 0 when no
check fails and 1 otherwise. In `--json`, each check's `status` is `pass`, `fail` or `warn`.

| Check | Passes when |
|---|---|
| Default branch green | Every completed push run on the default branch in the last `--green-days` days (default 7) is green, and there is at least one. |
| CI headroom | For each of Windows, macOS and Linux, the latest job of each workflow stays under `--headroom` (default 70%) of its `timeout-minutes`. The operating system comes from the job name, and the timeout from the workflow file at the base: a number, or the `matrix.os == '<os>' && <a> \|\| <b>` form; a job without the key has GitHub's default of 360 minutes. When the workflow, the job or the value cannot be read, the timeout is unknown and the check fails. |
| Checker can execute on this host | The checker and verifier sandboxes run one command, as `start` checks before a run. Needs `--manifest`. |
| Checker calibration passed | A passing calibration matches the manifest's checker (client, model, effort and checker prompt); see `calibrate` in [autonomous runs](21-autonomous-runs.md). |
| Client versions | Each native client the manifest's roles name (both Claude Code and Codex without `--manifest`) is at its minimum version or later: Claude Code 2.1.319, which carries the fix for the worktree sandbox escape, and Codex 0.167. The client is the one a run launches (`AGENTSMITH_CLAUDE_BIN` or `AGENTSMITH_CODEX_BIN`, else `claude` or `codex` on `PATH`), asked for `--version`. The version read is the one next to the client's own name (`2.1.327 (Claude Code)`, `Claude Code 2.1.318`, `codex-cli 0.169.0`); when the name is not in the output and it holds exactly one version, that one. A prerelease is one or more non-empty, dot-separated identifiers of letters, digits and `-` (`2.1.319-beta.1`), and counts as below its release. Anything else, such as `2.1.319-` or `2.1.319-beta_1`, is unreadable. A client that is not found, or whose version cannot be read, fails the check: an unknown version is never a pass. |
| Clients installed as a command-line tool | Warns, and never fails, when a client is a binary bundled with an editor's marketplace extension: its path, or the path its link points to, is inside the `extensions` folder of one of these editor folders: `.vscode`, `.vscode-insiders`, `.vscode-server`, `.vscode-server-insiders`, `.vscode-oss`, `.cursor`, `.cursor-server`, `.windsurf`, `.windsurf-server` or `.positron` (for example `~/.vscode/extensions` or `~/.cursor/extensions`). Other folders named `extensions` do not count. The editor updates or removes that binary on its own schedule, so the version checked above can change under a run. Install the command-line client and point `AGENTSMITH_CLAUDE_BIN` or `AGENTSMITH_CODEX_BIN` at it. |
| Kill switch tested | At least one `autonomy_pause_refused` event is recorded with its facts: the refused command, the run or graph ID, the marker at `.harness/AUTONOMY_PAUSED` of this checkout or its main checkout, the marker's modification time (no later than the refusal) and a time that is not in the future. |
| Pipeline guard in the verifier | `.harness/verify.conf` at the base runs `autonomous-run.py check-specs`. |
| Risk policy and lens file at the base | `.harness/risk-policy.json` is a valid [risk policy](29-risk-map.md) and `.harness/lenses.json` exists, both at the base. The lens file's format comes with the review lenses; until it is committed, this check fails. |
| Policy and lens paths match files at the base | Every path pattern of every risk-policy rule, and every trigger path of every lens, matches at least one file committed at the base, with the [risk map](29-risk-map.md)'s glob rules (case ignored). Every lens must-read document is a file at the base. A pattern that matches nothing has drifted from the tree it was written for, so the change it should catch goes unclassified: the check fails and names each dead pattern with its rule number or lens ID. It also fails when the policy or the lens file is missing or invalid, because there is nothing to check. Only committed files count, not the work tree. |
| Receipts exportable | Every run's state, events and receipts read as JSON, so `factory export` can write them out of the Git folder. |

To exercise the kill switch on purpose, create `.harness/AUTONOMY_PAUSED`, try a `start`, see it
refused, and remove the file. The refusal is recorded in `agentsmith-factory/events.jsonl` in
the Git folder. That log is local and anyone with write access to the Git folder can add to it, so
a record is evidence, not proof: readiness checks the facts it can, and a bare or inconsistent
record does not count.

## The six numbers

Each number states its data window (default: the last 28 days, or from `--since`) and its sample
size `n`. Below 5 cases it says `insufficient data` instead of a value that looks precise. A run
counts in the window when it started there.

| Number | From |
|---|---|
| Accepted without human rework | Share of finished runs (accepted, awaiting-human, escalated or interrupted) that were accepted with no operator touch. |
| Defects found after merge, per tier | The operator's defect log against the landed changes of each tier (the tier each run recorded). |
| Operator touches per landed change | `run_escalated`, `run_interrupted` and `run_resumed` events of the runs that reached acceptance, per accepted run. Delivery consents will count too once they are recorded. |
| Human minutes per landed change | The operator's minutes log, over the landed changes that have minutes logged. |
| Time the default branch spends red | Completed push runs on the default branch, plus the last run of each workflow before the window: the hours, and the share of the window, during which the latest run of any workflow was failing. It is an upper bound when pushes are sparse, because a failing workflow counts as red until its next run. |
| Spend per landed change | All Claude USD and Codex tokens of every run in the window, divided by the landed changes. A run whose spend is missing or marked incomplete is left out of both sides and counted in the detail; unknown spend is never counted as zero. |

A landed change is an accepted run here: what happens after the pull request is up to a person.

### Rework and review numbers

Five more numbers say why work was redone and whether the human gate is real. They follow the
same rules: the same window, a stated `n`, and `insufficient data` below 5 cases. Each is derived
from run state and `events.jsonl`, the minutes log and the lens triage record; no file stores them.
In `--json` they are rows of `numbers` like the six above.

| Number | `n` counts | From |
|---|---|---|
| Rework causes | rejections | Every `attempt_rejected` event of the runs in the window, counted by its `reason` (`verify`, `checker`, `hidden-tests`, `incomplete`, `hidden-test-probe`, `scope`, `protected`, `budget`, `stale`; see [rejection reasons](21-autonomous-runs.md)). A rejection recorded before reasons existed counts as `unrecorded`. |
| Spend split, making and verifying | runs with known spend | The `usage_recorded` events of each run: the maker's spend is making, the checker's is verifying, in Claude USD and Codex tokens, with the verifying share of each. Runs with unknown spend are left out, as for spend per landed change. Lens reviews and the verify command itself spend no model budget that the run records. |
| Budget stops on runs later accepted | runs a budget stopped | Runs with an `attempt_rejected` event whose reason is `budget`, and the share of them later accepted: the run itself after a resume, or a rework of it (the `rework.of` of the manifest a run started from, followed through reworks of reworks). A manifest changed since its run started is not used. A high share says the budget stops good work. |
| Approval theatre | approvals (accepted runs) | Whether people approve without looking. An approval counts as theatre when it had 1 human minute or less logged and no rework (no operator touch and no rework run made from it), or when it was approved without its evidence being opened. It is not theatre when someone spent more than a minute or reworked it, and opened its evidence. Anything else is unknown, never "not theatre". A tier is flagged when every approval in it is theatre; one real review clears it. The overall `flag` is `true` when a tier is flagged, `false` when every tier is cleared, and `unknown` otherwise. |
| Lens addressed rate | lens findings triaged in the window | The [review lens](32-review-lenses.md) triage record: per lens, the share of its findings whose decision is `act`. A lens with fewer than 5 findings says `insufficient data` on its own. The record says what the operator decided, not that a fix landed. |

**Evidence opened.** When an accepted spec has a `## Demo` section, the controller records the
run's demonstration transcript and its SHA-256 as `demo` in the run state. Opening it appends an
`evidence_opened` event to the run's `events.jsonl` with the hash of the file opened. It counts only
when that hash is the one in `demo`: an open of another file, or of an altered one, is not an open.
In the theatre row, `evidence_opened` counts approvals `opened`, `not_opened` and `no_demo` (no
demonstration was recorded, so there was nothing to open). An approval whose demonstration was not
opened counts as theatre. One with no demonstration counts as theatre only by its minutes, and is
unknown otherwise. Until any approval in the window has a demonstration, `evidence_opened` reads
`unknown`.

## Sweep

`agentsmith factory sweep` is one read-only pass over every run in the repository. It reads each
run's state and `events.jsonl` and reports four lists:

| List | A run is on it when |
|---|---|
| Damaged | Its state or `events.jsonl` cannot be read, or its record holds values the sweep cannot use (for example a NUL in its manifest path). It is skipped with a warning that names it; every other run is still swept. |
| Stalled | It is not finished (not `accepted`, `escalated` or `interrupted`) and has had no event for more than `--stall-minutes` (default 30; a whole number from 1 to 10080, one week). A running run counts too: the point is to catch one that hangs. |
| Waiting on you | The [inbox](31-inbox.md) lists it as `damaged`, `escalated`, `dead`, `interrupted` or `accepted` (not landed). The sweep uses the inbox's own derivation, the same count the [attention budget](21-autonomous-runs.md) uses, so the three never disagree. `--base` names the origin branch that counts as landed, as in the inbox. |
| Past the round cap | Its attempt number is higher than `limits.max_attempts` in the manifest it started from. A manifest that changed since the start, or cannot be read, is not used; for a run that is not finished, the sweep warns that the cap is unknown. |

A run can be on more than one list. Each row names its next step. Text is the default, `--json`
gives the same report with `schema_version`.

**Why 30 minutes.** Each maker and checker turn writes `role_started` when it begins and
`role_completed` when it ends, so the longest normal gap between events is one role turn with its
verify. Thirty minutes flags a silent run early in the template's 480-minute wall budget, before it
has spent most of it unseen. A turn that is longer but healthy shows as stalled too; the sweep only
reports, so the cost is a look. If your turns are routinely longer, raise `--stall-minutes`.

**Exit status:** `0` nothing needs attention, `1` at least one run is on a list (a damaged run
counts), `2` the repository cannot be read or `--stall-minutes` is outside 1 to 10080. Warnings (an unreadable run, a missing origin base)
are printed but do not change the status.

**It writes nothing.** No lock, no state, no log, in the repository, in its Git folder or anywhere
else. You can run it as often as you like. It does not read GitHub.

**No daemon is shipped.** Schedule it yourself if you want it to run on its own. In an installed
project the command is `./.agentsmith/agentsmith`. A crontab line that checks every 15 minutes;
cron mails you whatever a job prints, so the report reaches you only when something needs
attention:

```sh
*/15 * * * * cd /path/to/repo && ./.agentsmith/agentsmith factory sweep > /tmp/agentsmith-sweep.txt 2>&1 || cat /tmp/agentsmith-sweep.txt
```

On macOS with launchd, save this as `~/Library/LaunchAgents/com.example.agentsmith-sweep.plist`
and load it with `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.agentsmith-sweep.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.example.agentsmith-sweep</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>-c</string>
    <string>cd /path/to/repo &amp;&amp; ./.agentsmith/agentsmith factory sweep &gt; /tmp/agentsmith-sweep.txt 2&gt;&amp;1</string>
  </array>
  <key>StartInterval</key><integer>900</integer>
</dict></plist>
```

A non-zero exit from the scheduled job means a run needs you; what you do with it (a notification,
a mail) is up to your scheduler.

## Operator logs and export

The defect and minutes logs are the operator's input, in `agentsmith-factory/` in the Git folder.
Agent roles cannot write there. `defect add` takes the full commit SHA of the merged change and
its tier; `minutes add` takes a run ID and the minutes a person spent on it. Rows are checked again when
they are read: a row without a valid time, a defect without a full commit SHA or a known tier, or
minutes that are not a number from above 0 to 1,440 is skipped, and `numbers` reports how many
rows it skipped.

`factory export <folder>` writes one JSON file per run (its state, events and receipts) and one,
`factory.json`, for the factory logs: `events`, `defects`, `minutes` and `intake` (the
[intake](#intake) verdict records). It writes to a folder outside the Git folder that is empty or
does not exist yet. Use it to keep the record beyond the repository's Git folder.
Export redacts rather than refuses: your home folder becomes `~`, and text that looks like a
secret (the secret scanner's patterns, GitHub tokens, and `secret`, `token`, `password` or
`api_key` assignments) becomes `[redacted: <kind>]`. A quoted value is redacted up to its closing
quote, spaces included; an unquoted one up to the end of its token. It prints how many values it
redacted.
The home folder is found in any letter case, with `/` or `\` (also doubled), and in the
Windows forms `\\?\C:\Users\you` and Git Bash's `/c/Users/you`. The separator after it stays as
written, so `C:\Users\you\repo` becomes `~\repo` and `C:/Users/you/repo` becomes `~/repo`.
A folder whose name only starts with yours (`you2` next to `you`) is left alone. Redaction is
pattern-based, so read an export before you share it.

## Intake

`factory intake <issue>` reads one issue of the GitHub repository of the `origin` remote. Name it by
number (`7` or `#7`) or by its URL; a URL of another repository is refused. The read is one
`gh issue view` call. Intake never writes to GitHub: no comments, no labels, no assignment, no state
change.

The title and body are someone else's text, so intake cleans them before you see them and labels
them untrusted. It removes:

- zero-width characters (U+200B to U+200D, U+2060 to U+2064, U+FEFF);
- bidirectional controls, overrides and isolates (U+200E, U+200F, U+061C, U+202A to U+202E,
  U+2066 to U+2069);
- the whole tag block (U+E0000 to U+E007F), which can spell text no reader sees;
- variation selectors (U+FE00 to U+FE0F, U+E0100 to U+E01EF), which can encode hidden bytes. An
  emoji only loses its presentation hint;
- every other invisible format character (Unicode category Cf), such as the soft hyphen;
- control characters other than newline and tab, so the text cannot drive your terminal;
- HTML comments. An unclosed `<!--` hides everything after it when GitHub renders it, so intake
  removes everything after it too.

The report names each kind and how many were removed. It never repeats the hidden text, so a
prompt hidden in a comment is not copied anywhere.

Without `--verdict`, intake only prints the cleaned issue and the report, and writes nothing.

The verdict is yours. Intake is deterministic tooling: it does not decide or suggest one. Pass
exactly one verdict with its own fields:

| Verdict | Required | Means |
|---|---|---|
| `ACCEPT` | nothing | The issue is ready to become a spec as written. |
| `ACCEPT-RESCOPED` | `--left-out <item>`, one or more | Accepted with a smaller scope. A rescope that does not name what it leaves out is refused. |
| `NEEDS-INFO` | `--question <text>`, one or more | The author must answer first. Intake does not post the questions; you ask them. |
| `REJECT` | `--reason <text>` | Not taken. |

A flag that belongs to another verdict is refused. Your flags and the draft path are checked before
the issue is read.

The record is appended to `agentsmith-factory/intake.jsonl` in the Git folder, outside the tracked
tree. It holds the time, the repository, the issue number, URL, cleaned title and author's login,
the SHA-256 of the cleaned body, the cleaning report, `"untrusted": true`, the verdict and the path
of any draft spec. Intake an issue again after it changes: each verdict is a new row, and the
history stays. `factory export` includes these records under `intake` in `factory.json`, redacted
like the rest of the export.

`--draft-spec <path>` goes with `ACCEPT` or `ACCEPT-RESCOPED`. It writes a new spec from the
repository's `.harness/templates/wayfinder-spec.md` (or the harness's own template), with
`status: draft`. Intake fills in only the title and a "Source issue (untrusted)" section that quotes
the cleaned body line by line. Quoting keeps the issue's own headings and list items from counting
as acceptance criteria, edge cases or non-goals. For a rescope, each left-out item becomes a non-goal.
Every other section stays for you. The path must be inside the repository and outside the Git
folder, and an existing file, or a link, is never overwritten. The path is checked before the issue
is read and again as the file is written: a folder that became a link in between is refused, and
then no record is written. On Windows a short window remains (see `KNOWN-ISSUES.md`).

A draft spec cannot start a run. `autonomous-run.py prepare` refuses it until its acceptance
criteria, edge case, non-goal, research note, review receipt, route and assumptions are complete,
and `start` refuses any spec that is not `status: accepted` with `accepted_by` and `accepted_at`.
Only a person accepts a spec.
