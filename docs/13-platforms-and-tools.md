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
Windsurf/Devin, Cline, Roo Code, OpenHands, OpenCode, Junie, Zed, and Jules use the direct adapter.

There are no instruction symlinks, proprietary imports, or independently editable duplicated
cores. Shared Agent Skills live in `.agents/skills`; only Claude gets a required runtime copy.

## Tiers and targets

- **Native:** Claude Code and Codex.
- **Certified targets:** GitHub Copilot, Cursor, Gemini CLI, Windsurf/Devin, Cline, Roo Code,
  Aider, Continue, OpenHands, Goose, OpenCode, JetBrains Junie, Zed, and Jules.
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

## Operating systems and evidence

Conformance runs natively on Ubuntu, macOS, and Windows, including spaces/Unicode, CRLF foreign
configuration, dry-run, idempotence, and owned uninstall. Closed IDE/cloud clients use dated
manual evidence where automation is unavailable.

Large local-model scenarios are scheduled/manual, not per-PR. Records include client/model
versions, model digest, context window, hardware class, latency, three-run outcome, and failures.

The authoritative matrix is [config/agents.json](../config/agents.json); its schema is
[config/agents.schema.json](../config/agents.schema.json).
