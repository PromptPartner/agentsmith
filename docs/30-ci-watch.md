# CI watch

`agentsmith ci watch` follows continuous integration for one commit and ends in exactly one named
state with one next step. It is report-only: it never fixes, pushes, comments, labels, reruns or
cancels anything. It reads GitHub through the [GitHub CLI](https://cli.github.com) (`gh`), which
must be installed and logged in (`gh auth login`).

```sh
agentsmith ci watch --pr 67
agentsmith ci watch --sha 884ab3cfbaf1b05e7557712c2108a99b0284c9fe --repo owner/name --json
agentsmith ci watch --pr 67 --cap-minutes 45 --stall-minutes 20
```

`--repo` defaults to the repository `gh` finds in the current folder. With `--sha`, the base
branch is the repository's default branch unless `--base` names another one.

## How it watches

1. **Conflicts first.** With `--pr`, a pull request that conflicts with its base ends as
   `conflict`, and no run is read: a conflicting pull request gets no run, so waiting for one
   would end in a false result. While GitHub is still computing mergeability, the watch waits.
2. **The runs for the exact head commit.** It lists the workflow runs registered for the head
   SHA and follows those runs and their jobs. With `--pr`, a run counts only when it also comes from the pull
   request's head branch and head repository: the same commit pushed to another branch or a fork
   does not test this pull request. It never reads the pull request's aggregate check
   view: right after a push, that view can still show the previous commit's green checks before
   the new run exists.
3. **One wall-clock cap.** Polls are 30 seconds apart. The cap (`--cap-minutes`, default 60)
   bounds the whole watch, including the time GitHub takes to answer: every `gh` read gets a
   timeout of the time left, and the deadline is checked after each read.
4. **One end state.** When every run is complete, or something decides the outcome earlier,
   the watch stops and prints the state and its next step. With `--pr`, the head is read again on every poll and once
   more before any end state is reported, so a push during the watch ends it as `head-moved`.

## End states and exit codes

| State | Exit | Meaning |
|---|---|---|
| `green` | 0 | Every run for the commit completed with its jobs listed, and every job passed or was skipped. A completed run whose job list is empty or still running is read again, not counted as green. |
| `red-at-diff` | 10 | A job failed in the project's own steps, and it does not fail on the base branch. |
| `red-on-base` | 11 | The failing job also fails on the base branch's latest completed push run of the same workflow. |
| `flaky` | 12 | The failing job passed on an earlier attempt of the same run, or in another run of the same workflow and event for this commit. |
| `environment` | 13 | A job timed out, was cancelled, or could not start, or it failed while every step so far was runner setup (`Set up job`, checkout, `setup-*`, cache or artifact actions), so none of the project's own steps had run. |
| `runner-stalled` | 14 | A run that is queued or in progress has shown no progress (no job or step started or finished) for `--stall-minutes` (default 30). |
| `no-run-registered` | 15 | No run exists for the commit 5 minutes after the watch started, or when the cap is reached. |
| `conflict` | 16 | The pull request conflicts with its base. |
| `cap-reached` | 17 | Runs were still going when the cap was reached. |
| `head-moved` | 18 | With `--pr`: the pull request's head commit changed during the watch. Results about the old head are stale, so none is reported; watch the new head. |

Exit status 2 means the watch could not run: `gh` is missing or not logged in, the arguments are
wrong, or a read from GitHub failed.

When jobs fail for different reasons, the state is the most actionable one, in this order:
`red-at-diff`, `red-on-base`, `environment`, `flaky`. Every failing job is still listed with its
own category in the report.

A failure after the project's own steps have run is `red-at-diff`, even in a setup-like step
such as an artifact upload or a post step. The watch cannot tell a broken artifact path or a
test that leaves bad files behind from a storage outage, and the change is the first suspect once
its commands have run; calling it `environment` would invite a rerun that hides a real defect.

`flaky` is detected without rerunning anything. A `pull_request` run tests the merge of the
change with its base, so a job that passes on the `push` run and fails on the `pull_request` run
is not counted as flaky: the base may be the difference. A rerun needs the operator's go-ahead.

## Report

`--json` prints one line of ASCII JSON with sorted keys: `state`, `exit_code`, `next_step`,
`repo`, `pr`, `sha`, `base`, `branch` (the pull request's head branch; `null` for `--sha`),
`elapsed_seconds`, `schema_version`, and `runs`, where each run has
its `id`, `workflow`, `event`, `attempt`, `status`, `conclusion` and `failing_jobs` (each with
`id`, `name` and `category`).

The gh calls it makes are `gh auth status`, `gh repo view`, `gh pr view`, and read-only
`gh api` GET requests: the commit's runs, the jobs of each run attempt, and the base branch's
latest completed push run of the same workflow. Runs and jobs are read in full with `--paginate`;
when GitHub reports more items than were read, the watch stops with exit status 2 rather than
decide on a partial list.
