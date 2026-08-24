---
name: harness-doctor
description: Check whether this project's Agentsmith harness is installed correctly and healthy — fires on "is my harness set up right?", "harness doctor", "check my harness". Part of the Agentsmith harness; checks the active platform's managed rules, settings, skills, hooks, verification, and leanness with a one-line fix for each finding.
---

# Harness doctor — is the harness healthy?

Confirm the harness is wired correctly, in plain language, with a concrete fix per finding.

## When this fires
"is my harness set up right / healthy?" / "harness doctor" / after an install or a `--self-update`.

## Identify the platform
Use the path this skill loaded from to identify the active runtime: `.claude/skills` means Claude;
`.agents/skills` means Codex. Independently inspect `CLAUDE.md` and `AGENTS.md` for an
`AGENTSMITH:BEGIN … END` block to identify single- versus both-platform install mode. Also inspect
the global copies (`~/.claude/CLAUDE.md` and `${CODEX_HOME:-$HOME/.codex}/AGENTS.md`) during a
machine-level check. If both platforms have managed rules, check both independently and compare
their managed blocks for equivalence. If the skill path is unavailable, use the install mode as
the runtime fallback. Do not infer the active runtime from `CODEX_HOME` alone.

## Fast path — if a harness checkout is reachable
If you can find a harness checkout that has `setup.sh` (the cwd, or a path the operator names),
offer to run `bash setup.sh --doctor --platform <claude|codex|both>` for the full machine-level
report. `setup.sh` is NOT copied into projects — don't assume it's here. Claude checks may include
plugins and status-line wiring; Codex checks must not require either.

## Fallback — self-contained project checks
Check each; report pass, or a one-line fix:
- **Rules:** the platform's instruction file (`CLAUDE.md` or `AGENTS.md`) is present and contains
  an `AGENTSMITH:BEGIN … END` managed block. In both mode, compare both managed blocks exactly.
  Fix: re-install for the intended platform, or run `./setup.sh --self-update` from a checkout.
- **Configuration:** for Claude, check `.claude/settings.json` and/or `settings.local.json`. For
  Codex, validate `.codex/config.toml` when present and the Agentsmith-managed block in
  `${CODEX_HOME:-$HOME/.codex}/config.toml`; confirm its approval/sandbox pair is one of the two
  supported safety mappings. Never treat Claude settings as proof of a Codex install.
- **Skills and hooks:** Claude uses `.claude/skills` and Claude settings/hooks; Codex uses
  `.agents/skills` and `${CODEX_HOME:-$HOME/.codex}/hooks.json` plus its hooks directory. In both
  mode check both native copies. Codex has no Agentsmith plugin or status-line requirement.
- **`.harness/verify.conf`** exists AND has a real phase — not just the `sanity ::` placeholder.
  Fix: edit it to list this project's real checks.
- **`scripts/*.sh`** present and executable. Fix: `chmod +x scripts/*.sh`.
- **Leanness:** if `./scripts/lint-leanness.sh` exists, run it with no file argument so it checks
  the active instruction file — or both managed copies — and report the line/token budget.
  Over budget → move prose into a skill or doc, not more `core/`.

## Report
A short pass/fix list headed by the active platform, most-important first. End with the single
highest-value fix to do next.
