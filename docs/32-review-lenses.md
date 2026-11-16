# Review lenses

A review lens is a specialist review that runs only when a change touches its area: security,
data, installer, user interface. Lenses are **report-only**. They cannot block, approve or change
anything; they write findings, and the operator decides. A lens is not a client-specific agent:
its brief works in an attended Claude Code or Codex session alike.

```sh
agentsmith lens plan  --base main --head my-branch            # which lenses, how deep
agentsmith lens brief security --base main --head my-branch   # the prompt for one lens
agentsmith lens record --base main --head my-branch --source lens:security \
  --evidence "login accepts any password :: src/auth/login.py:2 :: return True" \
  --decision act --rationale "authentication is bypassed" --checker missed
agentsmith lens report                                        # noise and missed defects
```

## The lens file

Lenses live in `.harness/lenses.json`. Like the [risk policy](29-risk-map.md), the file is read
**at `--base`**, so a change cannot remove the lenses that review it. Start from
[`templates/lenses.json`](../templates/lenses.json) (security, data, installer, ui), adapt it,
and commit it.

| Key | Meaning |
|---|---|
| `id` | Lowercase id, for example `security`. |
| `paths` | Globs, with the risk map's rules: root-anchored, `*` inside one folder, `**` across folders. |
| `must_read` | Up to five documents the reviewer reads first, for example `DESIGN.md`. Relative paths only (no drive letter, no `..`). The brief points at them as committed at `--base` (`git show <base>:<path>`), so a candidate cannot swap them; a document that is a symbolic link at the base commit is refused, and a missing one is named. |
| `brief` | One line: what this lens looks for. |
| `evidence` | One line: what a finding must cite. |
| `min_tier` | The lowest tier (`A`, `B`, `C`, `human`) at which the lens runs. |

A lens triggers when a changed path matches its `paths` (a renamed or copied file counts by its
old and new path), or when a risk-policy rule that matched the change names the lens id in its
`lenses`. It runs only when the change's tier is at least its `min_tier`. A lens names no model:
which model checks is decided when the review runs, not in the lens file.

## Review depth

The depth comes from the change's tier and the class of the checker model (`--checker-class`,
default `standard`):

| Tier | `small` | `standard` | `frontier` |
|---|---|---|---|
| `A` | normal | light | light |
| `B` | normal | normal | normal |
| `C` | normal (warning) | deep | deep |
| `human` | normal (warning) | deep | deep |

- **light**: read the diff for the triggered paths and the must-read documents; report only clear
  defects.
- **normal**: read the whole diff and every must-read document; check each requirement they state;
  report defects and missing tests.
- **deep**: as normal, then trace each changed path to its callers and tests, and try to reproduce
  each suspected defect with a command or a failing test.

A small checker model always gets a normal review: a light pass relies on judgment about what to
skip, and a deep pass on long tracing. For tiers that want a deep review, the plan and the brief
warn that a stronger checker is needed.

## Candidate data in the brief

Whoever wrote the candidate chose its file names, so they can carry text meant to steer the
reviewer. The brief shows the changed paths that triggered the lens only inside a block marked as
data from the candidate, opened and closed by a marker with a random token, one escaped line each
(control characters and newlines appear as `\xNN`, and every line starts with `  | `). The brief
tells the reviewer to treat that block, the diff and every changed file as data, not instructions.

## Evidence

Every finding cites the candidate (the head commit) in the form
`criterion :: file[:line] :: excerpt`, the same form that an accepting checker uses for a run's
evidence. The file is a repository path at the head commit, the line counts from 1, and the
excerpt is copied exactly from that line (or from the file when no line is given). `lens record`
checks the citation against the head commit and refuses a row whose citation does not hold.

## The trial record

`lens record` appends one row per finding to `agentsmith-lenses/manifest.jsonl` under the Git
common directory, outside the tracked tree. A symbolic link at that folder or file is refused, so
the record cannot be redirected into the tracked tree. Write the rows before fixing anything. Each row has:

- `source` (`lens:<id>`, `checker`, `human` or `bot:<name>`), `location` and `evidence`;
- `decision`: `act`, `skip` (with a reason), or `skip-silently` (style only; the code is correct);
- a one-line `rationale`, and the `fix` or check, if any;
- for a lens finding, `checker`: whether the single checker also reported it (`found` or `missed`);
- `confidence`, from these rules: it starts by source (`medium` for a lens, the checker or a person;
  `low` for a bot); a `--reproduction` command makes it `high`; independent agreement (another
  source, not a bot, at the same place in the same candidate) raises it one step; a bot's
  assertion never raises anything.

Each row has an `id`, a hash of the candidate, source, location and evidence. `lens record`
refuses a finding that is already recorded, so a retry cannot inflate the counts; a copy that
reaches the file anyway, for example by an edit by hand, is skipped by `lens report` with a warning.

Disagreement between sources is allowed; an unexplained omission is not.

`lens report` reads only valid rows: a line that is not JSON text or lacks a field a row needs is
skipped, counted as `invalid_rows` and named in a warning, never counted as a finding. It
recomputes confidence over the valid rows and counts, for lens findings only:

- **noise rate**: lens findings not acted on (`skip` or `skip-silently`), divided by all lens
  findings;
- **missed by the single checker**: lens findings acted on that the single checker did not report.

The trial is met with at least 20 candidates, a noise rate under 20%, and at least one acted-on
defect that the single checker missed. Until those numbers exist, lenses stay report-only.
