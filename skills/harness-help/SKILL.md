---
name: harness-help
description: Orient a non-coder to this project's Agentsmith harness — fires on "what is this harness?", "what are my rules?", "which profile am I on?", "what do I type next?". Part of the Agentsmith harness; reads the active platform's instruction and safety files, then reports the profile, rules, safety mode, and next step in plain language.
---

# Harness help — get oriented

Explain, in plain language with no jargon, what this harness does for the operator and what to do
next. This is the non-coder's front door.

## When this fires
"what is this harness / what does it do?" / "what are my rules?" / "which profile am I on?" /
"what do I type next?" / a general "help me get started here".

## Identify the platform
Use the path this skill loaded from to identify the active runtime: `.claude/skills` means Claude;
`.agents/skills` means Codex. Independently inspect `CLAUDE.md` and `AGENTS.md` for an
`AGENTSMITH:BEGIN … END` managed block to identify install mode. One managed file identifies a
single-platform install; two mean both. In both mode, read both managed blocks and report any
difference — they should be equivalent. If the skill path is unavailable, use the install mode as
the runtime fallback. Do not use `CODEX_HOME` alone as evidence that Codex is active.

## What to do (no script needed)
Read the managed block in `CLAUDE.md` (Claude), `AGENTS.md` (Codex), or both, and report:
1. **Active profile(s)** — the work-type this project is tuned for (from the profile section).
2. **Your rules, in 3–5 bullets** — the load-bearing ones (verify before done, protected main,
   look before you delete, be honest about what failed). Summarize; don't dump the file.
3. **Safety mode** — for Claude, read `.claude/settings.local.json` `defaultMode` if present. For
   Codex, read the Agentsmith-managed values in `.codex/config.toml`, falling back to
   `${CODEX_HOME:-$HOME/.codex}/config.toml`: `on-request` + `workspace-write` is cautious;
   `never` + `danger-full-access` is trusted. In both mode report both and flag disagreement.
4. **What to type next** — take one small task end to end. In Claude, say "verify" or `/verify`
   and "handoff" or `/handoff`; in Codex, say "verify" or `$verify` and "handoff" or `$handoff`.

Point to `docs/01-harness-philosophy.md` and `docs/07-how-to-pick-a-profile.md` for the why and the
profile choices. If `FIRST-STEPS.md` exists, point at it too.

## Report
A short, friendly orientation: the active platform, profile, a few rules, safety mode, and the one
thing to do next. No file dumps, no jargon.
