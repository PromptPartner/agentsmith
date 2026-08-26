---
name: harness-doctor
description: Check whether this project's Agentsmith harness is installed correctly and healthy — fires on "is my harness set up right?", "harness doctor", "check my harness". Part of the Agentsmith harness; checks each selected agent's managed rules, settings, skills, hooks, verification, and leanness with a one-line fix for each finding.
compatibility: Requires filesystem and command access; the full report requires the cross-platform Agentsmith CLI.
---

# Harness doctor — is the harness healthy?

Confirm the harness is wired correctly, in plain language, with a concrete fix per finding.

## When this fires
"is my harness set up right / healthy?" / "harness doctor" / after an install or a `--self-update`.

## Identify the target
Use the agent named by the operator or the explicit `AGENTSMITH_AGENT` value. Never infer the active
agent from this skill's install path: `.agents/skills` is shared across clients. Without an explicit
agent, run the common project checks and label agent-specific capabilities as unknown.

## Fast path — if the Agentsmith CLI is available
Run `agentsmith doctor`, adding `--agent <id[,id...]>` when the target is known. If the command is
not on PATH, use `.agentsmith/agentsmith` on macOS/Linux or `.agentsmith\\agentsmith.cmd` on Windows. Report instructions,
skills, MCP/config, hooks, and runtime helpers separately; an unsupported optional capability does
not make instruction discovery unhealthy.

## Fallback — self-contained project checks
Check each; report pass, or a one-line fix:
- **Rules:** canonical `AGENTS.md` is present and contains an `AGENTSMITH:BEGIN … END` managed
  block. When a target requires a generated instruction adapter such as `CLAUDE.md`, compare its
  managed content with `AGENTS.md`. Fix: update the intended agent through the Agentsmith installer.
- **Configuration:** validate only the declared target's native configuration. For Claude, check
  `.claude/settings.json` and/or `settings.local.json`. For Codex, validate `.codex/config.toml`
  when present and the managed `config.toml` under `CODEX_HOME` (or the user's `.codex` directory
  when that variable is unset). Never treat one client's configuration as proof of another's.
- **Skills and hooks:** inspect the shared `.agents/skills` pack first, then any genuinely required
  client adapter and the target's declared hook integration. Never report hook parity for a client
  that only discovers instructions or skills.
- **`.harness/verify.conf`** exists AND has a real phase — not just the `sanity ::` placeholder.
  Fix: edit it to list this project's real checks.
- **Runtime helpers:** `agentsmith verify --list` succeeds without requiring Bash or WSL.
- **Leanness:** use the compatibility report's static-context measurement for canonical
  `AGENTS.md`, and report the line/token budget.
  Over budget → move prose into a skill or doc, not more `core/`.

## Report
A short pass/fix list headed by the selected agent or “common project checks,” most-important
first. End with the single highest-value fix to do next.
