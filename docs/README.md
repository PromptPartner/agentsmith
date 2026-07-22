# The docs — a map and a reading order

Everything in this folder is **dynamic context**: none of it is loaded into the agent unless a
task calls for it, so it costs the rule budget nothing (see
[`01-harness-philosophy.md`](01-harness-philosophy.md) for why that distinction runs the whole
design). That's also why these docs can afford to be generous while `core/` is rationed line by
line.

**The numbers are the reading order.** Go top to bottom and it reads as one course — from "what
is a harness" to "make it your team's own," with the glossary as the appendix:

| | One line |
|---|---|
| [`01-harness-philosophy.md`](01-harness-philosophy.md) | What a harness is and why the model is the small part — the 5-minute foundation. |
| [`02-your-first-hour.md`](02-your-first-hour.md) | From "it installed" to "I know what changed": the tour of your own `CLAUDE.md`, first task, first handoff. |
| [`03-verify-means-evidence.md`](03-verify-means-evidence.md) | The most load-bearing concept: what counts as proof, per kind of work. |
| [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md) | The economics of rules, the four ways they fail, and the guard for each. |
| [`05-operating-modes.md`](05-operating-modes.md) | Attended sessions vs autonomous loops, and which model for which phase. |
| [`06-your-first-loop.md`](06-your-first-loop.md) | The concrete recipe for standing up an unattended loop — safely, in order. |
| [`07-how-to-pick-a-profile.md`](07-how-to-pick-a-profile.md) | The nine profiles and how to choose (or stack) them. |
| [`08-how-to-add-a-profile.md`](08-how-to-add-a-profile.md) | Extending the harness to work it doesn't cover yet. |
| [`09-adapting-it-to-your-team.md`](09-adapting-it-to-your-team.md) | Earning your own rules, and retrofitting onto an existing project. |
| [`10-best-practices.md`](10-best-practices.md) | Dos & don'ts, each traceable to a real incident. |
| [`11-designing-uis.md`](11-designing-uis.md) | Product UI is `software-dev`: the `DESIGN.md` design-system workflow and how the harness holds UI to it. |
| [`12-whats-built-in.md`](12-whats-built-in.md) | The catalog of conveniences setup can install — the machinery. |
| [`13-platforms-and-tools.md`](13-platforms-and-tools.md) | What runs where, and how to run it in Codex / Gemini / claude.ai. |
| [`14-project-tracker-guide.md`](14-project-tracker-guide.md) | Tool-agnostic tracker conventions (and the write-consent rule). |
| [`15-safety-model.md`](15-safety-model.md) | What the harness can do to your machine, and how to bound it. |
| [`16-troubleshooting.md`](16-troubleshooting.md) | Symptom → cause → fix, for when it's behaving oddly at runtime. |
| [`17-influences.md`](17-influences.md) | Full credits — who said each idea first, plus complementary work. |
| [`18-glossary.md`](18-glossary.md) | Every harness term, one line each, with pointers. The appendix. |
| [`feedback/README.md`](feedback/README.md) | The post-incident log: how lessons become system changes. |
| [`research/`](research/) | Source research the docs above were distilled from. |

## In a hurry? Four shortcuts

**"I've never used an agent harness."** You ship software for a living; the AI-agent part is the
new bit. Read [`01`](01-harness-philosophy.md), skim [the glossary](18-glossary.md) once, then
[`04`](04-why-your-agent-ignored-the-rule.md) — the doc to read *before* a rule fails on you.

**"I just installed it."** Setup left a `FIRST-STEPS.md` card in your project — that's your first
30 minutes. Then [`02`](02-your-first-hour.md), [`03`](03-verify-means-evidence.md), and
[`05`](05-operating-modes.md) — and [`06`](06-your-first-loop.md) when you want to run something
unattended.

**"Should I trust this on my machine?"** [`15-safety-model.md`](15-safety-model.md) is the whole
posture in one place — what it can do, what's opt-in, and how to lock it down. If something's
already behaving oddly, [`16-troubleshooting.md`](16-troubleshooting.md).

**"I want to make it mine."** [`09`](09-adapting-it-to-your-team.md), then
[`10`](10-best-practices.md), then [`08`](08-how-to-add-a-profile.md) — and
[`feedback/README.md`](feedback/README.md) for the loop that makes it compound.
