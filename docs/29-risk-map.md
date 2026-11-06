# Risk map

`agentsmith risk classify` reports how risky a change is. It reads the paths that changed between
two commits and returns a **tier** and the **lenses** (specialist reviews) that the change
triggers. The tier comes from a policy file that you commit. It does not come from the agent that
wrote the change.

```sh
agentsmith risk classify --base main --head my-branch
agentsmith risk classify --base 1a2b3c4 --head 5d6e7f8 --json
```

The command is read-only. It writes no file and contacts no service. Today the tier is a report:
it does not skip any review, and nothing merges automatically because of it.

## Tiers

Tiers are ordered from lowest to highest risk. The result of a change is the highest tier of any
path it touches.

| Tier | Meaning | Typical paths |
|---|---|---|
| `A` | Low risk inside an accepted direction | Documentation, tests, small tooling |
| `B` | Needs the operator's agreement for the area | Application code, user-facing text and locales |
| `C` | The operator reviews every change | Authentication, permissions, dependencies, billing logic |
| `human` | Outside what the policy can classify; the operator reviews it in person | Unmatched paths and the fixed floor below |

## The policy file

The policy is `.harness/risk-policy.json`. A starting point is
[`templates/risk-policy.json`](../templates/risk-policy.json): copy it to
`.harness/risk-policy.json`, adapt the paths to your project, and commit it.

```json
{
  "schema_version": 1,
  "rules": [
    {"paths": ["docs/**", "**/*.md"], "tier": "A"},
    {"paths": ["src/**"], "tier": "B"},
    {"paths": ["src/auth/**"], "tier": "C", "lenses": ["security"]}
  ]
}
```

- Each rule has `paths` (one or more globs), a `tier` (`A`, `B`, `C` or `human`) and optional
  `lenses` (lowercase ids such as `security`). Other keys are an error.
- Globs start at the repository root. `*` and `?` match inside one folder name; `**` matches any
  number of whole folders, including none, so `docs/**` also covers an entry named `docs`.
  `*.md` matches only Markdown files at the root; use `**/*.md` for any depth. Use `/` as the
  separator. Matching takes time proportional to the pattern and path lengths, so no pattern can
  stall a classification.
- Every rule that matches a path counts, and the highest tier wins. Rule order does not matter, so
  a broad rule cannot hide a stricter one. The lenses of all matching rules add up.
- Names match ignoring case, because macOS and Windows open `Src/Auth` for `src/auth`.
- A path that matches no rule is `human`.

**The policy is read at `--base`.** A change that edits the policy is still classified by the
policy it started from, so a candidate cannot relax the rules that judge it. Pass the commit the
work started from as `--base`. If the base commit has no policy, every path is `human`. If the
policy at the base is invalid, the command exits with status 2 and prints nothing on standard
output.

## The fixed floor

Some paths are `human` whatever the policy says. The floor is part of the program, not of the
policy, so no policy can remove it. Names match ignoring case.

| Floor | Paths |
|---|---|
| Agent instructions | `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`, `GEMINI.md` at any depth; anything inside a `.claude/`, `.codex/`, `.agents/` or `.cursor/` folder |
| Continuous integration | `.github/workflows/**`, `.github/actions/**`, any `CODEOWNERS` file |
| Harness | `.harness/**` (including the policy itself), `.agentsmith/**`, `agentsmith.py`, `scripts/autonomous-run.py`, `native_launcher.py`, `work_graph.py`, `windows_verifier_sandbox.py`, `risk_map.py`, `scripts/verify*` |
| Credentials | Names starting with `.env` or `id_`, names ending in `.pem` or `_key`, anything inside a `secrets/` folder |
| Migrations | Anything inside a `migrations/` folder |

The floor errs toward review. The credential names can match ordinary files, such as
`id_utils.py`; such a change is `human` and the operator reviews it.

## What counts as changed

Every added, modified, deleted or type-changed path counts. A renamed or copied file counts by its
old path **and** its new path, so moving a file out of a strict area keeps the strict tier, and
moving one into a floor path is `human`. A range with no changed paths is `human`, because nothing
was classified.

## A tier can be raised, never lowered

A reviewer may decide that a change is riskier than its paths suggest. A recorded tier can be
raised to a higher one, but never lowered; programs use `risk_map.raise_tier(recorded, proposed)`,
which returns the higher of the two.

## JSON report

`--json` prints one line of ASCII JSON with sorted keys and sorted paths. The same range gives
the same bytes on macOS, Linux and Windows.

```json
{"base": "<commit>", "head": "<commit>", "lenses": ["security"],
 "paths": [{"lenses": ["security"], "matched": ["rule:2", "rule:3"], "path": "src/auth/login.py", "tier": "C"}],
 "policy": {"blob": "<policy blob id at base, or null>", "path": ".harness/risk-policy.json"},
 "schema_version": 1, "tier": "C"}
```

`matched` names the reasons for each path: `rule:N` is the Nth rule in the policy (counting from
1), `floor:<category>` is a floor entry, and `unmatched` means no rule matched.
