# Platforms, agents, and capability boundaries

AgentSmith's installer and helpers share one Python 3.11+ standard-library runtime. `setup.sh` and
`setup.ps1` are thin launchers, so macOS, Linux, and native Windows execute the same code. Managed
hooks invoke Python directly; Git Bash and WSL are not runtime requirements.

## Three compatibility layers

| Layer | Question answered |
|---|---|
| Instructions | Does the client discover canonical `AGENTS.md` at the documented scope and nesting behavior? |
| Skills and tools | Does it support Agent Skills and/or MCP, and does AgentSmith manage that surface? |
| Native runtime | Are hooks, doctor checks, and lifecycle operations supported and managed? |

A passing instruction fixture proves none of the other layers. Run `agentsmith compatibility` or
read [the compatibility contract](22-compatibility-contract.md).

## Instruction and adapter model

`AGENTS.md` is canonical. Claude receives a generated `CLAUDE.md` copy. Gemini CLI selects
`AGENTS.md`; Aider, Continue, and Goose get minimal managed pointers. Copilot, Cursor,
Windsurf/Devin, Cline, Roo Code, OpenHands, OpenCode, Junie, Zed, Jules, and Pi use the direct
adapter.

There are no instruction symlinks, proprietary imports, or independently editable duplicated
cores. Shared Agent Skills live in `.agents/skills`; only Claude gets a required runtime copy.

## Tiers and targets

- **Native:** Claude Code and Codex.
- **Certified targets:** GitHub Copilot, Cursor, Gemini CLI, Windsurf/Devin, Cline, Roo Code,
  Aider, Continue, OpenHands, Goose, OpenCode, JetBrains Junie, Zed, Jules, and Pi.
- **Community-compatible:** expected to consume `AGENTS.md`, but not tested by this project.

“Certified target” names the intended tier, not a passed claim. Unsupported and unverified remain
different states. Tabby and LM Studio are excluded as harness targets because they are model
backends; local providers are evaluated only behind a client supplying tools and context.

## Native destinations

| Surface | Claude | Codex |
|---|---|---|
| Global instructions | `~/.claude/CLAUDE.md` | `$CODEX_HOME/AGENTS.md` |
| Project instructions | generated `CLAUDE.md` + canonical `AGENTS.md` | canonical `AGENTS.md` |
| Shared project skills | `.agents/skills` | `.agents/skills` |
| Runtime skill adapter | `.claude/skills` | none |
| User config | `~/.claude/settings.json` | `$CODEX_HOME/config.toml` |
| Status line when unset | AgentSmith model/directory/context gauge | Codex built-in model/directory gauge |
| Project MCP | `.mcp.json` | `.codex/config.toml` |
| Managed hooks | Python command in Claude settings | Python command in Codex hooks config |

Capabilities without a documented stable interface stay disabled. AgentSmith does not emulate a
hook or MCP surface to make the matrix look complete.

## User-level rules (`--global`)

`install --global` writes one user-level rules file for each selected agent in this table.
`update` and `--uninstall` manage the same files.

| Agent | File `--global` writes | Location setting |
|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | none |
| Codex | `$CODEX_HOME/AGENTS.md` | `CODEX_HOME`, default `~/.codex` |
| OpenCode | `~/.config/opencode/AGENTS.md` | none; see the `XDG_CONFIG_HOME` note |
| Pi | `$PI_CODING_AGENT_DIR/AGENTS.md` | `PI_CODING_AGENT_DIR`, default `~/.pi/agent`; a leading `~` is expanded |

Other agents have no user-level file that AgentSmith manages. A global install warns for each of
them, writes nothing for them, and leaves them out of its "installed for" line. Install those agents
per project with `--target`. A global install, `update plan`, and `update apply` refuse two selected
agents whose files are the same file, for example when `CODEX_HOME` points at `~/.config/opencode`.

These destinations are fixed in code, not read from `config/agents.json`. A staged update reads the
candidate release's registry, so registry data must not decide where the trusted updater writes.
For a global install with Pi, plans and rollback receipts record `PI_CODING_AGENT_DIR`; run
`update apply` and `update rollback` with the same value that `update plan` saw. The value must be
absolute or start with `~/`. AgentSmith refuses a relative value, because Pi resolves it against
its own working directory.

**OpenCode notes**

- OpenCode loads the first file that exists of `~/.config/opencode/AGENTS.md` and
  `~/.claude/CLAUDE.md`. After a global OpenCode install, OpenCode stops reading
  `~/.claude/CLAUDE.md`.
- OpenCode honours `XDG_CONFIG_HOME`; AgentSmith always writes `~/.config/opencode`. When the two
  differ, install warns and doctor reports `opencode-xdg-config-ignored`. Unset the variable or set
  it to `~/.config`.
- OpenCode also loads skills from `~/.claude/skills` and `.claude/skills`. With Claude and OpenCode
  both selected, every AgentSmith skill exists in a Claude folder and an Agent Skills folder, and
  OpenCode keeps one copy at random. Doctor reports `duplicate-skill-discovery`. Set
  `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` in OpenCode's environment so it reads only the Agent
  Skills folders.

**Pi notes**

- Pi reads user skills from `~/.agents/skills`, resolved from your home folder, not from
  `PI_CODING_AGENT_DIR`. Project `.agents/skills` load only after Pi's trust prompt, and
  non-interactive runs skip them without notice. Use `install --global --with-skills` for Pi.
- Pi loads one context file per folder and checks `AGENTS.override.md` first. If the agent folder
  contains `AGENTS.override.md`, Pi ignores the managed `AGENTS.md`.

## Operating systems and evidence

Conformance runs natively on Ubuntu, macOS, and Windows, including spaces/Unicode, CRLF foreign
configuration, dry-run, idempotence, and owned uninstall. Closed IDE/cloud clients use dated
manual evidence where automation is unavailable.

Large local-model scenarios are scheduled/manual, not per-PR. Records include client/model
versions, model digest, context window, hardware class, latency, three-run outcome, and failures.

The authoritative matrix is [config/agents.json](../config/agents.json); its schema is
[config/agents.schema.json](../config/agents.schema.json).
