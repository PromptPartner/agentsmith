# AgentSmith — clear working rules for coding agents

AgentSmith gives coding agents a shared set of working rules. You choose the universal rules and a
profile for the kind of work you do. AgentSmith combines them into one `AGENTS.md` file in your
project. Claude Code receives the same rules in a generated `CLAUDE.md` file.

Support is reported separately for three things: whether an agent reads the rules, whether optional
skills and external tool connections work, and whether AgentSmith can configure the agent directly.
Support in one area does not imply support in the others. See the detailed
[compatibility contract](docs/22-compatibility-contract.md) and the machine-readable list of
[supported agents](config/agents.json).

## Targets

Claude Code and Codex are the two **native integrations**, which means AgentSmith can configure
their local applications directly. The compatibility table also tracks
GitHub Copilot, Cursor, Gemini CLI, Windsurf/Devin, Cline, Roo Code, Aider, Continue, OpenHands,
Goose, OpenCode, JetBrains Junie, Zed, and Jules.

Those 14 clients are certification targets, not blanket claims. Each registry record says what is
supported, unsupported, or not yet verified. Tabby and LM Studio provide models rather than coding
agent applications, so they need a separate test for each agent and model provider.

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

Every project run writes one managed `AGENTS.md`. Claude's `CLAUDE.md` contains the same generated
text. AgentSmith creates no file links, proprietary Markdown imports, or second copy of the
universal rules that users must edit separately.

With the universal rules installed, agents use plain international English by default. They explain
technical terms in common words and describe the effect and risk before commands. Use
`--operator-bio` to state what you already know and where you want more detail. An explicit request
to answer in another language always wins. See the copy-ready bios in [INSTALL.md](INSTALL.md#3-set-responsibility-background-and-external-write-consent).

## Permissions and trusted mode

Omitting `--safety` is the cautious path for fresh installs and ordinary updates. The wizard asks
`Safety [cautious/trusted] [cautious]:`; pressing Enter chooses cautious.

| Mode | Claude Code | Codex | Use when |
|---|---|---|---|
| `cautious` (default) | `permissions.defaultMode = acceptEdits` | `approval_policy = "on-request"`, `sandbox_mode = "workspace-write"` | Normal development, shared/client machines, or any environment still earning trust |
| `trusted` (explicit opt-in) | `permissions.defaultMode = bypassPermissions` | `approval_policy = "never"`, `sandbox_mode = "danger-full-access"` | A machine and repository you fully own, after you accept the wider range of possible changes |

Choose trusted only by passing `--safety trusted`. To move back, rerun with `--safety cautious` or
omit the flag. When an older AgentSmith-managed trusted configuration is encountered, `--dry-run`
shows the trusted-to-cautious migration; the real run warns and backs up the existing JSON/TOML
before changing only AgentSmith's safety keys. Unrelated Claude JSON and Codex TOML content stays
in place.

## Inspect and maintain an install

```bash
python3 agentsmith.py agents list
python3 agentsmith.py compatibility
python3 agentsmith.py doctor --agent all --target /path/to/project
python3 agentsmith.py evaluate --agent native --dry-run --claude-max-usd 10 --codex-max-tokens 100000

agentsmith update check --json
agentsmith update plan --target /path/to/project --save /tmp/agentsmith-update.json
agentsmith update apply --plan /tmp/agentsmith-update.json

./setup.sh --agent all --profile auto --dry-run --target /path/to/project
./setup.sh --agent all --uninstall --target /path/to/project
```

When installed as a command, the public forms are `agentsmith agents list`, `agentsmith
compatibility`, and `agentsmith doctor ...`. Doctor resolves the selected client's effective
global, project, and nested instruction chain, including fingerprints, generator metadata, and
combined/duplicate token estimates. It separately inspects actual safety, skills, MCP, hooks,
scanner commands, and installed runtime ownership. Duplicate full cores are warnings, not automatic
rewrites; use the reported `--profile-only` recommendation only when a self-contained project copy
is not required. Fixture evidence is never presented as a live-client claim.

Updates select stable semantic-version tags from the official repository by default. `check` and
`plan` do not change the installation. Planning stages the release in temporary directories and
records the exact managed create/replace paths, hashes, and file modes. It uses the current trusted
installer logic and treats candidate release files as data; candidate code does not run during
planning. `apply --plan` is the approval boundary: it rechecks every planned fingerprint, runs the
candidate installer in temporary directories, requires the exact staged set, writes
managed changes atomically, runs strict health checks, and prints the path to a local rollback receipt. Use
`agentsmith update rollback --receipt FILE` to restore the exact pre-update bytes. Pass `--global`
instead of `--target` for the separate global scope. An explicit `--from` may select a fork or local
test remote; a moving development branch is never selected implicitly. The first plan creates a
machine-local authentication key at `~/.agentsmith/update-integrity.key`. Plans and receipts are
bound to that key, so an edited or copied document cannot silently authorize different changes.
Staged updates retain an installation's `--assemble-only` choice, so they do not introduce native
permission settings or status-line helpers that the original install intentionally omitted.
Selected project MCP configuration is fingerprinted and updated with the same approval and rollback
boundary; MCP servers and settings that AgentSmith does not own remain intact.

`agentsmith update configure --auto-check weekly` opts into short, opportunistic checks at command
startup. They report availability only and never block the requested command when offline.
Automatic installation is not supported; use `--auto-check off` to disable the checks. The old
`install --self-update` flag remains temporarily for clean Git checkouts only. It fast-forwards the
current checkout and cannot provide release selection, installation fingerprints, or rollback.

`agentsmith evaluate` runs nine behavioral scenarios for installed Claude Code and Codex clients.
The default is a write-free dry run that resolves clients, commands, isolation, scenarios, and
budgets. Real execution requires `--live` plus a positive budget for each selected client; every
trial uses a fresh temporary Git repository with native tool networking disabled. Raw logs stay
under `~/.agentsmith/evaluations/raw/`; only reviewed, normalized schema-v2 records belong in
`compatibility/evaluations/`.

Codex trials additionally use a temporary `CODEX_HOME` with a single-file bridge to validated
ChatGPT subscription authentication. User instructions, settings, hooks, plugins, apps, and MCP
servers do not enter the trial, OAuth refreshes remain consistent with the source login, and
API-key-authenticated Codex sessions fail closed.

## Skills, MCP, and hooks

`--with-skills` installs the canonical pack under `.agents/skills`. Claude additionally gets the
`.claude/skills` adapter its runtime requires. Skills declare compatibility in frontmatter and do
not infer runtime identity from their installation path.

`--with-mcp playwright,context7` manages project MCP only for clients with a supported native adapter.
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
agentsmith secret-scan --all
agentsmith secret-scan FILE...
printf '%s\n' "text to inspect" | agentsmith secret-scan -
```

An installed project carries the Python runtime and command shims under `.agentsmith/`, so hooks
and skills resolve the same CLI on macOS, Linux, and Windows. Verification phases are
project-owned and run with the native OS shell.

The default secret scan examines only added lines in the staged Git diff, which is the pre-commit
contract. `--all` scans the tracked working tree; file arguments and `-` select explicit files or
stdin. The scanner reports path, line, and pattern name with the matched value redacted. Put one
Python regular expression per line in `.harness/secret-scan.allow` only for inert fixtures that
cannot be reshaped; never use it to waive a live credential.

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
