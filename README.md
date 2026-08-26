# AgentSmith — portable operating rules for coding agents

AgentSmith turns maintained Markdown sources into a project operating agreement, portable skills,
and scoped runtime adapters. The canonical project instruction file is `AGENTS.md`. Claude Code
receives a generated `CLAUDE.md` copy; other clients either read `AGENTS.md` directly or receive a
minimal pointer configuration.

Compatibility has three independent layers: instruction discovery, skills/MCP tools, and native
runtime integration. Reading Markdown never implies hook, skill, or MCP parity. See the
[compatibility contract](docs/22-compatibility-contract.md) and machine-readable
[agent registry](config/agents.json).

## Targets

Claude Code and Codex are the two **native** integrations. The certification matrix also tracks
GitHub Copilot, Cursor, Gemini CLI, Windsurf/Devin, Cline, Roo Code, Aider, Continue, OpenHands,
Goose, OpenCode, JetBrains Junie, Zed, and Jules.

Those 14 clients are certification targets, not blanket claims. Each registry record says what is
supported, unsupported, or unverified. Tabby and LM Studio are model backends rather than agent
runtimes; local-model evidence belongs to a client-plus-provider scenario.

## Requirements

- Python 3.11 or newer
- no third-party Python packages
- `setup.sh` on macOS/Linux or `setup.ps1` on Windows

The launchers only locate Python and delegate identical arguments to `agentsmith.py`. Native
Windows setup, helpers, and managed hooks require neither Git Bash nor WSL.

## Quick start

```bash
git clone https://github.com/PromptPartner/agentsmith.git ~/tools/agentsmith
cd ~/tools/agentsmith

./setup.sh --agent codex --profile software-dev --target /path/to/project
./setup.sh --agent all --profile software-dev --with-skills --target /path/to/project
```

```powershell
pwsh ./setup.ps1 --agent all --profile software-dev --with-skills --target C:\path\to\project
```

`--agent` is repeatable and accepts comma-separated IDs or the groups `native`, `standard`,
`local`, and `all`. The old `--platform claude|codex|both` selector remains an alias during
migration. Mixing `--agent` and `--platform` is rejected.

```bash
./setup.sh --agent claude --agent codex --profile general-admin --target .
./setup.sh --agent gemini-cli,aider,continue,goose --profile document-creation --target .
./setup.sh --platform both --profile software-dev --target .
```

Every project run writes one managed `AGENTS.md`. Claude's `CLAUDE.md` is generated from the same
assembled bytes. AgentSmith creates no instruction symlinks, proprietary Markdown imports, or
second independently editable core.

## Inspect and maintain an install

```bash
python3 agentsmith.py agents list
python3 agentsmith.py compatibility
python3 agentsmith.py doctor --agent all --target /path/to/project

./setup.sh --agent all --profile auto --dry-run --target /path/to/project
./setup.sh --agent all --uninstall --target /path/to/project
```

When installed as a command, the public forms are `agentsmith agents list`, `agentsmith
compatibility`, and `agentsmith doctor ...`. Doctor reports instructions, skills, MCP, hooks, and
runtime separately. Fixture evidence is never presented as a live-client claim.

## Skills, MCP, and hooks

`--with-skills` installs the canonical pack under `.agents/skills`. Claude additionally gets the
`.claude/skills` adapter its runtime requires. Skills declare compatibility in frontmatter and do
not infer runtime identity from their installation path.

`--with-mcp playwright,context7` manages MCP only for clients with a supported native adapter.
Foreign JSON/TOML content is preserved; manually owned Codex MCP names win over a managed copy.

`--with-handoff-hooks`, `--with-ui-design-hook`, and `--with-hooks` install Python commands rather
than shell helpers. Hooks are enabled only for documented native surfaces.

Claude-only `--org-policy` manages the OS policy directory with backup/restore ownership. Use
`HARNESS_ORG_DIR` when building or testing a fleet image without writing the default system path.

## Cross-platform helpers

```bash
agentsmith verify --list
agentsmith verify
agentsmith handoff ITEM-123
agentsmith new-research "topic"
agentsmith new-feedback "observed failure"
agentsmith secret-scan
```

An installed project carries the Python runtime and command shims under `.agentsmith/`, so hooks
and skills resolve the same CLI on macOS, Linux, and Windows. Verification phases are
project-owned and run with the native OS shell.

## Profiles and operating model

The universal core lives in `core/`; work-type quality gates live in `profiles/` for software,
DevOps, marketing, documents, data, research, design, administration, security, and autonomous
loops. The working loop is understand → plan → implement → verify with evidence → finalize →
handoff.

The software-development assembly remains roughly 8k–9k estimated tokens. AgentSmith does not
silently substitute a weaker “local model” ruleset.

## Development verification

```bash
python3 scripts/test-agent-conformance.py --strict
python3 compatibility/test_registry.py
python3 -m py_compile agentsmith.py
```

Strict conformance covers all 16 registry entries, selector groups, Unicode paths, CRLF foreign
configuration, idempotent reruns, owned uninstall, canonical instruction selection, skill
metadata, and Bash-free hook commands. CI runs it natively on Ubuntu, macOS, and Windows.

## Documentation

- [Installation and migration](INSTALL.md)
- [Compatibility contract](docs/22-compatibility-contract.md)
- [Harness philosophy](docs/01-harness-philosophy.md)
- [Why verification means evidence](docs/03-verify-means-evidence.md)
- [Platforms and capabilities](docs/13-platforms-and-tools.md)
- [Safety model](docs/15-safety-model.md)
- [Troubleshooting](docs/17-troubleshooting.md)

## License and credit

MIT — see [LICENSE](LICENSE). Built and maintained by Lukas Hertig / PromptPartner. Public work
that influenced the harness is credited in [docs/18-influences.md](docs/18-influences.md).
