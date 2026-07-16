# Hooks

Two kinds live here:
- **Claude Code session hooks** (this file, below) — handoff automation, installed globally.
- **Git guardrails** (`hooks/git/`) — pre-commit / commit-msg / pre-push checks, installed per repo
  via `scripts/install-git-hooks.sh`. See the **Git guardrails** section at the bottom.

## Handoff hooks (Claude Code session hooks)

Two hooks that automate the harness's handoff discipline (core/50): bring work to a safe state
and emit a recall prompt **before** context runs out, so a session never dies mid-edit.

Install both (global) with:

```bash
./setup.sh --with-handoff-hooks
```

That copies the scripts to `~/.claude/hooks/`, refreshes `~/.claude/statusline-command.sh` (so it
persists the context-% signal), and wires both hooks into `~/.claude/settings.json` (idempotent;
keeps a `.bak`). Needs `jq`.

## What you get

### 1. `handoff-on-keyword.sh` — UserPromptSubmit — **reliable**
When your prompt contains **"handoff"** or **"wrap up"**, it injects the handoff protocol
(safe-state → handoff note → paste-ready recall prompt). This is the path to trust: it keys off
the prompt text, which the hook always receives. This is the recommended primary trigger.

### 2. `context-budget-nudge.sh` — Stop — **best-effort / experimental**
When context **used** crosses a threshold (default **30%**, set `HANDOFF_PCT_THRESHOLD`), it nudges
**once per session** toward a handoff. The default is deliberately *low* — the cue is to hand off
**early**, when the window is ~25–30% used, not when it's nearly full: model quality degrades as
context fills (Opus 4.8's sweet spot is ~25–40% used, so you hand off near the bottom of the band).

> **Honest caveat.** No Claude Code hook receives the live context-% — only the **statusline**
> does. So this hook reads the % that `statusline-command.sh` writes to a temp file
> (`$TMPDIR/claude-ctx-<session>.pct`). That makes it inherently fragile: the file can be stale
> (the statusline hasn't re-rendered since the last turn) or missing (statusline not installed).
> The dependable signals remain the **"handoff" keyword** above and the **human-watched
> `ctx:NN%` gauge** in the status line. Treat this as a backstop, not a guarantee. Full
> feasibility write-up: `docs/research/claude-code-hooks-and-managed-policy.md`.

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

Hook stdin/output schemas can shift between Claude Code versions — if a hook seems inert, check
the current `hooks` docs (the scripts fail safe: no `jq`, bad input, or stale signal → no-op,
never a blocked prompt).

---

## Git guardrails (`hooks/git/`)

Per-repo git hooks that enforce the harness's git discipline. Install with:

```bash
./scripts/install-git-hooks.sh            # recommended set: secret-scan + protect-main + conventional
./scripts/install-git-hooks.sh --all      # + branch-naming + tests-green
./scripts/install-git-hooks.sh --branch-naming --tests-green   # add the opt-in ones
./scripts/install-git-hooks.sh --minimal  # secret-scan only (legacy)
# or, during setup:  setup.sh --profile X --with-hooks   (installs the recommended set)
```

The installer writes thin `.git/hooks/{pre-commit,commit-msg,pre-push}` dispatchers that call the
scripts in `hooks/git/`. It backs up any foreign hook it would overwrite and is re-runnable.

| Guardrail | Git hook | Default | What it does |
|-----------|----------|---------|--------------|
| **secret-scan** | pre-commit | always | No live secrets in a commit (Rule 8). |
| **protect-main** | pre-commit | recommended | Refuse commits on `main`/`master` — branch first. (The very first commit, before the branch is born, is allowed.) Override `PROTECTED_BRANCHES`. |
| **conventional-commit** | commit-msg | recommended | Subject must be `type(scope): why`. Merge/revert/fixup pass. Override `CC_TYPES`. |
| **branch-naming** | pre-push | opt-in | Branch must match `BRANCH_PATTERN` (default `you/ai-123-slug`) so PRs auto-link. Base branches exempt. |
| **tests-green** | pre-push | opt-in | Runs `scripts/verify.sh` before push; blocks if red. |

Every guardrail is bypassable for a single commit/push with `--no-verify` (use sparingly), and each
fails safe. They're plain scripts — test one directly, e.g. `hooks/git/conventional-commit.sh msg.txt`.
