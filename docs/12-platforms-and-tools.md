# Platforms, tools & surfaces — what runs where

## Operating systems

| OS | Status | Notes |
|---|---|---|
| **macOS** | Native | One-line installer, auto-updates. |
| **Linux** | Native | One-line installer, auto-updates. |
| **Windows** | Native | Run **`setup.ps1`** — a native PowerShell port of `setup.sh` (same flags, same behaviour) that needs no Git Bash for setup itself. The runtime helper scripts (`verify.sh`, the git hooks) are still bash, so **install Git for Windows or use WSL** if you want those to run; otherwise `setup.ps1` warns where a POSIX shell is required. |

The assembled `CLAUDE.md` (and `AGENTS.md`/`GEMINI.md`) are **plain markdown — fully
OS-agnostic.** Only the shell scripts care about the OS. On Windows-native, run **`setup.ps1`**
for setup (`./setup.ps1 --wizard` or any `--flag`s, identical to `setup.sh`); use **WSL or Git
Bash** for the bash helper scripts (`verify.sh`, hooks).

## Surfaces (where Claude Code runs)

| Surface | Rules (CLAUDE.md) | Plugins / Skills | Hooks | Local MCP | Shell scripts |
|---|---|---|---|---|---|
| Terminal CLI | ✅ | ✅ | ✅ | ✅ | ✅ |
| VS Code / JetBrains | ✅ | ✅ | ✅ | ✅ | ✅ |
| Desktop app | ✅ | ✅ | ✅ | ✅ | ✅ |
| Web (claude.ai/code) | reads repo rules | ❌ | ❌ | cloud MCP only | ❌ |
| iOS | limited | ❌ | ❌ | cloud MCP only | ❌ |

The harness is fullest on the **local** surfaces. Web/iOS are cloud-only: no local hooks, no
local MCP, no on-disk `.claude/` discovery.

## Claude Code vs claude.ai vs Cowork vs other tools

- **Claude Code** — what this harness targets. Gets everything: rules + plugins + skills + hooks
  + MCP + the verify/setup scripts.
- **claude.ai web "Projects"** — you can paste the assembled rules into a Project's custom
  instructions to get the *rules* (not plugins/hooks/scripts). Good for chat-style work.
- **Claude Cowork** (Anthropic's knowledge-work agent) — reads/edits files in folders, connects
  to Drive/Gmail/etc. Your **marketing / document / data / research / general-admin** profiles
  fit it well. Use the rules as instructions; the plugin/script automation stays Claude-Code-only.
- **Other agentic tools** — `CLAUDE.md` is Claude Code's filename. The cross-tool convention is
  **`AGENTS.md`** (OpenAI Codex reads it; the Google SDLC paper treats `AGENTS.md`/`CLAUDE.md`/
  `GEMINI.md` as one "rule file"). `GEMINI.md` is for Gemini CLI. Cursor/Windsurf use their own
  files. Emit the extra filenames with `setup.sh --also-agents-md` and/or `--also-gemini-md`;
  for others, symlink or copy `CLAUDE.md`.

### Running it in Codex, Gemini CLI, and other agents

The rules are plain Markdown, so the *judgment* of the harness travels to any agent that reads a
rule file. The *machinery* (skills, hooks, setup/verify scripts) is Claude Code-specific — on
other tools you get the operating discipline, and you run `verify.sh` yourself in a terminal
rather than through the agent.

- **OpenAI Codex (the coding agent in ChatGPT).** Assemble with `--also-agents-md`, which writes
  an `AGENTS.md` next to `CLAUDE.md` from the same core+profile source:
  `./setup.sh --profile software-dev --target . --also-agents-md`. Codex picks up `AGENTS.md`
  automatically. Re-running keeps both files in sync — edit `core/`/`profiles/`, never the
  generated file.
- **Gemini CLI.** Same, with `--also-gemini-md` for `GEMINI.md`. You can emit all three at once;
  they're byte-identical rules under three names, so a mixed-tool team shares one rulebook.
- **Cursor / Windsurf / others.** They read their own rule-file names — symlink or copy `CLAUDE.md`
  to whatever the tool expects; the content is portable as-is.

This is also what makes the **plan-in-one-tool, build-in-another** pattern work — e.g. plan in
Claude, execute in Codex — since both are reading the same rules. The model-and-tool-per-phase
technique is in [`05-operating-modes.md`](05-operating-modes.md); verification stays constant
across whichever tool ran the step ([`03-verify-means-evidence.md`](03-verify-means-evidence.md)).
The seam also runs the other way, for verification: point the *second* tool at the first's diff as an
independent reviewer **and tester** — e.g. build in Claude, then have Codex write/run its own tests or
reproduce the bug (the optional `codex` gate; see [`config/plugins.md`](../config/plugins.md)).

## Per-project vs global install

Both — and the **layered** model is best:

| Layer | What | How |
|---|---|---|
| **Global (once per machine)** | config (settings, statusline), plugins, skills, and the universal **core** rules in `~/.claude/CLAUDE.md` (applies to every project) | `./setup.sh --global` |
| **Per project** | a thin `CLAUDE.md` carrying just the **profile** + project specifics | `./setup.sh --profile <name> --profile-only --target <dir>` |

Claude Code concatenates global → project automatically, so the core is loaded everywhere and
each repo only adds its profile. Prefer this once you're running the harness across several
projects. (A standalone `./setup.sh --profile <name> --target <dir>` without `--global` writes a
**self-contained** core+profile file — fine for a one-off or a machine where you don't want
global changes.)
