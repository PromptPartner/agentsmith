# Install Agentsmith by asking your agent

**For the human:** you don't have to run anything. If you already use a coding agent — Claude Code,
Codex, OpenClaw, Cursor, or similar — paste the prompt below into it *while you're in your project
folder*, and the agent will install the Agentsmith harness for you. It uses its own terminal, so you
never touch one.

```
Set up the Agentsmith harness in this project for me. Read the instructions at
https://raw.githubusercontent.com/PromptPartner/agentsmith/master/AGENT-INSTALL.md
and follow them: get the harness, detect the right profile for this project, ask me
anything you need, show me what you'll change, and then run its setup.
```

> If the repository is still private, the raw link above won't load. In that case: clone or download
> Agentsmith somewhere first, then tell your agent *"read `AGENT-INSTALL.md` in `<that folder>` and
> follow it to set up the harness in this project."*

---

## Instructions for the agent

You are an AI coding agent with shell and file access, working in the user's project directory. Your
job is to install the **Agentsmith** harness (native Claude/Codex operating rules + supporting
scaffold) for this user. Follow these steps in order. **Ask the user the questions in step 4 — don't
guess — and show them the plan before you write anything.** The setup script backs up any file it
changes, but you should still confirm first.

### 1. Get the harness
- If an Agentsmith checkout already exists on this machine, use it.
- Otherwise clone it to a permanent tools location (it's a tool the user keeps, not a per-project
  dependency):
  - macOS / Linux: `git clone https://github.com/PromptPartner/agentsmith.git ~/tools/agentsmith`
  - Windows (PowerShell): `git clone https://github.com/PromptPartner/agentsmith.git $HOME\tools\agentsmith`
- If you cannot reach the repository (private, no network, no credentials), **stop and tell the
  user** how to get it manually — do not fabricate the files.
- If `git` is missing, install it (or have the user install it) first — the setup script's own
  `--wizard` will also detect this and guide the install.

### 2. Pick the setup script for this OS
- macOS / Linux → `./setup.sh`
- Windows → `pwsh ./setup.ps1` (needs PowerShell 7+; check `pwsh --version`)

Both take the **same flags**. Everywhere below, `<setup>` means whichever applies.

### 3. Detect the right profile
Run the detector against the current project (this writes nothing):
```
<setup> --platform claude --profile auto --assemble-only --target . --dry-run
```
Note the auto-detected profile it prints (`software-dev`, `devops-setup`, `data-crunching`,
`document-creation`, or `general-admin`). Platform does not affect detection and dry-run writes
nothing; ask for the real destination in step 4. If the project clearly mixes types, note that too.

### 4. Ask the user (only what's needed)
Ask these briefly, accept short answers, and use sensible defaults if they don't care:
1. **Platform** — "Install for Claude, Codex, or both?" Default: `claude` for compatibility. If
   you are Codex, recommend `codex`; if the user actively uses both, recommend `both`.
2. **Profile** — "This looks like a `<detected>` project — good, or should I use a different one?"
   (offer the list above).
3. **Your name & role** — optional; it just personalises the rules. Blank is fine.
4. **Scope** — "Install it **globally** so every project on this computer follows the core rules
   (recommended), or **just this project**?" Default: **global** (the full install).
5. **Tracker** — optional: where they track bugs/tasks (Linear, GitHub, or a `KNOWN-ISSUES.md`).
6. **Tracker writes** — only if they named a tracker in 5. Ask it as its own question; do **not**
   infer it from the answer above: *"Should I be able to create issues and post comments in
   `<tracker>` myself, or should I draft them and let you post?"* Default (and the answer if they
   don't care): **draft** → omit the flag. Only pass `--tracker-writes allowed` on an explicit yes.
   Naming a tracker says where the team works; it is not permission to write there.

### 5. Run setup (full install is the default)
Show the exact command(s) first, then run on confirmation.

- **Global (recommended default)** — install the core + machine config once, then a thin
  per-project profile:
  ```
  <setup> --platform <chosen-platform> --global --operator-name "<name>" --operator-role "<role>" --tracker "<tracker>"
  <setup> --platform <chosen-platform> --profile <chosen> --profile-only --target .
  ```
  Append `--tracker-writes allowed` to the first command **only** if they explicitly said yes to
  question 6. Omitted = the safe default (you draft the item, they post it).
- **This project only** — a single self-contained file, nothing global:
  ```
  <setup> --platform <chosen-platform> --profile <chosen> --operator-name "<name>" --target . --assemble-only
  ```

The script is idempotent and backs up any existing file before changing it (look for the
`backup: …bak…` lines in its output). It does **not** overwrite anything without `--force`.

### 6. Verify and report
- Confirm it wrote the selected native rule file: Claude `CLAUDE.md`, Codex `AGENTS.md`, or both.
  For global installs, also confirm `~/.claude/CLAUDE.md` and/or `$CODEX_HOME/AGENTS.md` (default
  Codex home: `~/.codex`). Do not inspect other Orca account homes.
- Tell the user what changed, then give them the three next steps the script prints:
  1. edit `.harness/verify.conf` with the project's real checks,
  2. skim the new native rule file(s) and resolve any `[TODO: …]` placeholders,
  3. read `docs/01-harness-philosophy.md` for the 5-minute "why".
- To remove Agentsmith-managed content later, use the same platform and scope:
  `<setup> --platform <chosen-platform> --uninstall --target .` (and `--uninstall --global`).
  Report the scaffolding/config the command intentionally retains; do not describe it as deleting
  manually owned configuration.

### Guardrails
- **Confirm before writing.** Show the plan; don't run setup silently.
- **Global install touches platform homes** — say exactly which ones before you do it:
  `~/.claude` for Claude; resolved `$CODEX_HOME` plus `~/.agents/skills` for Codex.
- **Codex hook trust is interactive** — if hooks were installed, tell the user to review them with
  `/hooks`. Do not claim the Claude context-percentage nudge or a `PreCompact` hook exists in Codex.
- **Org policy is Claude-only** — never combine `--org-policy` with platform `codex` or `both`.
- **Never invent the harness files.** If you couldn't get the repo in step 1, stop.
- **When unsure, ask** rather than guess — that's the whole point of step 4.
