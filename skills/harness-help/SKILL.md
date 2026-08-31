---
name: harness-help
description: Orient a non-coder to this project's Agentsmith harness — fires on "what is this harness?", "what are my rules?", "which profile am I on?", "what do I type next?". Part of the Agentsmith harness; reads the canonical instructions and selected agent's safety configuration, then reports the profile, rules, safety mode, and next step in plain language.
compatibility: Requires an Agent Skills-compatible coding agent with filesystem access.
---

# Harness help — get oriented

Explain, in plain language with no jargon, what this harness does for the operator and what to do
next. This is the non-coder's front door.

## When this fires
"what is this harness / what does it do?" / "what are my rules?" / "which profile am I on?" /
"what do I type next?" / a general "help me get started here".

## Identify the target
Use the agent named by the operator or the explicit `AGENTSMITH_AGENT` value. Never infer the active
agent from this skill's install path: portable canonical content may be copied into a required
client adapter such as `.claude/skills`. Without a declared agent, explain the common rules and
label agent-specific safety configuration as unknown.

## What to do (no script needed)
Read the canonical managed block in `AGENTS.md` and report:
1. **Active profile(s)** — the work-type this project is tuned for (from the profile section).
2. **Your rules, in 3–5 bullets** — the load-bearing ones (verify before done, protected main,
   look before you delete, be honest about what failed). Summarize; don't dump the file.
3. **Safety mode** — when an agent is declared, read its managed native configuration and explain
   the effective approval and sandbox settings. Otherwise say that client-specific safety was not
   identified.
4. **What to type next** — take one small task end to end. Say “verify” or “handoff”; mention an
   invocation prefix only when the declared client documents one.

Point to `docs/01-harness-philosophy.md` and `docs/07-how-to-pick-a-profile.md` for the why and the
profile choices. If `FIRST-STEPS.md` exists, point at it too.

## Report
A short, friendly orientation: the selected agent when known, profile, a few rules, safety mode,
and the one thing to do next. No file dumps, no jargon.
