# Inbox

`agentsmith inbox` lists everything that waits on you. It is derived from run, graph, spec and Git
state on every call. There is no stored board, and listing writes no file: not in the working
tree, not in the Git directory.

```sh
agentsmith inbox
agentsmith inbox --json
agentsmith inbox --issues                 # also read open GitHub issues, read-only
agentsmith inbox claim 12                 # claim issue 12 locally
agentsmith inbox release 12
```

## Rows

| Kind | Waits on you because | Re-checked against Git |
|---|---|---|
| `damaged` | A run's state cannot be read, holds values of the wrong type, or has an unknown status. Damage fails closed: the run is listed, and counts for the attention budget, until you repair its state or move its folder out of `agentsmith-runs`. | Nothing to check: the record itself is the problem. |
| `escalated` | An autonomous run stopped at a boundary it may not cross. The next step quotes its reason. | Its branch and base commit exist. |
| `dead` | A run is unfinished (`prepared`, `making`, `checking`, `retrying`, `resuming`) but neither its controller nor its role process is alive. | Its branch and base commit exist. |
| `interrupted` | A run was stopped and can be resumed or discarded. | Its branch and base commit exist. |
| `awaiting-human` | A run's checker accepted, but its calibration has not passed, so the checker is advisory and the run is held. The next step quotes the reason ("checker advisory: calibration …"), names the held commit, and says that a human reviews and re-runs with an explicit approval. A held commit that has landed is not listed. | The held commit exists and its branch still contains it. |
| `accepted` | A run's accepted commit has not landed: it is not reachable from the origin base branch. With `--issues`, a commit that is the head of an open pull request is still listed, with the next step to review and merge that pull request: merging is your work. Without `--issues` the next step says that no pull request was checked; a commit already on a remote branch is named, with no advice to push it again. | The commit exists and its branch still contains it. |
| `integration` | A work graph's verified integration candidate waits for your approval. | The candidate commit exists and its branch still contains it. |
| `spec` | A spec under `docs/specs/` is not accepted (for example `status: draft`). Only you accept a spec. | Read from `HEAD` and the working tree; an uncommitted one says so. |
| `manifest` | A run manifest under `.harness/runs/` has no run yet: it is uncommitted, its spec is not accepted, or it is ready for you to start. | Read from `HEAD` and the working tree. |
| `untriaged` | With `--issues`: an open GitHub issue, with a draft disposition and its local claim. | The issue is open on GitHub. |

A running run (live controller or role process) is not listed: it waits on nobody yet. Accepted
work that has landed is not listed either.

The run rows (`damaged`, `escalated`, `dead`, `interrupted`, `accepted`; one row per run at most)
are also what the [attention budget](21-autonomous-runs.md) counts before `prepare` writes a new
run and before `start` launches one, with or without `--issues`, and
what `agentsmith factory sweep` reports as waiting on you
([factory readiness](31-factory-readiness.md)). Both use the same derivation as this list.

**A row whose claim Git contradicts is dropped, with a warning.** For example: an escalated run
whose branch was deleted, or an accepted commit that its branch no longer contains. A state file
that cannot be read is not a contradiction but damage, and is listed as `damaged`. The warning names the item, so you can inspect or clean it up, but the
inbox never shows a row that Git does not support.

Each row has a `kind`, an `id`, an `age` (since the item last changed), a one-line next step,
and a `tier` where a commit range exists (from the [risk map](29-risk-map.md), computed from the
run's base commit to its commit).

An `accepted` or `awaiting-human` row whose spec declared a demo also links the controller's
demo transcript ([replayable demo evidence](21-autonomous-runs.md#replayable-demo-evidence)). Its
next step ends with the `autonomous-run.py evidence <run-id>` command and says whether you opened
that transcript yet, and `--json` adds an `evidence` object: `artefact`, `sha256`, `command` and
`opened`. A transcript that no longer matches its recorded hash is not linked; a warning names it.

The branch that counts as landed is resolved in this order: `--base <branch>` on `origin`; else the
branch `origin/HEAD` points to; else `origin/main`; else `origin/master`. When `--base` names a
branch that does not exist, or `origin/HEAD` points to a branch that is gone, the inbox says so in
a warning and never falls back silently. When nothing resolves, every accepted commit is listed,
with a warning.

The table prints control characters from titles, reasons and file names as `\xNN` escapes, so
no text can move the cursor or clear the terminal. `--json` keeps the exact text, JSON-escaped.

## GitHub issues and claims

`--issues` reads every open issue and open pull request through the [GitHub CLI](https://cli.github.com)
(read-only `gh api --paginate` requests, so no list stops at a fixed limit). It needs `gh` installed and logged in, and fails with exit status 2
and a clear message when it is not; without `--issues`, `gh` is never used. Triage is a draft
disposition printed in the row (for example "direct" for an issue labelled `bug`). Nothing is
written to GitHub: no labels, no comments, no assignment. To read one issue as untrusted input and
record your verdict on it, use [`agentsmith factory intake`](31-factory-readiness.md#intake).

A claim is local operator input, not part of the derived list: `inbox claim <issue>` records that
you, or a session you started, are taking the issue. One claim per issue; a second claim is refused
until `inbox release <issue>`. When `gh` is installed and logged in, `claim` first checks, read-only, that the
issue exists and is open, and refuses otherwise; without `gh` the claim is kept and marked
`unverified` in its row. Claims live under the Git common directory
(`agentsmith-inbox/claims/`), outside the tracked tree, so they never make the tree dirty and never
reach GitHub. A claim on an issue that is no longer open shows as a warning.

## Exit status

`0` when the list was derived (rows and warnings are information), `2` when the repository or
GitHub cannot be read, or a claim is refused.
