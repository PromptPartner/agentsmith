---
name: harness-help
description: Orient a non-coder to this project's Agentsmith harness — fires on "what is this harness?", "what are my rules?", "which profile am I on?", "what do I type next?". Part of the Agentsmith harness; reads CLAUDE.md and reports the active profile, a short rules summary, the safety mode, and the next thing to type — in plain language.
---

# Harness help — get oriented

Explain, in plain language with no jargon, what this harness does for the operator and what to do
next. This is the non-coder's front door.

## When this fires
"what is this harness / what does it do?" / "what are my rules?" / "which profile am I on?" /
"what do I type next?" / a general "help me get started here".

## What to do (no script needed)
Read `CLAUDE.md` — specifically its `AGENTSMITH:BEGIN … END` managed block — and report:
1. **Active profile(s)** — the work-type this project is tuned for (from the profile section).
2. **Your rules, in 3–5 bullets** — the load-bearing ones (verify before done, protected main,
   look before you delete, be honest about what failed). Summarize; don't dump the file.
3. **Safety mode** — read `.claude/settings.local.json` `defaultMode` if present: cautious (asks
   before shell/network) vs trusted (runs freely). Say which, plainly.
4. **What to type next** — take one small task end to end; say "verify" (or `/verify`) to check
   it's shippable; say "handoff" (or `/handoff`) to wrap up so nothing is lost.

Point to `docs/01-harness-philosophy.md` and `docs/07-how-to-pick-a-profile.md` for the why and the
profile choices. If `FIRST-STEPS.md` exists, point at it too.

## Report
A short, friendly orientation: the profile, a few rules, the safety mode, and the one thing to do
next. No file dumps, no jargon.
