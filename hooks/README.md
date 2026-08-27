# Hooks

Two kinds live here:
- **Claude Code and Codex session hooks** (this file, below) — handoff automation and UI reminders,
  installed globally for the selected runtime.
- **Git guardrails** (`hooks/git/`) — pre-commit / commit-msg / pre-push checks, installed per repo
  via `scripts/install-git-hooks.sh`. See the **Git guardrails** section at the bottom.

## Handoff hooks

The keyword hook automates the harness's handoff discipline (core/50) in both Claude Code and
Codex: bring work to a safe state and emit a recall prompt before a session ends mid-edit. The
same script understands each runtime's `UserPromptSubmit` payload and emits its expected context
shape.

Install the native hook set for the selected platform with:

```bash
./setup.sh --platform claude --with-handoff-hooks
./setup.sh --platform codex  --with-handoff-hooks
./setup.sh --platform both   --with-handoff-hooks
```

Both clients receive absolute commands pointing at the installed Python runtime. Claude stores hook
definitions in `settings.json`; Codex stores them in `$CODEX_HOME/hooks.json`. Both merges are
idempotent and preserve unrelated hooks. Codex requires a one-time trust review after installation:
open `/hooks`, inspect the definitions, and approve them.

## What you get

These hooks automate the **cue inside the current session**, not the session transition itself.
The keyword hook injects the handoff protocol, and Claude's Stop hook can prevent one stop long
enough for the agent to run it. Neither hook proves that the tree is safe, verifies the handoff
note, or opens a fresh context. Complete the safe-state + note steps, then start a fresh chat with
the generated kickoff block. A controller that verifies those steps and creates the successor
session would be a separate rollover orchestrator; it is not part of the current hook set.

### 1. `handoff-on-keyword.sh` — UserPromptSubmit — **reliable**
When your prompt contains **"handoff"** or **"wrap up"**, it injects the handoff protocol
(safe-state → handoff note → paste-ready recall prompt). This is the path to trust: it keys off
the prompt text, which the hook always receives. This is the recommended primary trigger.

### 2. `context-budget-nudge.sh` — Stop — **best-effort / experimental**
Claude Code only. This hook is not installed for Codex because it depends on Claude's status line;
Codex therefore gets the reliable keyword hook, but no percentage-triggered handoff.

When context **used** crosses a threshold (default **30%**, set `HANDOFF_PCT_THRESHOLD` to an
integer from 1–100), it nudges **once per session** toward a handoff. The default is deliberately
*low* — the cue is to hand off
**early**, when the window is ~25–30% used, not when it's nearly full: model quality degrades as
context fills (Opus 4.8's sweet spot is ~25–40% used, so you hand off near the bottom of the band).
When a valid threshold signal exists, the Stop response is an enforced cue: it blocks that stop and
returns the handoff reason to the agent. It still does not execute or verify the handoff itself.

> **Honest caveat.** No Claude Code hook receives the live context-% — only the **statusline**
> does. So this hook reads the % that AgentSmith's installed `agentsmith-statusline.py` writes to a temp file
> (`$TMPDIR/claude-ctx-<session>.pct`). That makes it inherently fragile: the file can be stale
> (the statusline hasn't re-rendered since the last turn) or missing (statusline not installed).
> Files older than 300 seconds are ignored; `HANDOFF_SIGNAL_MAX_AGE_SECONDS` can set a 1–3600
> second freshness window.
> The dependable signals remain the **"handoff" keyword** above and the **human-watched
> `ctx:NN%` gauge** in the status line. Treat this as a backstop, not a guarantee. Full
> feasibility write-up: `docs/research/claude-code-hooks-and-managed-policy.md`. The separate
> automatic-rollover decision is recorded in
> `docs/research/handoff-rollover-orchestration.md`.

## Manual wiring

If you'd rather edit `settings.json` yourself instead of `--with-handoff-hooks`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "bash ~/.claude/hooks/handoff-on-keyword.sh" } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "bash ~/.claude/hooks/context-budget-nudge.sh" } ] }
    ]
  }
}
```

Keep only the `UserPromptSubmit` entry if you want the reliable half without the experimental one.

Codex uses the same event in `$CODEX_HOME/hooks.json`; setup writes an absolute, safely quoted
command because `CODEX_HOME` may contain spaces. A minimal definition is:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "bash \"/absolute/path/to/CODEX_HOME/hooks/handoff-on-keyword.sh\"" } ] }
    ]
  }
}
```

After adding or changing a Codex command hook, review it through `/hooks`; Codex skips untrusted
non-managed hooks.

Hook schemas can shift between runtime versions — if a hook seems inert, check the current hook
docs. The scripts fail safe: no `jq`, bad input, or stale signal is a no-op, never a blocked prompt.

---

## UI design-system nudge (`ui-design-reminder.sh`) — PreToolUse — opt-in

A third session hook, for the `software-dev` profile's design-system discipline. It recognizes
Claude `Edit`/`Write`/`MultiEdit` file paths and every affected path in a Codex `apply_patch`. On a
**UI file** (`*.tsx *.jsx *.vue *.svelte *.css *.scss *.less *.astro`, or a path under
`components/`/`ui/`) it injects a **once-per-session**, **non-blocking** reminder to consult
`DESIGN.md`. It self-gates on a project-root `DESIGN.md` and returns only PreToolUse
`additionalContext`: it never blocks or auto-approves the edit. Unknown or malformed patch input
is a silent no-op.

Install it at setup, when you tell the wizard the project has a UI:

```bash
./setup.sh --profile software-dev --design-system stub      # scaffolds DESIGN.md, then offers the hook
```

Or wire it by hand (global `~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "hooks": [ { "type": "command", "command": "bash ~/.claude/hooks/ui-design-reminder.sh" } ] }
    ]
  }
}
```

For Codex, put the equivalent entry in `$CODEX_HOME/hooks.json` with matcher `^apply_patch$` and
an absolute command path to `$CODEX_HOME/hooks/ui-design-reminder.sh`, then approve it through
`/hooks`.

Non-regression tests: `bash scripts/test-handoff-on-keyword.sh`,
`bash scripts/test-context-budget-nudge.sh`, and `bash scripts/test-ui-design-reminder.sh`. They
exercise both runtime schemas, fail-open and threshold behavior, once-per-session behavior, and
Codex add/update/delete/multi-file patches.

---

## Git guardrails (`hooks/git/`)

The supported installer path is deliberately narrow:

```bash
./setup.sh --agent native --profile software-dev --with-hooks --target .
```

It installs only a thin pre-commit dispatcher to the Python `agentsmith secret-scan` command. If a
foreign pre-commit hook exists, setup preserves it and prints the command to integrate manually;
it never overwrites foreign hook logic.

The older shell hook bundle remains available as an explicit manual tool. It is not installed by
`--with-hooks`:

```bash
./scripts/install-git-hooks.sh --minimal                    # secret scan only
./scripts/install-git-hooks.sh --protect-main --conventional
./scripts/install-git-hooks.sh --branch-naming --tests-green
./scripts/install-git-hooks.sh --all
```

That manual installer manages `.git/hooks/{pre-commit,commit-msg,pre-push}` and recognizes its own
legacy markers. Review those scripts before opting in; protect-main, conventional commits,
branch-naming, and tests-green are not part of the current Python install contract.

| Guardrail | Git hook | Default | What it does |
|-----------|----------|---------|--------------|
| **secret-scan** | pre-commit | always | No live secrets in a commit (Rule 8). |
| **protect-main** | pre-commit | recommended | Refuse commits on `main`/`master` — branch first. (The very first commit, before the branch is born, is allowed.) Override `PROTECTED_BRANCHES`. |
| **conventional-commit** | commit-msg | recommended | Subject must be `type(scope): why`. Merge/revert/fixup pass. Override `CC_TYPES`. |
| **branch-naming** | pre-push | opt-in | Branch must match `BRANCH_PATTERN` (default `you/ai-123-slug`) so PRs auto-link. Base branches exempt. |
| **tests-green** | pre-push | legacy opt-in | Runs the legacy `scripts/verify.sh`; new installs should call `agentsmith verify`. |

Every guardrail is bypassable for a single commit/push with `--no-verify` (use sparingly), and each
fails safe. They're plain scripts — test one directly, e.g. `hooks/git/conventional-commit.sh msg.txt`.
