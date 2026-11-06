# Factory readiness and numbers

`agentsmith factory` answers two questions about autonomous work in a repository:

- Is the repository ready for wider autonomy?
- What do the numbers say so far?

Both answers are derived each time from what is already recorded: run state and `events.jsonl`,
two operator logs, and read-only GitHub reads through `gh`. Nothing is kept as a board.
`readiness` and `numbers` write nothing and switch nothing on.

```sh
agentsmith factory readiness --manifest .harness/runs/<run-id>.json [--base origin/main] [--json]
agentsmith factory numbers [--since 2026-10-01] [--json]
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
| CI headroom | For each of Windows, macOS and Linux, the latest job of each workflow stays under `--headroom` (default 70%) of its `timeout-minutes`. The operating system comes from the job name, and the timeout from the workflow file at the base: a number, or the `matrix.os == '<os>' && <a> \|\| <b>` form; otherwise GitHub's default of 360 minutes. |
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
| Time the default branch spends red | Completed push runs on the default branch: the hours, and the share of the window, during which the latest run of any workflow was failing. |
| Spend per landed change | All Claude USD and Codex tokens of every run in the window, divided by the landed changes. A run whose spend is missing or marked incomplete is left out of both sides and counted in the detail; unknown spend is never counted as zero. |

A landed change is an accepted run here: what happens after the pull request is up to a person.

## Operator logs and export

The defect and minutes logs are the operator's input, in `agentsmith-factory/` in the Git folder.
Agent roles cannot write there. `defect add` takes the full commit SHA of the merged change and
its tier; `minutes add` takes a run ID and the minutes a person spent on it.

`factory export <folder>` writes one JSON file per run (its state, events and receipts) and one for
the factory logs, to a folder outside the Git folder that is empty or does not exist yet. Use it to
keep the record beyond the repository's Git folder.
Export redacts rather than refuses: your home folder becomes `~`, and text that looks like a
secret (the secret scanner's patterns, GitHub tokens, and `secret`, `token`, `password` or
`api_key` assignments) becomes `[redacted: <kind>]`. It prints how many values it redacted.
Redaction is pattern-based, so read an export before you share it.
