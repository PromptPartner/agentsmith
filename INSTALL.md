# Installing AgentSmith

AgentSmith uses one Python 3.11+ program on macOS, Linux, and Windows. The shell and PowerShell
setup files find Python and pass the same options to `agentsmith.py`.

## 1. Select agents and a profile

```bash
./setup.sh --agent codex --profile software-dev --target /path/to/project
./setup.sh --agent all --profile general-admin --target /path/to/project
```

```powershell
pwsh ./setup.ps1 --agent all --profile software-dev --target C:\path\to\project
```

`--agent` selects the coding agent that will read the rules. You can repeat it, use comma-separated
IDs, or select a group: `native`, `standard`, `local`, or `all`. Run
`python3 agentsmith.py agents list` to see what each agent supports. The older
selector `--platform claude|codex|both` is accepted but cannot be mixed with `--agent`.

Profiles add checks and working rules for a type of work, such as software development or research.
You can repeat `--profile` or use a comma-separated list. `--profile auto` inspects the project.
`--profile-only` leaves out the universal rules when those rules already come from a global install.

## 2. Generated files and settings

Project `AGENTS.md` is the main generated instruction file for every selection.

| Coding agent | File or setting AgentSmith manages |
|---|---|
| Claude Code | generated `CLAUDE.md` copy |
| Codex and direct consumers | `AGENTS.md` |
| Gemini CLI | `.gemini/settings.json` selects `AGENTS.md` |
| Aider | `.aider.conf.yml` reads `AGENTS.md` |
| Continue | `.continue/rules/agentsmith.md` points to `AGENTS.md` |
| Goose | `.goosehints` points to `AGENTS.md` |

AgentSmith updates only marked sections or settings that it owns. It backs up a changed file first,
checks configuration file syntax, and leaves unrelated content in place. It uses no file links,
`@RTK.md` imports, or second editable copy of the universal rules.

## 3. Set responsibility, background, and external-write consent

```bash
./setup.sh --agent all --profile software-dev \
  --operator-name "Your Name" --operator-role "Founder / Engineer" \
  --operator-bio "I can build and ship small applications. I am comfortable with daily Git and tests. Explain unfamiliar architecture and history-changing Git operations before commands." \
  --tracker linear --tracker-writes ask --target .
```

`--operator-role` states what you are responsible for. `--operator-bio` states what you already
know and where you need more explanation. AgentSmith does not use a separate explanation-level
setting because experience varies by topic. Copy one of these and adjust it:

- Newer developer: `I am new to software development. Explain each technical term in plain words. Before commands, tell me why we are doing this, what will change, the main risks, and how to undo it. Do not assume I know Git, terminals, or deployment.`
- Intermediate developer: `I can build and ship small applications. I am comfortable with daily Git, tests, and command-line tools. Explain unfamiliar architecture, infrastructure, and history-changing Git operations before commands. Skip basic syntax.`
- Expert developer: `I am an experienced software engineer. Be concise on routine code and tools. Go deep on non-obvious trade-offs, failure modes, security boundaries, and changes that are hard to reverse. State assumptions and show evidence.`

The universal rules make plain international English the default. If you explicitly ask for another
language, the agent uses it. If you use another language without asking for it as the answer
language, the agent gives one brief note that English usually uses fewer tokens, then continues in
English.

Naming a tracker does not authorize writes. `ask` is the default; `allowed` is explicit opt-in.
Reruns recover omitted name, role, bio, and tracker values from existing managed instructions.

## 4. Optional capabilities

```bash
./setup.sh --agent native --profile software-dev \
  --with-skills --with-mcp playwright,context7 \
  --with-handoff-hooks --with-ui-design-hook --with-hooks --target .
```

- Skills are canonical under `.agents/skills`; Claude gets `.claude/skills` as an adapter.
- MCP is project-scoped and managed only for supported native integrations.
- Runtime and git hooks invoke Python directly and require no Bash or WSL.
- Unsupported client capabilities remain unsupported; AgentSmith does not emulate them.

Omitting `--safety` selects cautious: Claude uses `acceptEdits`; Codex uses approval-on-request in
the workspace-write sandbox. `--safety trusted` is an explicit opt-in for a machine and repository
you fully own. The wizard uses `Safety [cautious/trusted] [cautious]:` and rejects any other answer.

This default changed in `0.2.0`. An ordinary update of an older AgentSmith-managed trusted config
migrates it to cautious rather than silently grandfathering bypass access. Preview with `--dry-run`;
the real run prints a migration warning and backs up the existing Claude JSON or Codex TOML before
updating its managed safety setting. Pass `--safety trusted` on the update only when retaining that
wider range of possible changes is an explicit decision.

When Claude has no `statusLine` key, install adds an AgentSmith-owned model/directory/context gauge
and a dependency-free helper under `~/.claude/`. Any explicit Claude status-line value is preserved.
Codex needs no added setting: its built-in model/directory status line is already active when
`tui.status_line` is absent, and an explicit Codex list (including `[]`) remains authoritative.

## 5. Preview, update, inspect, and uninstall

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

Use the staged updater for an installed project:

```bash
agentsmith update check
agentsmith update plan --target /path/to/project --save /tmp/agentsmith-update.json
# Read the plan. Applying it is the explicit installation approval boundary.
agentsmith update apply --plan /tmp/agentsmith-update.json
agentsmith update rollback --receipt /path/printed/by/apply.json
```

For a global installation, replace `--target /path/to/project` with `--global`. Stable release tags
from the official repository are the default. `--version v1.2.3` selects an exact stable tag, and
`--from REMOTE` selects an explicit fork or local test remote. Planning checks that the tag,
declared version, and Git commit agree. It records current fingerprints, preserved-content rules,
migration warnings, and verification steps without changing the installation. It also stages the
release in temporary directories and records the exact create/replace paths, hashes, and file modes.
Planning uses the current trusted installer logic and treats candidate release files as data. The
candidate release code does not run before `apply`.

The first plan creates a local authentication key at `~/.agentsmith/update-integrity.key`; this does
not change the installation. Plans and receipts are bound to that key and to the local account.
`apply` refuses an edited plan, a moved tag, any file that changed after planning, or a staged result
that differs from the authenticated proposal. It repeats the release installer against temporary copies,
then backs up and atomically replaces only managed
files. A failed apply or health check restores the pre-update bytes automatically. A successful
apply writes its rollback receipt and backups under `~/.agentsmith`, outside tracked project files.
Rollback also refuses when an updated file changed after apply, so it cannot overwrite later work.

Weekly checks are opt-in and report-only:

```bash
agentsmith update configure --auto-check weekly
agentsmith update configure --auto-check off
```

The check uses a short timeout and never blocks the requested command when offline. AgentSmith has
no automatic apply mode. The deprecated `install --self-update` option is only for a clean harness
Git checkout: it fast-forwards the current branch and lacks stable-release selection, staged plans,
installation receipts, and rollback.

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
agentsmith verify --record .harness/receipts/my-check
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
commands before calling the project verified. `verify --record <directory>` resolves a relative
directory from the project target, refuses to overwrite it, and stores an atomic command receipt
plus redacted per-phase output. Receipts remain local unless you deliberately move them.

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
- New installs record update choices and owned skill fingerprints in the existing
  `.agentsmith/state.json`. Planning can reconstruct a pre-manifest install only when managed
  markers and ownership state prove every required choice; otherwise it stops and asks for an
  explicit reinstall rather than guessing safety or ownership.

See [the compatibility contract](docs/22-compatibility-contract.md) and
[the current registry](config/agents.json).
