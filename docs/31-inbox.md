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
| `escalated` | An autonomous run stopped at a boundary it may not cross. The next step quotes its reason. | Its branch and base commit exist. |
| `dead` | A run is unfinished (`prepared`, `making`, `checking`, `retrying`, `resuming`) but neither its controller nor its role process is alive. | Its branch and base commit exist. |
| `interrupted` | A run was stopped and can be resumed or discarded. | Its branch and base commit exist. |
| `accepted` | A run's accepted commit has not landed: it is not reachable from the origin base branch, and (with `--issues`) no open pull request has it as its head. | The commit exists and its branch still contains it. |
| `integration` | A work graph's verified integration candidate waits for your approval. | The candidate commit exists and its branch still contains it. |
| `spec` | A spec under `docs/specs/` is not accepted (for example `status: draft`). Only you accept a spec. | Read from `HEAD` and the working tree; an uncommitted one says so. |
| `manifest` | A run manifest under `.harness/runs/` has no run yet: it is uncommitted, its spec is not accepted, or it is ready for you to start. | Read from `HEAD` and the working tree. |
| `untriaged` | With `--issues`: an open GitHub issue, with a draft disposition and its local claim. | The issue is open on GitHub. |

A running run (live controller or role process) is not listed: it waits on nobody yet. Accepted
work that has landed is not listed either.

**A row whose claim Git contradicts is dropped, with a warning.** For example: an escalated run
whose branch was deleted, an accepted commit that its branch no longer contains, or a state file
that cannot be read. The warning names the item, so you can inspect or clean it up, but the
inbox never shows a row that Git does not support.

Each row has a `kind`, an `id`, an `age` (since the item last changed), a one-line next step,
and a `tier` where a commit range exists (from the [risk map](29-risk-map.md), computed from the
run's base commit to its commit).

The branch that counts as landed is resolved in this order: `--base <branch>` on `origin`; else the
branch `origin/HEAD` points to; else `origin/main`; else `origin/master`. When `--base` names a
branch that does not exist, or `origin/HEAD` points to a branch that is gone, the inbox says so in
a warning and never falls back silently. When nothing resolves, every accepted commit is listed,
with a warning.

## GitHub issues and claims

`--issues` reads open issues and open pull requests through the [GitHub CLI](https://cli.github.com)
(`gh issue list`, `gh pr list`). It needs `gh` installed and logged in, and fails with exit status 2
and a clear message when it is not; without `--issues`, `gh` is never used. Triage is a draft
disposition printed in the row (for example "direct" for an issue labelled `bug`). Nothing is
written to GitHub: no labels, no comments, no assignment.

A claim is local operator input, not part of the derived list: `inbox claim <issue>` records that
you, or a session you started, are taking the issue. One claim per issue; a second claim is refused
until `inbox release <issue>`. Claims live under the Git common directory
(`agentsmith-inbox/claims/`), outside the tracked tree, so they never make the tree dirty and never
reach GitHub. A claim on an issue that is no longer open shows as a warning.

## Exit status

`0` when the list was derived (rows and warnings are information), `2` when the repository or
GitHub cannot be read, or a claim is refused.
