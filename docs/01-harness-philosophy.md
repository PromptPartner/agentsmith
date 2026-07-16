# Why this harness exists (the 5-minute version)

This is the "why" behind every file in this repo. Read it once; you won't need to re-read it.

## The agent is the model **plus** the harness

> **Agent = Model + Harness**

The model (Opus, Sonnet, GPT, Gemini…) is the engine. But an engine isn't a car. The *harness* —
the instructions, tools, memory, guardrails, hooks, sub-agent orchestration, and feedback loops
wrapped around the model — is the car, the road, and the traffic laws. Industry framing (Google's
*New SDLC With Vibe Coding* whitepaper — Osmani, Saboo & Kartakis, May 2026; Anthropic's Claude
Code guidance) puts it bluntly: **the model is roughly 10% of what determines the outcome; the
harness is the other ~90%.** And the harness is the part *you* control.

The practical consequence: **most agent failures are configuration failures.** When a session
goes sideways, the honest cause is rarely "the model is dumb" — it's a missing rule, a vague
instruction, an absent guardrail, a tool that wasn't reached for, or a context window full of
noise. Public benchmarks bear this out (a coding agent moved from outside the Top 30 to the Top 5
on Terminal Bench 2.0 by changing *only the harness*; a separate team gained 13.7 points the same
way). **So invest in the harness.** That's what this template is.

## What's in a harness (and where it lives here)

| Harness component | What it is | In this template |
|---|---|---|
| **Instructions / rule files** | Who the agent is, what it must/mustn't do | `core/` + the chosen `profiles/` → assembled into `CLAUDE.md` |
| **Tools** | APIs/scripts/MCP servers it can call | `config/mcp.example.json`, `config/plugins.md`, `scripts/` |
| **Memory** | State across sessions; the project's long-term knowledge | claude-mem + `docs/`, `templates/handoff-memory.md`, progress log |
| **Guardrails / hooks** | Deterministic code at lifecycle points (e.g. block a commit with a secret) | hooks you add per project; `scripts/verify.sh` as the gate |
| **Orchestration** | Sub-agent dispatch, routing, hand-offs | `core/40-subagents-and-tools.md` |
| **Observability / eval** | How you know it's doing well — review, judges, verification | `code-review` + `codex` gate; `core` Rule 2/5; quality gates |

## Static vs dynamic context — why this template is split the way it is

Context is the agent's most precious, most expensive resource. Two kinds:

- **Static context** is loaded *every turn* and paid for *every turn*: the system prompt and rule
  files (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`). It must be **lean** — too much dilutes the
  signal and burns tokens; too little and the agent forgets the rules.
- **Dynamic context** is loaded *on demand*: skills triggered by the task, docs fetched when
  relevant, memory recalled when needed, tool results. Efficient and scalable.

This template treats that boundary as a first-class design decision:
- The assembled **`CLAUDE.md` = `core` (always) + exactly one (or a few) `profile`(s)** — kept
  deliberately lean. It's the static context.
- Everything else — the eight other profiles, the skills, `templates/`, `docs/`, research,
  memory — is **dynamic**, pulled in only when the work calls for it.

That's also why "keep the surface small" (Rule 10) is load-bearing, not pedantry: every line you
add to the static rules makes the agent a little worse at everything else.

## The spectrum: match rigor to stakes

AI work runs on a spectrum, not a switch:

| | Vibe | Structured | Agentic engineering |
|---|---|---|---|
| Spec | casual prompt | detailed prompt + constraints | formal spec / plan / memory files |
| Verification | "seems to work?" | manual spot-checks | tests + evals + review gates |
| Scope | throwaway | features in known code | production / high-stakes |
| Risk | high (fine for disposable) | moderate | low (verified at every stage) |

A weekend experiment can be pure vibe. Anything touching real users, money, or production demands
the disciplined end. **The skill is knowing where to draw the line per task** — the profile sets
the floor, you raise it with the stakes. The one thing that separates the disciplined end from
guessing is *how the output gets verified*.

The trap isn't that the vibe end doesn't work — it often works *surprisingly* well. It's that it
works **on the surface while rotting underneath**: nobody knows why it works, one prompt-fix breaks
three unrelated features, edge cases outrun the tests, and only the original builder can safely
touch it. Vibe coding is how you *discover* what should exist; the disciplined end of that table —
**AI-assisted engineering** — is how it keeps existing. This harness is that discipline, made
portable.

## Two modes: conductor and orchestrator

- **Conductor** — hands-on, step-by-step, watching each change. Best for debugging, exploring
  unfamiliar ground, high-stakes edits.
- **Orchestrator** — define a goal, delegate to sub-agents, review outcomes not keystrokes. Best
  for well-specified features, migrations, parallelizable sweeps.

Move between them by task. The orchestrator mode rewards different skills — precise
specification, decomposition, fast evaluation of output, and system design — which is exactly
what the rest of this harness is built to support.

## The economics (why it's worth the setup)

Vibe coding is cheap to start and expensive to run — you burn tokens iterating on slop because
there's no system. A real harness costs more up front (you're reading this) and far less per task
after, because the output is reliable and you stop re-deriving the same decisions. **High setup,
low running cost — and the crossover comes fast.** A harness that improves a little every time you
use it (see `core/60-evolving-the-harness.md`) compounds from there. And the token bill is only
half the cost of skipping the system — the other half is quality debt that stays invisible until a
customer, a change, or a second engineer arrives, and then comes due all at once.

*Source for the framing in this doc: Google, "The New SDLC With Vibe Coding" (Osmani, Saboo &
Kartakis, May 2026); the field's converging best practices. The mental models are theirs; the rules
in `core/` are earned from real incidents. Full credits and the principle-by-principle source map:
[`16-influences.md`](16-influences.md).*
