# Agentsmith — Influences & Credits (research for the public credits doc)

> Purpose: credit ACCURATELY the named thinkers and bodies of work whose
> principles the "universal AI-agent harness" (Agentsmith) embodies. Every
> claim below is tied to a real, fetched source. No invented quotes. Where
> provenance is fuzzy, it says so. Curate this into the public influences page;
> keep the curated prose lean.
>
> Researched 2026-06-26. Primary source for the "New SDLC" framing is the Google
> whitepaper *"The New SDLC With Vibe Coding."* Its cover + p.2 footer were read
> directly and VERIFIED: authors **Addy Osmani, Shubham Saboo, Sokratis Kartakis**;
> published by **Google**; dated **May 2026** (see source #3). The PDF itself lives
> in the production project's research stash, not this repo.

---

## 1. Andrej Karpathy — terminology + the OS/autonomy framing
**Who:** Founding member of OpenAI, ex-Director of AI at Tesla; coined "Software 2.0," "vibe coding," and popularized "context engineering."

- **"Context engineering" over "prompt engineering."** Karpathy endorsed the term in a June 25, 2025 post: *"+1 for 'context engineering' over 'prompt engineering'. People associate prompts with short task descriptions you'd give an LLM in your day-to-day use. When in every industrial-strength LLM app, context engineering is the delicate art and science of filling the context window with just the right information for the next step."* (Tweet widely quoted; original at <https://x.com/karpathy/status/1937902205765607626> — note: X requires auth to fetch directly; text confirmed via multiple secondary mirrors.)
  → maps to: **"Agent = Model + Harness"** (config, not the model, is the lever) and **static/dynamic context economics**. *Confidence: high* on the quote and authorship; *med* that we can hot-link the primary tweet from a marketing page (consider citing a stable mirror).
- **LLM-as-OS / Software 1.0→2.0→3.0 / "autonomy slider."** From his June 2025 "Software Is Changing (Again)" talk (AI Startup School): the LLM is a new kind of computer/OS (LLM = CPU, context window = RAM/memory), and he advocates an **"autonomy slider"** — keep a human in the loop, dial autonomy up/down rather than chase full autonomy. Talk write-up: <https://www.latent.space/p/s3>.
  → maps to: context window = a scarce memory budget you must manage; hand-off-before-the-window-fills. *Confidence: high* on the talk's existence and themes; *med* on exact wording (cite the talk, not a paraphrase).
- **"Vibe coding."** Coined Feb 2025; the Google whitepaper (source #3, p.11) quotes him directly: *"fully give in to the vibes, embrace exponentials, and forget that the code even exists."* By early 2026 he introduced **"agentic engineering"** for the disciplined end of the spectrum (whitepaper p.12).
  → maps to: Agentsmith sits at the *disciplined* end — profiles add structure/verification, not vibes.

## 2. Addy Osmani — AI-assisted engineering discipline + the 70% problem
**Who:** Director, Google Cloud AI Developer Experience (14+ years at Google, ex-Head of Chrome Developer Experience). Author, *Beyond Vibe Coding* (O'Reilly, 2025) and Substack of the same name.

- **The "70% Problem."** *"AI gets you 70% of the way to a working solution, but that last 30% is where things get tricky"* — the final 30% (debugging, edge cases, security, maintainability) needs real engineering judgment. <https://addyo.substack.com/p/the-70-problem-hard-truths-about>.
  → maps to: **prove-it / verify the whole chain end-to-end**; the harness exists to make humans+agents close that 30% reliably. *Confidence: high.*
- **Vibe coding ≠ AI-assisted engineering.** He draws the line at structure, verification, and accountability. *"Beyond Vibe Coding"* book: <https://beyond.addy.ie/>. Medium framing: <https://medium.com/@addyosmani/vibe-coding-is-not-the-same-as-ai-assisted-engineering-3f81088d5b98>.
  → maps to: atomic commits, verification discipline, review-before-trust. *Confidence: high.*
- Note: Osmani is also lead author of the Google "New SDLC" whitepaper (source #3) — much of source #3's content is his.

## 3. Google whitepaper — "The New SDLC With Vibe Coding" (the closest single match)
**What it actually is (verified by reading the PDF in this repo):** a **Google-published** whitepaper, *"The New SDLC With Vibe Coding — From ad-hoc prompting to Agentic Engineering,"* by **Addy Osmani, Shubham Saboo, and Sokratis Kartakis**, dated **May 2026**, Google logo on the cover, released via Kaggle's "5-Day AI Agents Intensive (Vibe Coding) Course with Google." Kaggle landing: <https://www.kaggle.com/whitepaper-the-new-SDLC-with-vibe-coding>. Osmani's blog companion: <https://addyosmani.com/blog/new-sdlc-vibe-coding/>.
> Accuracy note: credit it as a **Google whitepaper authored by Osmani/Saboo/Kartakis**, NOT an anonymous "Google says." It's the right primary source for the harness framing; the "June-2026" filename in our repo is our label — the document itself says **May 2026**.

Direct quotes/figures from the PDF:
- **"Agent = Model + Harness"** (p.26, set as a display equation). Preceding text: *"The model is one input into a running agent. Everything else, the prompts, the tools, the context policies, the hooks, the sandboxes, the sub-agents, the observability, is the harness: the scaffolding wrapped around the model that lets it actually finish something."* Figure 7 (p.27) labels the split roughly **Model ~10% / Harness ~90%**.
  → maps to: **"Agent = Model + Harness; most failures are configuration failures."** (Near-verbatim alignment.) *Confidence: high.*
- **Static vs dynamic context** (p.16, Figure 4 p.17): *"Static context is always loaded: system instructions, rule files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`), global memory... expensive because every token is present in every interaction. Dynamic context is loaded on demand... efficient because the agent pays the token cost only when the information is needed."* And: *"The best systems treat this boundary as a first-class architectural decision, reviewed and versioned like any other configuration."* Agent **Skills** + **progressive disclosure** are named the key pattern (p.17).
  → maps to: **keep the always-loaded file LEAN; push specialized knowledge into skills/docs/memory loaded on demand.** (Near-verbatim — this whitepaper even names the three filenames Agentsmith assembles.) *Confidence: high.*
- **System-Evolution / feedback loop:** the "continuous quality flywheel" (p.23) — *"evaluate against a benchmark suite, diagnose failures by clustering root causes, optimize the prompts or tools that caused them, verify fixes against a regression suite... Each cycle compounds."* — and the **"factory model"** (pp.24–25): *"the developer's primary output is not code — it's the system that produces code,"* with **feedback loops that route failures back to agents** and **guardrails that constrain agents to safe, predictable behavior.**
  → maps to: **fix the system not the symptom; regression-gate rule changes.** *Confidence: high.*
- **No-secrets discipline:** p.30 gives the canonical hook example — *"The harness runs deterministic hooks (e.g., blocking a commit if the agent tries to push a hard-coded password)."*
  → maps to: **no-secrets discipline as an enforceable guardrail/hook.** *Confidence: high.*

## 4. "Self-Harness: Harnesses That Improve Themselves" (arXiv 2606.09498) — confirmed real
**Who/what:** Hangfan Zhang, Shao Zhang, Kangcong Li, Chen Zhang, Yang Chen, Yiqun Zhang, Lei Bai, Shuyue Hu — **Shanghai Artificial Intelligence Laboratory** (affiliation VERIFIED from the paper's title-page byline, `@pjlab.org.cn`). Submitted **June 8, 2026**, cs.CL. <https://arxiv.org/abs/2606.09498>.
- The agent improves its **own operating harness** without human engineers or a stronger external agent, via a three-stage loop: **Weakness Mining** (find model-specific failure patterns from traces) → **Harness Proposal** (generate *"diverse yet minimal harness modifications tied to these failures"*) → **Proposal Validation** (*"accepts candidate edits only after regression testing"*). Reported held-out gains on Terminal-Bench-2.0 across three model families (e.g., 40.5%→61.9%). VentureBeat write-up: <https://venturebeat.com/orchestration/researchers-introduce-self-harness-a-framework-that-lets-ai-agents-rewrite-their-own-rules-boosting-performance-up-to-60>.
  → maps to: **System-Evolution loop — bounded/minimal edits, regression-gated.** This is the academic articulation of Agentsmith's "fix the system, regression-gate the rule change." *Confidence: high* — it exists, says this, and the Shanghai AI Lab affiliation is verified from the paper's title page.

## 5. Anthropic engineering — the operating-discipline backbone
**Who:** Anthropic (makers of Claude / Claude Code).
- **"Building Effective AI Agents"** (Dec 2024): defines agents as *"LLMs autonomously using tools in a loop,"* and argues for the **simplest pattern that works**, composing from workflow/agent building blocks. <https://www.anthropic.com/engineering/building-effective-agents>.
  → maps to: simplicity-first harness design; don't over-scaffold.
- **"Effective context engineering for AI agents"**: *"Context is a critical but finite resource... with diminishing marginal returns,"* names **"context rot"** (recall degrades as tokens grow), calls context engineering *"the natural progression of prompt engineering,"* and prescribes *"the smallest possible set of high-signal tokens."* <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>.
  → maps to: **keep the always-loaded file LEAN; hand off before the window fills.** *Confidence: high.*
- **Claude Code best practices** (incl. the CLAUDE.md / "keep it tight" guidance): <https://code.claude.com/docs/en/best-practices>.
  → maps to: the operating-agreement file format itself (CLAUDE.md).

## 6. Genuine additional influences (checked — only the ones that map)
- **Simon Willison** — coined **"prompt injection"** (Sept 2022) and sharpened the **vibe coding vs "vibe engineering"** distinction (the latter = staying *"proudly and confidently accountable for the software you produce"*). <https://simonwillison.net/tags/prompt-injection/> · <https://simonw.substack.com/p/vibe-engineering>. → no-secrets/security posture + the "accountable, not vibes" stance. *Confidence: high.*
- **"12-Factor Agents" — Dex Horthy / HumanLayer** — *"own your context window,"* *"own your prompts,"* deterministic code + targeted LLM decisions; the **"dumb zone"** (recall degrades past ~40% context fill). <https://github.com/humanlayer/12-factor-agents> (Factor 3: <https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md>). → static/dynamic context economics; lean window. *Confidence: high.*
- **Chip Huyen — *AI Engineering* (O'Reilly, 2025)** — systematizes context construction, evaluation, and **LLM-as-judge** for foundation-model apps. <https://www.oreilly.com/library/view/ai-engineering/9781098166298/>. → evidence/eval discipline (prove-it). *Confidence: high* on the book; *med* that the harness draws *directly* on it vs. converges with it — credit as a convergent/grounding text, not a claimed lineage.
- **Kent Beck — Test-Driven Development** — *Test-Driven Development: By Example* (Addison-Wesley, 2002); the **red → green → refactor** cycle, "write a failing test first." <https://www.martinfowler.com/bliki/TestDrivenDevelopment.html> · Beck's "Canon TDD": <https://newsletter.kentbeck.com/p/canon-tdd>. → **prove-it / failing-test-first** (Agentsmith's "evidence before assertion"). *Confidence: high.*
- **Chesterton's Fence — G.K. Chesterton** — from *The Thing* (1929), ch. "The Drift from Domesticity": don't remove the fence until you understand why it was put up. Original passage: <https://www.chesterton.org/taking-a-fence-down/>. → **understand-before-you-change.** *Confidence: high* (this is the genuine origin — credit Chesterton, 1929, not a modern blog).

---

## Mapping at a glance (harness principle → primary source)
| Harness principle | Strongest source |
|---|---|
| Agent = Model + Harness (failures are config failures) | Google "New SDLC" whitepaper p.26 (#3); reinforced by Karpathy (#1) |
| Static vs dynamic context; keep loaded file lean | Google whitepaper p.16–17 (#3); Anthropic context-engineering (#5); 12-Factor (#6) |
| Hand off before the window fills | Anthropic "context rot" (#5); Horthy "dumb zone" (#6); Karpathy OS/memory (#1) |
| Prove-it / evidence before assertion | Kent Beck TDD (#6); Addy Osmani 70% problem (#2); Chip Huyen evals (#6) |
| Understand before you change | Chesterton's Fence, 1929 (#6) |
| System-Evolution loop; regression-gate rule changes | Self-Harness arXiv (#4); Google whitepaper "quality flywheel"/"factory model" (#3) |
| No-secrets discipline (enforced by hooks) | Google whitepaper p.30 hook example (#3); Willison prompt-injection (#6) |

## All source URLs (flat list)
- https://x.com/karpathy/status/1937902205765607626
- https://www.latent.space/p/s3
- https://addyo.substack.com/p/the-70-problem-hard-truths-about
- https://beyond.addy.ie/
- https://medium.com/@addyosmani/vibe-coding-is-not-the-same-as-ai-assisted-engineering-3f81088d5b98
- https://addyosmani.com/blog/new-sdlc-vibe-coding/
- https://www.kaggle.com/whitepaper-the-new-SDLC-with-vibe-coding
- https://arxiv.org/abs/2606.09498
- https://venturebeat.com/orchestration/researchers-introduce-self-harness-a-framework-that-lets-ai-agents-rewrite-their-own-rules-boosting-performance-up-to-60
- https://www.anthropic.com/engineering/building-effective-agents
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://code.claude.com/docs/en/best-practices
- https://simonwillison.net/tags/prompt-injection/
- https://simonw.substack.com/p/vibe-engineering
- https://github.com/humanlayer/12-factor-agents
- https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md
- https://www.oreilly.com/library/view/ai-engineering/9781098166298/
- https://www.martinfowler.com/bliki/TestDrivenDevelopment.html
- https://newsletter.kentbeck.com/p/canon-tdd
- https://www.chesterton.org/taking-a-fence-down/
