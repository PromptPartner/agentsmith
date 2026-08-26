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

Use `--safety cautious` for approval-on-request/workspace-write mappings. The flag path retains
`trusted` as its migration default; use that only in an environment you own.

## 5. Preview, inspect, and uninstall

```bash
./setup.sh --agent all --profile software-dev --dry-run --target .
python3 agentsmith.py doctor --agent all --target .
python3 agentsmith.py compatibility --json
./setup.sh --agent all --uninstall --target .
```

Dry-run performs no writes. Uninstall removes managed instructions and configured-adapter content
while preserving foreign content and project scaffolding. Backups remain beside changed files.

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
```

Project verification phases live in `.harness/verify.conf` and run with the native OS shell.
Replace the failing `unwired` placeholder with real build, lint, test, render, or evaluation
commands before calling the project verified.

## 7. Evidence and migration

`agentsmith compatibility` reports instructions, skills, MCP, hooks, evidence, and static-context
size separately. Fixture evidence proves deterministic generation and ownership only. Real-client
claims require dated observed/manual evidence with client version and OS. Local-model runs also
record model digest, context window, hardware class, latency, and all failures.

Migration notes:

- `--platform` remains an alias; migrate automation to `--agent` when convenient.
- A Claude-only project now also gets canonical `AGENTS.md`; `CLAUDE.md` is generated from it.
- Shared skills live in `.agents/skills`; Claude's directory is an adapter.
- Old shell helpers may remain in upgraded projects, but new hooks and skills use the Python CLI.
- `--with-rtk` no longer adds proprietary instruction imports.

See [the compatibility contract](docs/22-compatibility-contract.md) and
[the current registry](config/agents.json).
