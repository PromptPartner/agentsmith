# Installing AgentSmith

AgentSmith uses one Python 3.11+ standard-library runtime on macOS, Linux, and Windows. The shell
and PowerShell entrypoints are launcher-only; every platform executes `agentsmith.py` with the
same arguments.

## 1. Select agents and a profile

```bash
./setup.sh --agent codex --profile software-dev --target /path/to/project
./setup.sh --agent all --profile general-admin --target /path/to/project
```

```powershell
pwsh ./setup.ps1 --agent all --profile software-dev --target C:\path\to\project
```

`--agent` can be repeated, accepts comma-separated IDs, and expands `native`, `standard`, `local`,
or `all`. Use `python3 agentsmith.py agents list` for IDs and capability boundaries. The legacy
selector `--platform claude|codex|both` is accepted but cannot be mixed with `--agent`.

Profiles are comma-separated or repeatable. `--profile auto` inspects the project. `--profile-only`
omits the universal core for a layered native install.

## 2. Generated surfaces

Project `AGENTS.md` is canonical for every selection.

| Adapter | Managed project surface |
|---|---|
| Claude Code | generated `CLAUDE.md` copy |
| Codex and direct consumers | `AGENTS.md` |
| Gemini CLI | `.gemini/settings.json` selects `AGENTS.md` |
| Aider | `.aider.conf.yml` reads `AGENTS.md` |
| Continue | `.continue/rules/agentsmith.md` points to `AGENTS.md` |
| Goose | `.goosehints` points to `AGENTS.md` |

AgentSmith reconciles owned blocks or keys, backs up changed foreign files, validates JSON/TOML,
and leaves unrelated content in place. It uses no symlinks, `@RTK.md`, or independently editable
copies of the core.

## 3. Identity and external-write consent

```bash
./setup.sh --agent all --profile software-dev \
  --operator-name "Your Name" --operator-role "Founder / Engineer" \
  --tracker linear --tracker-writes ask --target .
```

Naming a tracker does not authorize writes. `ask` is the default; `allowed` is explicit opt-in.
Reruns recover omitted identity and tracker values from existing managed instructions.

## 4. Optional capabilities

```bash
./setup.sh --agent native --profile software-dev \
  --with-skills --with-mcp playwright,context7 \
  --with-handoff-hooks --with-ui-design-hook --with-hooks --target .
```

- Skills are canonical under `.agents/skills`; Claude gets `.claude/skills` as an adapter.
- MCP is managed only for supported native integrations.
- Runtime and git hooks invoke Python directly and require no Bash or WSL.
- Unsupported client capabilities remain unsupported; AgentSmith does not emulate them.

Omitting `--safety` selects cautious: Claude uses `acceptEdits`; Codex uses approval-on-request in
the workspace-write sandbox. `--safety trusted` is an explicit opt-in for a machine and repository
you fully own. The wizard uses `Safety [cautious/trusted] [cautious]:` and rejects any other answer.

This default changed in `0.2.0`. An ordinary update of an older AgentSmith-managed trusted config
migrates it to cautious rather than silently grandfathering bypass access. Preview with `--dry-run`;
the real run prints a migration warning and backs up the existing Claude JSON or Codex TOML before
updating its managed safety setting. Pass `--safety trusted` on the update only when retaining that
blast radius is an explicit decision.

When Claude has no `statusLine` key, install adds an AgentSmith-owned model/directory/context gauge
and a dependency-free helper under `~/.claude/`. Any explicit Claude status-line value is preserved.
Codex needs no added setting: its built-in model/directory status line is already active when
`tui.status_line` is absent, and an explicit Codex list (including `[]`) remains authoritative.

## 5. Preview, inspect, and uninstall

```bash
./setup.sh --agent all --profile software-dev --dry-run --target .
python3 agentsmith.py doctor --agent all --target .
python3 agentsmith.py compatibility --json
./setup.sh --agent all --uninstall --target .
```

Dry-run performs no writes. Uninstall removes managed instructions, the unchanged default Claude
status line, and configured-adapter content while preserving foreign content, customized helpers,
and project scaffolding. Backups remain beside changed files.
Doctor is read-only: it reports effective global/project/nested sources, managed metadata and
fingerprints, combined and duplicate context, actual native safety, and current/stale owned
capabilities. A duplicate-core warning recommends `--profile-only` but never rewrites a project;
self-contained project instructions may be intentional for collaborators.

Global native destinations are fixed, so `--global --target ...` is rejected:

```bash
./setup.sh --agent native --global --operator-name "Your Name"
./setup.sh --agent native --profile software-dev --profile-only --target /path/to/project
```

For a shared machine, Claude-only organization policy uses the OS-managed policy directory and
restores prior managed values on uninstall. Preview it first; the real default path needs elevated
filesystem permission:

```bash
sudo ./setup.sh --agent claude --org-policy --profile security-audit
```

Set `HARNESS_ORG_DIR` to an explicit directory for fleet packaging or a non-privileged test.

## 6. Portable helpers

```bash
agentsmith verify --list
agentsmith verify
agentsmith handoff ITEM-123
agentsmith new-research "topic"
agentsmith new-feedback "symptom"
agentsmith secret-scan
agentsmith secret-scan --all
agentsmith secret-scan FILE...
agentsmith secret-scan -
agentsmith evaluate --agent native --trials 3 --dry-run --claude-max-usd 10 --codex-max-tokens 100000
```

`secret-scan` defaults to staged added lines. The other modes scan the tracked working tree,
explicit files, or stdin; all use the same Python implementation as the managed pre-commit hook.
Findings expose only path, line, and the matched pattern name—the value is redacted.

`evaluate` defaults to a no-model dry run. A real run additionally requires `--live` and positive
budgets for every selected client. It creates a fresh temporary Git repository per trial, disables
network access in the native client sandbox, keeps raw logs outside the repository, and emits
normalized schema-v2 records. Review every failure and secret-scan the records before copying them into
`compatibility/evaluations/`.

Project verification phases live in `.harness/verify.conf` and run with the native OS shell.
Replace the failing `unwired` placeholder with real build, lint, test, render, or evaluation
commands before calling the project verified.

## 7. Evidence and migration

`agentsmith compatibility` reports instructions, skills, MCP, hooks, evidence, and static-context
size separately. Fixture evidence proves deterministic generation and ownership only. Real-client
claims require dated observed/manual evidence with client version and OS. Local-model runs also
record model digest, context window, hardware class, latency, and all failures.

Migration notes:

- Omitted `--safety` now means cautious. Trusted remains available only through the explicit flag.
- `--platform` remains an alias; migrate automation to `--agent` when convenient.
- A Claude-only project now also gets canonical `AGENTS.md`; `CLAUDE.md` is generated from it.
- Shared skills live in `.agents/skills`; Claude's directory is an adapter.
- Old shell helpers may remain in upgraded projects, but new hooks and skills use the Python CLI.
- `--with-rtk` no longer adds proprietary instruction imports.

See [the compatibility contract](docs/22-compatibility-contract.md) and
[the current registry](config/agents.json).
