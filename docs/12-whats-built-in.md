# What's built in

The core and profiles supply judgment; this page inventories executable machinery. Every optional
surface should solve a concrete problem because each one adds maintenance and failure modes.

## Shared runtime

`agentsmith.py` is the Python 3.11+ standard-library core for installation, managed-block
reconciliation, doctor output, compatibility reporting, behavioral evaluation, helpers, secret
checks, and hook handling.
`setup.sh` and `setup.ps1` only discover Python and delegate arguments.

Project installs carry `.agentsmith/agentsmith.py` plus POSIX and Windows command shims. This keeps
helpers and managed hooks native on macOS, Linux, and Windows without Git Bash or WSL.

## Rules and adapters

- `AGENTS.md` is the canonical project instruction artifact.
- Claude gets a generated `CLAUDE.md` copy.
- Gemini CLI, Aider, Continue, and Goose get managed pointers to `AGENTS.md`.
- Ten other certification targets use the direct `AGENTS.md` adapter.
- Foreign configuration is backed up and preserved; uninstall removes only owned content.
- Claude receives a default model/directory/context status line only when no explicit choice exists;
  Codex's native default remains active without redundant managed TOML.

## Optional capability flags

- `--with-skills` installs the canonical pack into `.agents/skills`; Claude also receives its
  required `.claude/skills` adapter.
- `--with-mcp <name[,name]>` manages supported Claude/Codex MCP surfaces while preserving foreign
  servers and manually owned name conflicts.
- `--with-handoff-hooks` installs the written handoff reminder on supported native hook surfaces.
- `--with-ui-design-hook` adds a scoped reminder to consult `DESIGN.md` for UI edits.
- `--with-hooks` installs the Python secret gate as a git pre-commit hook when no foreign hook would
  be overwritten.
- Omitted `--safety` maps native clients to cautious approval/workspace settings;
  `--safety trusted` is an explicit opt-in. Managed trusted updates warn and back up before the
  cautious migration.

Capabilities without a documented stable client interface stay disabled. AgentSmith does not
emulate hooks or MCP to make matrix cells green.

## Portable helper commands

| Command | Purpose |
|---|---|
| `agentsmith verify [--record <directory>]` | Run `.harness/verify.conf` phases with the native OS shell; optionally retain a local redacted command receipt. |
| `agentsmith handoff` | Scaffold durable session memory with branch/HEAD/dirty facts. |
| `agentsmith new-research` | Create a durable research note that is archived, never silently deleted. |
| `agentsmith new-feedback` | Create the five-stage post-incident record. |
| `agentsmith secret-scan [--all|FILE...|-]` | Scan staged additions by default, or the tracked tree/files/stdin, with redacted findings. |
| `agentsmith doctor` | Inspect effective instruction sources and actual installed safety, skills, MCP, hooks, scanner, and runtime state. |
| `agentsmith compatibility` | Render the registry and static-context measurement without overstating evidence. |
| `agentsmith evaluate --agent claude\|codex\|native` | Dry-run or execute the nine isolated, budgeted native-client behavior scenarios. |

## Skills

The bundled skills are dynamic context: handoff, verify, harness-doctor, harness-help,
new-research, new-feedback, writing-rules, wayfinder, autonomous-run, and the example skill.
Every `SKILL.md` declares compatibility metadata. Runtime-specific behavior uses explicit context,
not the directory in which a skill happened to be installed.

The autonomous-run controller remains constrained to macOS/Linux because its isolation layer uses
`sandbox-exec` or Bubblewrap. That limitation is declared rather than hidden behind a generic
Windows compatibility claim.

## Verification and CI

The repository's strict conformance suite validates the 16-agent contract, registry schema,
selector groups, Python-only launchers and hooks, canonical instructions, Unicode paths, CRLF
foreign config, idempotence, and uninstall ownership:

```bash
python3 scripts/test-agent-conformance.py --strict
python3 compatibility/test_registry.py
python3 scripts/test-evaluate.py
python3 scripts/test-statusline.py
```

CI runs those checks and the fake-client evaluation harness natively on Ubuntu, macOS, and Windows.
The fixture harness proves runner behavior, not Claude or Codex behavior. Existing POSIX-only
guardrail tests remain a separate Ubuntu job; they do not stand in for Windows runtime evidence.
