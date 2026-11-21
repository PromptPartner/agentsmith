# Factory readiness and numbers

`agentsmith factory` answers three questions about autonomous work in a repository:

- Is the repository ready for wider autonomy?
- What do the numbers say so far?
- Which runs need a person now? (`sweep`)

The answers are derived each time from what is already recorded: run state and `events.jsonl`,
two operator logs, and read-only GitHub reads through `gh`. Nothing is kept as a board.
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
```

`--target <repository>` points any of them at another checkout. CI is read for the GitHub
repository of that checkout's `origin` remote, never for the folder you run the command from.
Without `gh`, when it is not signed in, or when `origin` is not on GitHub, the checks and numbers
that need CI say so, and the rest still run.

## Readiness

Each check passes or fails with its evidence, and a failing check names the next step. The
exit status is 0 when every check passes and 1 otherwise.

| Check | Passes when |
|---|---|
| Default branch green | Every completed push run on the default branch in the last `--green-days` days (default 7) is green, and there is at least one. |
| CI headroom | For each of Windows, macOS and Linux, the latest job of each workflow stays under `--headroom` (default 70%) of its `timeout-minutes`. The operating system comes from the job name, and the timeout from the workflow file at the base: a number, or the `matrix.os == '<os>' && <a> \|\| <b>` form; a job without the key has GitHub's default of 360 minutes. When the workflow, the job or the value cannot be read, the timeout is unknown and the check fails. |
| Checker can execute on this host | The checker and verifier sandboxes run one command, as `start` checks before a run. Needs `--manifest`. |
| Checker calibration passed | A passing calibration matches the manifest's checker (client, model, effort and checker prompt); see `calibrate` in [autonomous runs](21-autonomous-runs.md). |
| Kill switch tested | At least one `autonomy_pause_refused` event is recorded with its facts: the refused command, the run or graph ID, the marker at `.harness/AUTONOMY_PAUSED` of this checkout or its main checkout, the marker's modification time (no later than the refusal) and a time that is not in the future. |
| Pipeline guard in the verifier | `.harness/verify.conf` at the base runs `autonomous-run.py check-specs`. |
| Risk policy and lens file at the base | `.harness/risk-policy.json` is a valid [risk policy](29-risk-map.md) and `.harness/lenses.json` exists, both at the base. The lens file's format comes with the review lenses; until it is committed, this check fails. |
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
| Accepted without human rework | Share of finished runs (accepted, escalated or interrupted) that were accepted with no operator touch. |
| Defects found after merge, per tier | The operator's defect log against the landed changes of each tier (the tier each run recorded). |
| Operator touches per landed change | `run_escalated`, `run_interrupted` and `run_resumed` events of the runs that reached acceptance, per accepted run. Delivery consents will count too once they are recorded. |
| Human minutes per landed change | The operator's minutes log, over the landed changes that have minutes logged. |
| Time the default branch spends red | Completed push runs on the default branch, plus the last run of each workflow before the window: the hours, and the share of the window, during which the latest run of any workflow was failing. It is an upper bound when pushes are sparse, because a failing workflow counts as red until its next run. |
| Spend per landed change | All Claude USD and Codex tokens of every run in the window, divided by the landed changes. A run whose spend is missing or marked incomplete is left out of both sides and counted in the detail; unknown spend is never counted as zero. |

A landed change is an accepted run here: what happens after the pull request is up to a person.

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

`factory export <folder>` writes one JSON file per run (its state, events and receipts) and one for
the factory logs, to a folder outside the Git folder that is empty or does not exist yet. Use it to
keep the record beyond the repository's Git folder.
Export redacts rather than refuses: your home folder becomes `~`, and text that looks like a
secret (the secret scanner's patterns, GitHub tokens, and `secret`, `token`, `password` or
`api_key` assignments) becomes `[redacted: <kind>]`. It prints how many values it redacted.
The home folder is found in any letter case, with `/` or `\` (also doubled), and in the
Windows forms `\\?\C:\Users\you` and Git Bash's `/c/Users/you`. The separator after it stays as
written, so `C:\Users\you\repo` becomes `~\repo` and `C:/Users/you/repo` becomes `~/repo`.
A folder whose name only starts with yours (`you2` next to `you`) is left alone. Redaction is
pattern-based, so read an export before you share it.
