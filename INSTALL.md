# Installing AgentSmith

There are two supported entry points. Both end in the same reviewed installation plan.

## Option 1: manual guided setup

Download the signed installer for your operating system from the [latest release](https://github.com/PromptPartner/agentsmith/releases/latest):

- macOS: Apple silicon (`arm64`) or Intel (`x86_64`)
- Windows: 64-bit (`x86_64`)
- Linux: 64-bit (`x86_64`)

Install it, open a terminal, and run:

```console
agentsmith
```

The wizard asks for:

1. your language;
2. an existing project or a new empty folder;
3. the AI agent that should read the rules;
4. a work profile, recommended from static project evidence;
5. your relevant experience, so explanations match what you know;
6. cautious or trusted permissions;
7. optional advanced settings;
8. confirmation of the exact plan.

No project file changes before the final confirmation. For a new project, AgentSmith creates the folder and initializes Git only after confirmation. It does not generate an application framework.

Use `agentsmith install --wizard --lang de` to start directly in German. Supported wizard languages are English (`en`), German (`de`), Spanish (`es`), French (`fr`), and Simplified Chinese (`zh-CN`).

## Option 2: agent-guided setup

Give your coding agent this prompt:

```text
Install AgentSmith for this project. Follow the official agent guide at
https://github.com/PromptPartner/agentsmith/blob/master/AGENT-INSTALL.md
Inspect the project first, explain your profile recommendation in plain language,
show me the exact installation plan, and ask once before applying it.
```

The agent follows the same decisions as the manual wizard. It verifies the official release checksum, inspects without executing project code, previews managed destinations, waits for one approval, applies the setup, and runs `agentsmith doctor`.

## Existing and new projects

**Existing project:** AgentSmith reads filenames and configuration to recommend a profile. Inspection is static. It does not install project dependencies or execute scripts. Existing content outside AgentSmith-managed blocks is preserved.

**New project:** choose an absent or empty folder. AgentSmith creates it, runs `git init`, and adds its rules and verification scaffolding. Choose the application stack afterward with your agent.

If AgentSmith already manages the target, use `agentsmith status --target .` before changing it. A later wizard run recovers existing identity and consent settings instead of silently replacing them.

## Where the rules live

| Setup | Best for | Result |
|---|---|---|
| Project, default | Teams, shared repositories, and most users | The core agreement and profile are committed with the project. Collaborators can review the same rules. |
| User-wide, advanced | One person who wants the same core in every local project | The universal core is installed in the native user instruction locations. It does not travel with a repository. |
| Layered, advanced | Many projects with different work types | A user-wide core combines with a profile-only project layer. Every collaborator still needs an equivalent user-wide core. |

The project default is more portable and easier to review. In the wizard, user-wide rules are inside **Advanced options**. For an explicit layered setup:

```console
agentsmith install --agent native --global
agentsmith install --agent native --profile software-dev --profile-only --target /path/to/project
```

Claude loads its user and project `CLAUDE.md` files. Codex loads its user and project `AGENTS.md` files. `agentsmith doctor --target /path/to/project` reports the effective chain and warns about missing or duplicated layers.

## Profiles

Run these read-only commands at any time:

```console
agentsmith profiles list
agentsmith profiles recommend --target /path/to/project
```

One primary profile is the norm. `autonomous-loops` is a modifier for unattended work. The [profile guide](docs/07-how-to-pick-a-profile.md) describes every profile, examples, close calls, stacking, and safe switching.

For an existing installation, preview a profile change before applying it:

```console
agentsmith profiles switch --target /path/to/project --profile software-dev --dry-run
agentsmith profiles switch --target /path/to/project --profile software-dev
```

## What AgentSmith manages

`AGENTS.md` is the canonical project instruction file. Claude also receives a generated `CLAUDE.md`. Selected clients receive small adapters that point to `AGENTS.md`; AgentSmith does not maintain independent copies.

New project setups also receive:

- `.harness/verify.conf` for project checks;
- `.agentsmith/state.json` for owned settings and fingerprints;
- handoff, research, and feedback scaffolding;
- optional skills, MCP configuration, and hooks when selected.

Updates touch managed blocks and recorded files only. Existing files are backed up before replacement. Uninstall preserves project scaffolding, customized helpers, foreign configuration, and backups.

## Safety and experience

`cautious` is the default. Claude uses edit approval and Codex uses approval on request in its workspace sandbox. `trusted` is an explicit opt-in for a repository and machine you fully control.

The wizard asks about experience in the relevant domain instead of assigning one universal skill level. Choose the closest starting point and adjust the generated operator text later if needed. This affects explanations and confirmation detail; it does not weaken safety or verification rules.

Naming a tracker never authorizes writes. External system writes still require explicit consent unless the installation records that consent.

## Advanced command reference

The guided setup is the normal route. Direct flags remain for automation and existing users:

```console
agentsmith install --agent codex --profile software-dev --target /path/to/project
agentsmith install --agent native --profile software-dev --dry-run --target .
agentsmith install --agent native --profile software-dev --with-skills --with-hooks --target .
agentsmith doctor --agent native --target .
agentsmith status --target .
agentsmith compatibility --json
agentsmith install --agent native --uninstall --target .
```

`--agent` accepts an ID, repeated IDs, comma-separated IDs, or the groups `native`, `standard`, `local`, and `all`. The older `--platform` flag remains a compatibility alias. MCP is project-scoped. Organization policy, plugin packs, design-system generation, and direct ownership flags remain available in `agentsmith install --help` for specialized automation.

### Source installation for contributors

The source route requires Python 3.11+ and Git:

```console
git clone https://github.com/PromptPartner/agentsmith.git
cd agentsmith
python3 agentsmith.py
```

On Windows, use `py -3 agentsmith.py`. The shell and PowerShell launchers are compatibility wrappers around the same Python program. End users should prefer the signed standalone release.

### Updates and rollback

Standalone users update the central CLI with the next signed operating-system installer, then run
`agentsmith status --target /path/to/project`. Project rules and state remain in place.

Source-based installations use staged, authenticated update plans:

```console
agentsmith update check
agentsmith update plan --target /path/to/project --save /tmp/agentsmith-update.json
agentsmith update apply --plan /tmp/agentsmith-update.json
agentsmith update rollback --receipt /path/printed/by/apply.json
```

Planning downloads and inspects the selected stable release without running candidate code. Apply refuses an edited plan, a moved tag, changed managed files, or a staged result that differs from the authenticated proposal. A failed apply restores the previous bytes. Weekly update checks are opt-in and report only.

### Verification helpers

```console
agentsmith verify --list
agentsmith verify
agentsmith verify --record .harness/receipts/my-check --tree-class operator-worktree
agentsmith secret-scan
agentsmith handoff ITEM-123
```

Replace the generated `unwired` phase in `.harness/verify.conf` with the project's real build, lint, test, render, or evaluation commands before claiming the project is verified.

## Troubleshooting

Run `agentsmith doctor --target .` first. It reports each instruction source, selected profile, managed capability, safety setting, runtime, verification coverage, and one next action. See the [troubleshooting guide](docs/17-troubleshooting.md) for recovery details.
