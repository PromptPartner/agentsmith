# Manual install (the docs-only path)

`setup.sh` does all of this for you — and if you're unsure which flags you need, `./setup.sh
--wizard` asks the questions interactively and prints the exact command before running it. Use
the manual steps below only if you're on a shared/locked-down machine, don't want a script
touching `~/.claude`, or just want to understand what setup does.

## On Windows / PowerShell — use `setup.ps1`

On native Windows (no Git Bash / WSL), run **`setup.ps1`** instead of `setup.sh`. It's a faithful
port: **same flags, same behaviour, same output** — including `--wizard`, `--global`,
`--profile-only`, `--with-mcp`, `--org-policy`, `--export-instructions`, and `--self-update`. So
everywhere this guide (or the README) shows a `setup.sh` command, the Windows equivalent is the
same line with `setup.sh` swapped for `setup.ps1`:

```powershell
# the bash      ./setup.sh --profile software-dev --target .
# becomes       pwsh ./setup.ps1 --profile software-dev --target .
pwsh ./setup.ps1 --wizard
```

**Requires PowerShell 7+ (`pwsh`)** — the cross-platform PowerShell, not the older Windows
PowerShell 5.1 that ships in the box. Check with `pwsh --version`; if it's missing, install it from
the [PowerShell releases](https://github.com/PowerShell/PowerShell/releases) (or `winget install
Microsoft.PowerShell`). No `jq` needed — `setup.ps1` does its JSON merging natively. If PowerShell
blocks the script, run it as shown above (`pwsh ./setup.ps1 …`) or allow local scripts for the
session with `Set-ExecutionPolicy -Scope Process Bypass`.

The rest of this guide uses `setup.sh` for brevity; Windows users mentally substitute `setup.ps1`.

## 1. Assemble the rules (CLAUDE.md)

Either run the assembler without touching anything global:

```bash
./setup.sh --profile <name[,name]> --assemble-only --target /path/to/project
```

…or do it by hand: concatenate `core/*.md` (in filename order: 00,10,20,30,40,50,60) followed by
your chosen `profiles/<name>.md` into `<project>/CLAUDE.md`, then replace the placeholders:

| Placeholder | Replace with |
|---|---|
| `{{OPERATOR_NAME}}` | who leads the project |
| `{{OPERATOR_ROLE}}` | their role |
| `{{OPERATOR_BIO}}` | one or two sentences on background + how you should work with them |
| `{{TRACKER}}` | `Linear` / `GitHub Issues` / `Jira` / `a KNOWN-ISSUES.md` — **where** work is tracked |
| `{{TRACKER_POLICY}}` | **whether the agent may write there.** Set by `--tracker-writes ask\|allowed`, *not* by `{{TRACKER}}` — naming a tracker is a pointer, not permission. Default `ask` = the agent drafts the item and you post it. See [the tracker guide](docs/14-project-tracker-guide.md#grant-or-withhold-write-access). |
| `{{BRAND_PALETTE}}`, `{{BRAND_FONT}}` | only in `creative-design` — your brand colors/typeface |

**Global vs per-project:** for the layered model, install the core once globally
(`./setup.sh --global` → `~/.claude/CLAUDE.md`) and make each project's file profile-only
(`--profile-only`). Claude Code merges global + project automatically. By hand: concatenate
`core/*.md` into `~/.claude/CLAUDE.md`, and put only `profiles/<name>.md` in each `./CLAUDE.md`.

> **What `--global` writes, and what does not stop it.** `--global` always writes
> `~/.claude/CLAUDE.md` — that is the whole point of it, and it is the *only* place it writes the
> core. Two flags look like they redirect or defuse it and do not:
> `--target` is **refused** under `--global` (it would be silently ignored otherwise), and
> `--assemble-only` only skips the settings/plugins install — it still writes the file. The flag
> that writes nothing is `--dry-run`.
>
> Re-running is safe: `--global` reads the operator name/role/tracker already in the file and keeps
> them unless you pass new ones, so `./setup.sh --global` on its own will not blank your identity.
> Pass `--operator-name`/`--operator-role`/`--tracker` only when you want to *change* them. A
> timestamped backup is written before any change either way.

## 2. Scaffold the project

```bash
mkdir -p docs/research/_archive .planning .harness/handoffs scripts .claude
cp scripts/verify.sh scripts/new-research.sh scripts/handoff.sh   <project>/scripts/
cp .harness/verify.conf.example                                   <project>/.harness/verify.conf   # then EDIT it
cp templates/progress-log.md                                      <project>/.planning/
cp config/settings.local.cautious.json.example                    <project>/.claude/settings.local.json   # cautious default; swap for settings.local.trusted.json.example to run without prompts
chmod +x <project>/scripts/*.sh
```

Edit `<project>/.harness/verify.conf` so `scripts/verify.sh` runs your project's real checks.

## 3. Global config (`~/.claude/`)

```bash
cp config/statusline-command.sh ~/.claude/statusline-command.sh
```

Then merge `config/settings.json` into `~/.claude/settings.json`:
- If you have no `settings.json` yet: copy it over.
- If you do: merge the keys (`statusLine`, `enabledPlugins`, `extraKnownMarketplaces`,
  `effortLevel`, `autoMemoryEnabled`, `tui`). With `jq`:
  `jq -s '.[0] * .[1]' ~/.claude/settings.json config/settings.json > merged && mv merged ~/.claude/settings.json`

Note: the template intentionally does **not** set `skipDangerousModePermissionPrompt` or
`defaultMode: bypassPermissions`. Add those only on a sandbox you fully own and trust — they
trade safety prompts for speed.

## 4. Marketplaces + universal plugins

In Claude Code:

```
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add openai/codex-plugin-cc
/plugin install superpowers@claude-plugins-official
/plugin install code-review@claude-plugins-official
/plugin install claude-mem@thedotmack
/plugin install codex@openai-codex        # optional — needs the Codex CLI
```

Optional packs (latest from source): `/plugin marketplace add shinpr/claude-code-workflows` then
install the dev-workflow plugins; or `gopherguides/gopher-ai` + `Piebald-AI/claude-code-lsps` for
the stack/LSP plugins. `setup.sh --with-plugins dev-workflow,stack-lsp` does this for you. Update
later with `/plugin update` (or `setup.sh --update-plugins`). See [`config/plugins.md`](config/plugins.md).

## 4b. Skills & git hooks (optional)

- **Skills:** `setup.sh --with-skills` installs the bundled 6-skill harness pack (`handoff`,
  `verify`, `harness-doctor`, `harness-help`, `new-research`, `new-feedback`) plus the example.
  **Target follows the mode:** project mode → `<project>/.claude/skills/` (committable, travels with
  the repo); `--global` → `~/.claude/skills/`. The skills are self-contained + script-aware (they
  prefer a project-local `scripts/<x>.sh`, else run inline). Add your own — see
  [`skills/README.md`](skills/README.md).
- **Git guardrails:** in your project repo, `bash scripts/install-git-hooks.sh` (or
  `setup.sh --with-hooks`) installs the recommended set — **secret-scan** (no live secrets, Rule 8),
  **protect-main** (no commits straight to main — branch first), and **conventional-commit** (messages
  must be `type(scope): why`). Add the opt-in ones with `--branch-naming` (branch name must match a
  pattern so PRs auto-link) and `--tests-green` (run `verify.sh` before push); `--all` enables
  everything, `--minimal` is secret-scan only. Each is bypassable for one commit/push with
  `--no-verify`. Details: [`hooks/README.md`](hooks/README.md).
- **Handoff hooks (Claude Code):** `setup.sh --with-handoff-hooks` installs two session hooks —
  a **reliable** one that fires when you type "handoff"/"wrap up" (injects the safe-state +
  recall-prompt protocol) and a **best-effort** one that nudges when context passes ~30% used —
  i.e. hand off *early*: Opus 4.8's quality sweet spot is ~25–40% used, so the cue is when used
  *reaches* ~25–30%, not when the window is nearly full.
  Honest caveat: no hook sees the live context-% (only the statusline does), so the %-nudge reads
  a temp-file signal and is fragile — the keyword hook and the human-watched `ctx:NN%` gauge are
  the dependable triggers. Full detail: [`hooks/README.md`](hooks/README.md).
- **Leanness lint:** `scripts/lint-leanness.sh [CLAUDE.md]` (or `setup.sh --doctor`) warns when
  the assembled instructions grow past a token/line budget — the cue to move knowledge into a
  skill/doc instead of bloating static context. `--strict` makes it a verify phase.

## 4c. Updating the harness itself — `--self-update` (optional)

When the harness lives in a git checkout (you cloned it rather than copied a zip), keep it current
without re-cloning:

```bash
./setup.sh --self-update            # fast-forward this checkout, then re-assemble managed CLAUDE.md
./setup.sh --self-update --dry-run  # show the plan (remote, branch, auth scheme) — pull nothing
./setup.sh --self-update --no-reassemble   # update files only; re-run setup yourself later
```

(`setup.ps1 --self-update` is the identical Windows/PowerShell path.)

- **Where it pulls from** (first match wins, so nothing private is ever baked into the repo):
  `--from <url>` → `$HARNESS_REMOTE` env → a one-line `.harness/remote` file (gitignored) → the
  checkout's own `origin` remote.
- **Auth auto-detects from the URL.** `git@…` / `ssh://…` use the box's SSH key (nothing stored).
  `https://…` reads `$HARNESS_GH_TOKEN` at runtime — exported in your shell, supplied to git through
  an ephemeral askpass helper, and **never written to any tracked file** (it's a credential — see
  the "No live secrets in any tracked file" rule in
  [`core/20-principle-rules.md`](core/20-principle-rules.md)). For a private repo, an SSH deploy key
  is the simplest setup.
- **It won't clobber your work.** Pull is fast-forward-only and refuses a dirty or detached-HEAD
  checkout — commit or stash first. After a successful pull it re-assembles every `CLAUDE.md` /
  `AGENTS.md` / `GEMINI.md` that carries the managed markers, **preserving** your operator
  name/role/bio/tracker (recovered from the existing block, so they never regress to `[TODO]`).
- **Tracker writes fail closed on upgrade.** Updating from a harness older than the consent split
  re-renders R7 as **ask-first** and says so, even if the old rules had the agent filing issues
  directly. Those writes were inferred from naming a tracker, never actually granted — so the
  upgrade won't carry them forward. Re-run with `--tracker-writes allowed` to opt back in.

## 5. (Optional) MCP servers

Let setup do it: `setup.sh --profile <name> --with-mcp playwright,context7 --target .` extracts the
named block(s) from [`config/mcp.example.json`](config/mcp.example.json), drops the `_use` comment,
and merges them into the project's `.mcp.json` (idempotent — re-running adds without clobbering, and
an unknown name just warns with the available list). Needs `jq`. Or copy the blocks by hand into
`.mcp.json` (project scope) or `~/.claude/settings.json` (global). None are required.

## 6. Verify the install

```bash
cd <project> && ./scripts/verify.sh --list      # shows your configured phases
./scripts/verify.sh                              # runs them
```

You're set. Open the project in Claude Code; it reads `CLAUDE.md` automatically.

## 7. (Optional) Surfaces with no on-disk config — web Projects, Cowork

Some surfaces don't read a `CLAUDE.md` from disk: a claude.ai **Project**'s
custom-instructions box, **Claude Cowork**, or any assistant's system-prompt field.
For those, generate a paste-ready blob:

```bash
./setup.sh --profile software-dev --operator-name "You" --export-instructions > harness-instructions.md
# or pipe straight to the clipboard:  ... --export-instructions | pbcopy   # xclip/clip elsewhere
```

It assembles the full `core/` + chosen profile(s) with placeholders filled and the
file-management markers stripped, then prints it to stdout (guidance goes to stderr, so a
plain `> file` captures only the blob). Paste the whole thing into the surface's instructions
field. To change it later, edit `core/`/`profiles/` and re-export — don't hand-edit the paste.

## 8. (Optional) Shared / locked-down machines — org policy

For a machine many people use (a shared build box, a managed fleet), install the harness as a
**machine-wide managed policy** instead of per-user:

```bash
sudo ./setup.sh --org-policy                 # core rules, machine-wide
sudo ./setup.sh --org-policy --profile devops-setup   # bake a profile in too
```

This writes two files to the OS managed-policy directory (`/etc/claude-code` on Linux,
`/Library/Application Support/ClaudeCode` on macOS, `C:\Program Files\ClaudeCode` on Windows):

- a **managed `CLAUDE.md`** that loads before every user/project `CLAUDE.md` and **cannot be
  excluded** by an individual user; and
- a **hardened `managed-settings.json`** that sets `permissions.disableBypassPermissionsMode`
  and `permissions.disableAutoMode` to `"disable"` — so `--dangerously-skip-permissions` /
  bypass mode and background auto-mode are **unavailable on that machine**. Managed settings are
  highest precedence; a user or project cannot override them.

If a managed-settings.json already exists, the hardening is **merged** into it (your existing
allow/deny rules are preserved, a `.bak` is kept). Needs root/sudo to write the policy dir.
Set `HARNESS_ORG_DIR=/custom/path` to target a non-standard location (or to test). Use
`--dry-run` to preview the exact paths without writing.
