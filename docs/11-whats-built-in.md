# What's built in

The core rules and the profiles are the harness's *judgment*. This page is its *machinery* — the
conveniences setup can install for you, each solving a specific recurring friction. None is
required for the rules to work; reach for them as the need shows up. Everything here is opt-in via
a `setup.sh` flag (same flags on `setup.ps1`).

If you're evaluating what the harness *does* rather than what it *believes*, this is the catalog.
For the reasoning behind any of it, the cross-links point back to the doc that explains why.

- **Setup wizard** — `setup.sh --wizard` (or bare `./setup.sh`) asks the questions interactively
  and builds + runs the right command, printing it first so you learn the flags.
- **Native Windows setup** — `setup.ps1` is a PowerShell port of `setup.sh` with the same flags
  and behaviour (including `--wizard`), so Windows users don't need Git Bash just to set up.
- **Bundled skill pack** — `setup.sh --with-skills` installs six self-contained, script-aware,
  invoke-by-name skills: `/handoff`, `/verify`, `/harness-doctor`, `/harness-help`, `/new-research`,
  `/new-feedback`. They prefer a project-local `scripts/<x>.sh` when present, else run inline, so
  they work globally, in a harness project, or in a bare repo. Project mode installs them into
  `<project>/.claude/skills/`; `--global` into `~/.claude/skills/`. See [`skills/README.md`](../skills/README.md)
  and [`skills/RECOMMENDED.md`](../skills/RECOMMENDED.md).
- **Feedback / self-improvement loop** — a `docs/feedback/` convention + `scripts/new-feedback.sh`
  scaffolder makes the System-Evolution loop a one-liner (mirrors `new-research.sh`); see
  [`feedback/README.md`](feedback/README.md) and the recurring harness-review checkpoint.
- **CLAUDE.md leanness lint** — `scripts/lint-leanness.sh` (and `setup.sh --doctor`) warn when the
  assembled static context grows past its budget, nudging knowledge into skills/docs. The *why* is
  in [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md).
- **Handoff hooks** — `setup.sh --with-handoff-hooks` installs a reliable "handoff"-keyword prompt
  hook plus a best-effort context-% nudge (the % part is fragile by design — see `hooks/README.md`).
- **Guardrail hooks** — `scripts/install-git-hooks.sh` / `setup.sh --with-hooks`: secret-scan +
  protect-main + conventional-commit (default), branch-naming + tests-green (opt-in). These are the
  deterministic guards behind the rules ([`14-safety-model.md`](14-safety-model.md) covers the posture).
- **Profile-aware `verify.conf` presets** — setup drops a starter `.harness/verify.conf` matched to
  the chosen profile(s) (dev → build/test; docs → spell/links; data → row-count reconcile).
- **MCP picker** — `setup.sh --with-mcp <name[,name]>` writes the right block from
  `config/mcp.example.json` into the project's `.mcp.json`.
- **Org-policy variant** — `sudo setup.sh --org-policy` installs a managed `CLAUDE.md` at the OS
  policy path (applies to all users on a shared box) + a stricter, no-bypass settings profile.
- **Cowork / claude.ai export** — `setup.sh --export-instructions` emits a single paste-ready
  instructions blob for surfaces without on-disk config (web Projects, Cowork). See
  [`12-platforms-and-tools.md`](12-platforms-and-tools.md) for which surfaces need it.

**Two more worth knowing about**, not flags but shipped assets: five **worked example projects**
in [`examples/`](../examples/README.md) (each a filled `CLAUDE.md` + real `verify.conf` for one
profile), and **`--self-update`**, which pulls a newer harness and re-assembles your managed
`CLAUDE.md` blocks in one step (README → "Keeping the harness current").
