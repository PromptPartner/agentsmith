# Platforms, tools & surfaces — what runs where

Agentsmith installs Claude Code and OpenAI Codex as first-class targets. Choose with
`--platform claude|codex|both`; the default remains `claude`, so existing commands do not change.
The wizard asks the same question. `both` writes independent native copies, never symlinks, so the
result travels cleanly with a repository and works on Windows.

`--also-agents-md` remains as a deprecated compatibility flag. It emits only an extra instruction
file; use `--platform both` for Codex config, skills, MCP, and hooks too.

## Operating systems

| OS | Status | Notes |
|---|---|---|
| **macOS** | Native | Run `setup.sh`; `CODEX_HOME` may be an Orca-style path containing spaces. |
| **Linux** | Native | One-line installer, auto-updates. |
| **Windows** | Native | Run **`setup.ps1`** — a native PowerShell port of `setup.sh` (same flags, same behaviour) that needs no Git Bash for setup itself. The runtime helper scripts (`verify.sh`, the git hooks) are still bash, so **install Git for Windows or use WSL** if you want those to run; otherwise `setup.ps1` warns where a POSIX shell is required. |

The assembled rule files are **plain Markdown — fully OS-agnostic.** Only the shell scripts care
about the OS. On Windows-native, run **`setup.ps1`**
for setup (`./setup.ps1 --wizard` or any `--flag`s, identical to `setup.sh`); use **WSL or Git
Bash** for the bash helper scripts (`verify.sh`, git hooks). Codex's user directory is
`CODEX_HOME` when set, otherwise `~/.codex`; setup uses that one resolved path and never scans or
modifies other Orca account homes.

## Native destinations

| Surface | Claude | Codex |
|---|---|---|
| Global rules | `~/.claude/CLAUDE.md` | `$CODEX_HOME/AGENTS.md` |
| Project rules | `CLAUDE.md` | `AGENTS.md` |
| Global skills | `~/.claude/skills` | `~/.agents/skills` |
| Project skills | `.claude/skills` | `.agents/skills` |
| User config | `~/.claude/settings.json` | `$CODEX_HOME/config.toml` |
| Project MCP | `.mcp.json` | `.codex/config.toml` |
| User hooks | Claude settings + `~/.claude/hooks` | `$CODEX_HOME/hooks.json` + `$CODEX_HOME/hooks` |

For `--platform both`, rule content and bundled skills are copied independently to both
destinations. Codex configuration is backed up before changes; setup updates only an
Agentsmith-owned block, preserves unrelated comments/tables, validates the TOML, and updates the
same block idempotently on re-run. MCP selections become `[mcp_servers.<name>]` tables. Re-runs
union earlier Agentsmith selections and preserve foreign servers; manually owned name conflicts
are skipped with an actionable warning.

## Runtime capabilities

| Capability | Claude | Codex |
|---|---|---|
| Native rules and skills | ✅ | ✅ |
| Project MCP | `.mcp.json` | `.codex/config.toml` |
| Handoff keyword hook | ✅ | ✅; review/trust with `/hooks` |
| UI-design reminder | Claude edit/write tools | Recognizes `apply_patch` and affected UI paths |
| Context-percentage nudge | Best-effort; depends on Claude status line | ❌ |
| `PreCompact` handoff | Not introduced in this release | Not introduced in this release |
| Claude marketplaces/plugins/status line/`rtk` wiring | ✅ when selected | Never invoked by Codex-only installs |
| Organization policy | ✅ | Out of scope; rejected with an explanation |

The keyword hook and written handoff procedure are the dependable cross-runtime mechanisms. Codex
requires hook trust after installation, so open `/hooks`, review the Agentsmith definitions, and
approve them before relying on automatic invocation.

## Local, web, and other surfaces

- **Claude Code locally** gets native rules, plugins, skills, hooks, MCP, and helper scripts.
- **Codex locally** gets native rules, skills, hooks, MCP, and helper scripts without Claude-only
  marketplaces, status line, or `rtk` setup.
- **claude.ai Projects / Cowork** can use `--export-instructions` for a paste-ready rules blob;
  local hooks, skills, and scripts do not travel into a prompt field.
- **Gemini CLI** remains an instruction-file compatibility target through `--also-gemini-md`.
  Cursor, Windsurf, and similar tools can consume the plain Markdown under their own filenames,
  but Agentsmith does not install native machinery for them in this release.

Because both first-class runtimes read the same rule source, the **plan-in-one-tool,
build-in-another** pattern works — e.g. plan in Claude, execute in Codex. The model-and-tool-per-phase
technique is in [`05-operating-modes.md`](05-operating-modes.md); verification stays constant
across whichever tool ran the step ([`03-verify-means-evidence.md`](03-verify-means-evidence.md)).
The seam also runs the other way for independent review and testing.

## Per-project vs global install

The **layered** model keeps shared rules global and repository-specific rules local:

| Layer | Claude | Codex | Example |
|---|---|---|---|
| Global core | `~/.claude/CLAUDE.md` | `$CODEX_HOME/AGENTS.md` | `./setup.sh --platform both --global` |
| Project profile | `./CLAUDE.md` | `./AGENTS.md` | `./setup.sh --platform both --profile software-dev --profile-only --target .` |

A standalone project run without `--profile-only` writes a self-contained core+profile rule file.
Use `--dry-run` to preview all selected destinations without writing. Use the same platform value
with `--uninstall` so removal is scoped and predictable; the command reports retained scaffolding
and config rather than silently deleting manually owned data.

## Codex references

The native paths and schemas above track the official OpenAI documentation for
[configuration](https://learn.chatgpt.com/docs/config-file/config-basic),
[AGENTS.md and `CODEX_HOME`](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[skills](https://learn.chatgpt.com/docs/build-skills),
[hooks](https://learn.chatgpt.com/docs/hooks), and
[MCP](https://learn.chatgpt.com/docs/extend/mcp).
