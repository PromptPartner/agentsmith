# Principles & influences

This harness didn't invent its ideas — it earns them from real incidents on a production project,
and it stands on a body of public work by people who thought hard about how to build *with* AI
agents rather than just prompt them. This page credits that work and maps each idea to the part of
the harness it shows up in. If a rule here looks obvious, it's because someone below paid for the
lesson first.

The single closest match to this harness's framing is Google's whitepaper **"The New SDLC With
Vibe Coding — From ad-hoc prompting to Agentic Engineering"** (Addy Osmani, Shubham Saboo &
Sokratis Kartakis, May 2026). Where this page quotes "the model is ~10%, the harness is ~90%" or
"static vs dynamic context," that's their framing — the rules in `core/` are our earned application
of it.

## At a glance — harness principle → who said it first

| Harness principle | Strongest source |
|---|---|
| **Agent = Model + Harness** — most failures are *configuration* failures | Google, *The New SDLC With Vibe Coding* (Osmani/Saboo/Kartakis, 2026); reinforced by Karpathy |
| **Static vs dynamic context** — keep the always-loaded file lean | Google *New SDLC* whitepaper; Anthropic, *Effective context engineering*; 12-Factor Agents |
| **Hand off before the window fills** — recall degrades as tokens grow | Anthropic ("context rot"); Dex Horthy, 12-Factor Agents ("the dumb zone"); Karpathy (LLM-as-OS) |
| **Prove it** — evidence before assertion, failing test first | Kent Beck (TDD); Addy Osmani (the "70% problem"); Chip Huyen (evals) |
| **Understand before you change** | G.K. Chesterton — Chesterton's Fence, 1929 |
| **Fix the system, not the symptom** — regression-gate every rule change | *Self-Harness* (Shanghai AI Lab, 2026); Google whitepaper's "quality flywheel" / "factory model" |
| **No secrets, ever** — enforced by a deterministic hook | Google whitepaper (the canonical commit-blocking hook example); Simon Willison (prompt injection) |

## The people and the work

**Andrej Karpathy** — coined "Software 2.0" and "vibe coding," and popularized **context
engineering** over prompt engineering: *"the delicate art and science of filling the context window
with just the right information for the next step."* His **LLM-as-OS** framing (context window = a
scarce memory budget) and the **"autonomy slider"** (keep a human in the loop; dial autonomy up and
down rather than chase full autonomy) sit underneath this harness's conductor/orchestrator modes and
its hand-off-early discipline.
→ [Software Is Changing (Again)](https://www.latent.space/p/s3) · [the context-engineering post](https://x.com/karpathy/status/1937902205765607626)

**Addy Osmani** (Director, Google Cloud AI Developer Experience) — the **"70% Problem"**: *"AI gets
you 70% of the way to a working solution, but that last 30% is where things get tricky."* That last
30% — edge cases, security, maintainability — is exactly what `prove-it` and end-to-end verification
exist to close. He also draws the line we build on: AI-assisted engineering is *not* the same as vibe
coding — it has structure, verification, and accountability. Lead author of the *New SDLC* whitepaper
below.
→ [The 70% problem](https://addyo.substack.com/p/the-70-problem-hard-truths-about) · [Beyond Vibe Coding](https://beyond.addy.ie/)

**Google — *The New SDLC With Vibe Coding*** (Osmani, Saboo & Kartakis, May 2026) — the source of the
harness's spine: **"Agent = Model + Harness"** (the model is one input; the prompts, tools, context
policies, hooks, sub-agents, and observability are the harness), the **~10% model / ~90% harness**
split, **static vs dynamic context** as a first-class architectural decision (it even names the three
rule files we assemble — `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`), the **"quality flywheel"** and
**"factory model"** ("the developer's primary output is not code — it's the system that produces
code"), and the canonical **no-secrets hook** ("blocking a commit if the agent tries to push a
hard-coded password").
→ [whitepaper](https://www.kaggle.com/whitepaper-the-new-SDLC-with-vibe-coding) · [author's companion post](https://addyosmani.com/blog/new-sdlc-vibe-coding/)

**Anthropic** (makers of Claude / Claude Code) — the operating-discipline backbone. *Building
Effective Agents* argues for **the simplest pattern that works** (don't over-scaffold). *Effective
context engineering* names **"context rot"** (recall degrades as the window fills) and prescribes
*"the smallest possible set of high-signal tokens"* — the direct justification for keeping `core/`
lean and handing off early. The CLAUDE.md format and "keep it tight" guidance come from Claude Code
best practices.
→ [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) · [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) · [Claude Code best practices](https://code.claude.com/docs/en/best-practices)

**Dex Horthy — 12-Factor Agents** — *"own your context window," "own your prompts,"* deterministic
code with targeted LLM decisions, and **"the dumb zone"** (recall falls off past roughly 40% context
fill). This is the engineering articulation of the static/dynamic split and why we hand off before
the window is full.
→ [12-Factor Agents](https://github.com/humanlayer/12-factor-agents)

**Simon Willison** — coined **"prompt injection"** (2022) and sharpened the **vibe coding vs vibe
engineering** distinction: the latter means staying *"proudly and confidently accountable for the
software you produce."* That's the harness's security posture (no-secrets, treat untrusted input as
hostile) and its "accountable, not vibes" stance.
→ [prompt injection](https://simonwillison.net/tags/prompt-injection/) · [vibe engineering](https://simonw.substack.com/p/vibe-engineering)

**Kent Beck — Test-Driven Development** — red → green → refactor, *write the failing test first.*
This is `prove-it` in its original form: no failing test demonstrating the bug means no proof, so no
fix ships.
→ [TDD](https://www.martinfowler.com/bliki/TestDrivenDevelopment.html) · [Canon TDD](https://newsletter.kentbeck.com/p/canon-tdd)

**G.K. Chesterton — Chesterton's Fence** (*The Thing*, 1929) — don't take the fence down until you
understand why it was put up. Verbatim our `understand-before-you-change` rule.
→ [the original passage](https://www.chesterton.org/taking-a-fence-down/)

**Self-Harness: Harnesses That Improve Themselves** (Shanghai AI Laboratory, 2026) — the academic
form of `core/60-evolving-the-harness.md`: an agent improves its own harness through a loop of
**find the failure pattern → propose a minimal, targeted edit → accept it only after regression
testing.** Bounded edits, regression-gated. That's exactly "fix the system, not the symptom."
→ [arXiv:2606.09498](https://arxiv.org/abs/2606.09498)

**Chip Huyen — *AI Engineering*** (O'Reilly, 2025) — systematizes context construction, evaluation,
and **LLM-as-judge** for foundation-model apps; a grounding text for the evidence/eval discipline the
harness leans on (the `code-review` + `codex` review gates are this idea in practice).
→ [AI Engineering](https://www.oreilly.com/library/view/ai-engineering/9781098166298/)

**Cobus Greyling — *Loop Engineering*** (MIT, 2026) — the source for `profiles/autonomous-loops.md`.
Its framing draws the line this harness sits on: **`Harness = single session setup` / `Loop = harness
+ schedule + state + verification chain`** — Agentsmith is the harness, the profile governs the layer
above it. We adapted the methodology only (the L1→L3 autonomy ladder, the REJECT-by-default
maker/checker split, attempt caps, budget + kill switch, the path denylist, state-as-spine) and took
none of its tooling — the scheduler and subagent primitives are already native (R10). The sharpest
idea, from its own honest post-mortem: **a checker is worthless unless it measures something the
maker structurally cannot fake** — an LLM second opinion cannot catch an overfit backtest, because
the backtest *is* the overfit artifact.
→ [loop-engineering](https://github.com/cobusgreyling/loop-engineering) · [the essay](https://cobusgreyling.substack.com/p/loop-engineering)

## Complementary work (not influences)

These shaped nothing in `core/` — they sit *alongside* it, at a different layer.

**[pm-skills](https://github.com/phuryn/pm-skills) — by `phuryn`.** A marketplace of 100+
product-management skills, commands, and plugins for agents — discovery → strategy → execution →
launch → growth. Where this harness is about *how* to build so AI-written software keeps existing,
pm-skills is about *what* to build and why: the upstream product decisions that determine whether a
thing is worth maintaining at all. It targets the same runtimes (Claude Code, Codex CLI), so the
two compose cleanly on one machine.
→ [github.com/phuryn/pm-skills](https://github.com/phuryn/pm-skills)

---

*The mental models here are theirs; the specific rules in `core/` are earned from real incidents on
a production project. For the longer "why," see [`01-harness-philosophy.md`](01-harness-philosophy.md).*

*The receipts behind this page — exact page numbers, source URLs, and honest confidence ratings for
each attribution (including where the harness merely converges with a source rather than draws
from it) — are in [`research/agentsmith-influences-and-credits.md`](research/agentsmith-influences-and-credits.md).
This page is the curated version; that one is the working notes it was distilled from.*
