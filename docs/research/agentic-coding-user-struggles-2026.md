# Agentic coding user struggles and adoption motives

**Research date:** 2026-09-17  
**Status:** Working evidence base for marketing; not a prevalence study  
**Scope:** Technically curious non-developers, experienced developers adopting coding agents, and
users of structured workflows such as BMAD and GSD

## Research question

What makes people look for a coding-agent harness, what do non-developers struggle with after the
first successful prototype, and why do experienced developers adopt specification-driven or
multi-agent workflows?

## Method and evidence labels

The research combined:

- **[Study]** peer-reviewed papers, preprints, and controlled field experiments.
- **[Survey]** large self-report datasets with published methodology.
- **[Community]** Reddit posts and comments. These provide language and hypotheses, not prevalence.
- **[Product]** official repositories and documentation. These establish shipped capabilities, not
  user outcomes.
- **[First-party]** statements supplied by the project lead or published on a related product site.

Searches focused on 2024–2026 material and terms including non-developer, vibe coding, Claude Code,
Codex, specifications, debugging loops, AI productivity, BMAD, GSD, autonomous software factory,
worktrees, and agent harness. Reddit evidence was selected for clear first-hand descriptions rather
than popularity alone. Vendor claims were not treated as independent proof.

The installed deep-research package could not run because its required API credential was not
available. The built-in web-research path was used instead. Queries, source classes, caveats, and
direct links are recorded here for reproducibility.

## Executive finding

AI lowers the barrier to producing a first draft, but it does not distribute the judgment needed to
verify, maintain, secure, and finish software equally. The resulting gap is the clearest opening for
AgentSmith.

The user is not primarily asking for more code generation. They are asking for a teachable system
that keeps the agent inside the task, makes the plan understandable, proves what worked, and leaves
a path back when something goes wrong.

For experienced developers, the same need appears at a different altitude: consistent setup,
repository-local context, verification, continuity across long sessions, and bounded autonomy. The
market's “software factory” aspiration is real, but community evidence also shows resistance to
ceremony, token cost, orchestration complexity, and automation that cannot be trusted.

## What non-developers struggle with

### 1. Permission and gatekeeping

The first trigger can be social rather than technical: a colleague says that a designer, operator,
or founder should not use Claude Code or Codex. Community discussions show both sides of that
tension. Non-developers describe real empowerment, while experienced developers warn that the
ability to generate software is not the same as the ability to judge it.

A 2026 survey of 162 vibe coders gives this tension a useful name: a **perception–action gap**.
Non-developers recognize many of the same risks as professionals, but have less capacity to debug and
verify the output. Non-developers are especially motivated by accessibility; novices emphasize
learning and experimentation. [Study: Fawzy, Tahir, and Blincoe,
“From Prompting to Verification”](https://arxiv.org/abs/2605.24521)

**Implication:** AgentSmith should reject both extremes. It should not say “anyone can ship anything
without expertise,” and it should not say “learn software engineering before you begin.” The useful
promise is selective literacy: learn enough to understand the plan, the risk, and the evidence for
the task in front of you.

### 2. The difficulty moves rather than disappears

A self-described non-developer summarized the transition from “how do I code this?” to questions
such as whether the AI is correct, whether they understand enough to notice errors, and when to stop
fixing and ship. [Community:
“AI finally made me try building software for real”](https://www.reddit.com/r/vibecoding/comments/1vqx6mi/im_not_a_developer_ai_finally_made_me_try/)

Another non-developer built a useful internal tool, then became lost as the repository accumulated
hooks, harnesses, refactors, and tens of thousands of lines. The user wanted relevant learning and a
stopping rule, not a computer-science curriculum. [Community:
“I’m scared that I have no idea what I’m doing anymore”](https://www.reddit.com/r/ClaudeAI/comments/1uuf59z/im_a_vibe_coder_and_im_scared_that_i_have_no_idea/)

**Implication:** “Beginner-friendly” must include a controlled increase in explanation as the project
grows. A quick-start alone is insufficient.

### 3. Agents exceed the requested scope

Users report agents refactoring, adding features, or changing unrelated areas after being asked a
narrow question. A 2026 local-agent discussion described the reliable loop as small task → tests →
diff review → correction, because broader freedom led to random changes and plausible-looking broken
code. [Community:
“Local coding agents are good now, but only if you babysit them”](https://www.reddit.com/r/LocalLLaMA/comments/1u6mmuu/local_coding_agents_are_good_now_but_only_if_you/)

**Implication:** explicit scope, diff visibility, rollback, and a stopping condition are activation
features, not advanced governance features.

### 4. One-shot success becomes a repair loop

The most common broad survey frustration is not total failure. It is output that is nearly correct.
In the 2025 Stack Overflow Developer Survey, 66% of respondents selecting AI frustrations reported
solutions that were “almost right, but not quite,” and 45% reported that debugging AI-generated code
was more time-consuming. More respondents distrusted AI accuracy (46%) than trusted it (33%).
[Survey: Stack Overflow 2025, AI](https://survey.stackoverflow.co/2025/ai)

Community posts describe the same pattern as repeated prompts, regressions, and fixes that create new
work. This is the lived version of “vibe code once, bug-fix forever.”

**Implication:** do not promise frictionless speed. Show the difference between a fast draft and a
verified result.

### 5. Missing specifications produce inconsistent output

A Claude Code user reported months of inconsistent results until adopting a stable sequence: product
requirements document (PRD) → design → task breakdown → implementation, backed by reusable skills.
[Community:
“Took me months to get consistent results”](https://www.reddit.com/r/ClaudeAI/comments/1pup0k9/took_me_months_to_get_consistent_results_from/)

A heavily discussed workflow thread converged on reading and questioning the plan, breaking work into
small units, watching tests fail before implementation, and keeping reversible Git checkpoints. A
self-described non-developer specifically asked for a plain-English plan that was not dumbed down.
[Community:
“Here are the rules I follow”](https://www.reddit.com/r/ClaudeAI/comments/1tj2i90/im_a_software_engineer_with_a_decade_of/)

**Implication:** the first AgentSmith success should begin with a small, reviewable specification—not
with an impressive code-generation demo.

### 6. Visual success can hide data and correctness failures

Non-developers often validate by looking at the interface. That fails for data transformations,
security boundaries, background jobs, and edge cases. One developer described a non-coding partner's
data-crunching tool as particularly hard to assess because little of the result was visible in the
interface. [Community:
“Is it just me?”](https://www.reddit.com/r/ClaudeCode/comments/1t54zdn/is_it_just_me/)

**Implication:** AgentSmith must explain why tests and end-to-end checks are different from “the page
looks right,” using concrete examples rather than jargon.

### 7. Security knowledge does not arrive with code generation

A 2026 preprint analyzing deployed vibe-coded applications reported recurring placeholder logic,
unfiltered input, secret exposure, and failures linked to memory, local optimization, and missing
security knowledge. It reported at least one vulnerability in 91% of its deployed-app sample. This is
one preprint and its sample should not be generalized to all AI-generated software, but it strongly
supports explicit security gates. [Study:
“Understanding the (In)Security of Vibe-Coded Applications”](https://arxiv.org/abs/2606.23130)

USENIX reported package hallucinations across all 16 models in a 2024-era test set, averaging 19.6%,
with commercial models performing better than open models. The models are dated, but the study shows
why dependency verification should be deterministic rather than entrusted to confidence.
[Study: USENIX, “Package Hallucinations”](https://www.usenix.org/publications/loginonline/we-have-package-you-comprehensive-analysis-package-hallucinations-code)

**Implication:** beginner onboarding needs a clear boundary around production, customer data,
authentication, payments, and deployment. “Friendly” cannot mean hiding consequential risk.

## Is AI-assisted engineering slower than it looks?

The defensible answer is **sometimes, depending on the task, user, tool generation, and quality
standard**. The evidence does not support a universal “AI is slower” or “AI makes development ten
times faster” claim.

### Evidence for slower or misleadingly fast work

- A randomized controlled trial (RCT) of 16 experienced maintainers completing 246 tasks in mature
  repositories found early-2025 tools increased completion time by 19%, even though participants
  believed afterward that they were 20% faster. The setting—experts in familiar, mature projects and
  early-2025 models—limits generalization. [METR study](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)
- METR's 2026 follow-up said newer data suggested more speed-up, but selection effects and concurrent
  agent use made the estimate unreliable. METR explicitly changed its experiment design rather than
  presenting the noisy number as a conclusion. [METR 2026 update](https://metr.org/blog/2026-02-24-uplift-update/)
- SlopCodeBench evaluated iterative extension rather than one-shot completion. Across 15 agents, no
  agent solved a full evolving problem; structural erosion rose in 77% of trajectories and verbosity
  in 75.5%. This is a benchmark preprint, not a production field study. [SlopCodeBench](https://arxiv.org/abs/2603.24755)

### Evidence for faster work

- Three company field experiments covering 4,867 developers found a combined 26.08% increase in
  completed tasks with an AI coding assistant. Less-experienced developers adopted it more and saw
  larger gains. The outcome measured completed tasks, not long-term maintainability.
  [Management Science](https://pubsonline.informs.org/doi/10.1287/mnsc.2025.00535)
- In Stack Overflow's 2025 survey, 52% of respondents said AI tools or agents improved their
  productivity. This is self-report evidence and coexists with high distrust and debugging costs.
  [Stack Overflow 2025](https://survey.stackoverflow.co/2025/ai)

### Recommended language

Avoid: “Agentic development is slower than it looks.” It is memorable but too absolute.

Prefer one of these hypotheses for later message testing:

1. **AI makes the first draft fast. Reliable delivery still takes engineering.**
2. **Getting something to run is faster. Getting something you can trust still takes a process.**
3. **AI shortens the typing. It does not remove planning, testing, or responsibility.**
4. **The demo is fast. The last 20% is still where software becomes dependable.**

The second is the clearest for non-native English readers. The first is the strongest compact product
line. Neither should be presented as a measured universal law.

## What should happen in the first 30 minutes?

### Decision: prepared sandbox first, real repository second

The best-supported onboarding path is neither a blank new project nor an immediate change to the
user's valuable repository. Start with a **small, disposable but real template repository**. Let the
user complete one full AgentSmith loop there, then offer an “apply this to your project” path.

This is like learning to drive in a controlled car park. The controls and consequences are real, but
the first mistake does not damage the vehicle the learner depends on.

The recommended first loop is:

1. **Orient and specify (0–5 minutes):** state one outcome in plain English and write three observable
   acceptance checks.
2. **Predict and run (5–9 minutes):** inspect the prepared behavior, predict the result, and run the
   baseline check.
3. **Make one bounded change (9–18 minutes):** review the agent's plan and allow one small bug fix or
   improvement.
4. **Inspect and explain (18–25 minutes):** review the changed files and explain the result in plain
   language. The code diff is an input, not the only proof.
5. **Verify and recover (25–29 minutes):** run an automated check and exercise the visible result;
   demonstrate a safe revert or rollback.
6. **Transfer (29–30 minutes):** name the first suitable task in the user's own project and the risks
   to check before starting it.

### Why this path is stronger

- GitHub Skills recommends a template repository, an easy first action, three to five steps, and
  automated feedback. Its guidance says learners tend to drop out after 30–45 minutes and can take
  roughly four times as long as an expert. [Product: GitHub Skills
  Quickstart](https://skills.github.com/quickstart)
- Current developer-tool onboarding follows the same basic pattern. Cursor permits a sample or
  existing project and ends with tests; Replit uses a bounded new application, structured prompt,
  plan, and preview checklist; GitHub Copilot uses a small task isolated in a pull request and then
  review. These establish product patterns, not independent outcome evidence.
  [Cursor quickstart](https://docs.cursor.com/en/get-started/quickstart) ·
  [Replit tutorial](https://docs.replit.com/build/your-first-app) ·
  [GitHub Copilot coding agent](https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/overview)
- PRIMM—Predict, Run, Investigate, Modify, Make—starts beginners from a prepared program and gradually
  transfers ownership. A 2019 study across 13 schools reported improved attainment, while later
  worked-example and Use–Modify–Create studies support scaffolding before open creation. These
  studies concern programming education rather than coding-agent onboarding, so the transfer is an
  inference. [Study: PRIMM](https://doi.org/10.1080/08993408.2019.1608781) ·
  [Study: subgoal-labelled worked examples](https://doi.org/10.1186/s40594-020-00222-7) ·
  [Study: Use–Modify–Create](https://doi.org/10.1016/j.lindif.2021.101983)
- A study of non-programmers assessing AI-generated data-analysis code found that business users
  could not reliably identify important flaws. This argues against making “read the diff” the only
  beginner proof. The first loop should combine a visible outcome, executable checks, and an
  explicit risk boundary. [Study: non-programmers assessing AI-generated
  code](https://arxiv.org/abs/2508.06484)
- Claude Code and Codex documentation both reinforce bounded access and isolation. A disposable
  template, dedicated branch, or worktree teaches those boundaries before a live project is at
  risk. [Product: Claude Code security](https://docs.anthropic.com/en/docs/claude-code/security) ·
  [Product: Codex sandboxing](https://learn.chatgpt.com/docs/sandboxing)

### Why not the other two options first?

**A blank new project** introduces product definition, architecture, framework, environment, and
deployment choices at the same time. It creates an impressive generation demo but weak evidence that
the user learned scope, verification, or recovery.

**The user's existing project** is more relevant, but its unknown dependencies, missing checks,
secrets, and emotional value make it an inconsistent first lesson. It should be the immediate second
stage, once the user has completed one safe loop.

### Evidence limit and product test

No identified study directly compares these three choices in a 30-minute coding-agent onboarding
session. The recommendation triangulates learning research, current onboarding patterns, and safety
guidance. Test it with at least three first-time users. Measure completion, comprehension, recovery,
and whether they can correctly scope the next task in their own project—not whether they merely say
the tutorial felt easy.

## Why users adopt BMAD, GSD, and similar workflows

### Shipped capability

- BMAD progressively builds context through discovery, planning, specification, architecture, and
  implementation artifacts. Its current planning guidance explicitly distinguishes quick
  specifications from fuller planning. [Product: BMAD planning paths](https://docs.bmad-method.org/cs/plan/choose-a-planning-path/)
- GSD describes a requirements → research → plans → execution → verification pipeline, persistent
  state, specialized fresh-context agents, checkpoints, and context budgets.
  [Product: GSD architecture](https://github.com/gsd-build/get-shit-done/blob/main/docs/ARCHITECTURE.md)
- Archon exposes typed workflows, approval gates, isolated worktrees, resumability, and pull-request
  automation. [Product: Archon](https://github.com/coleam00/Archon)
- Superpowers packages planning, test-driven development, subagent execution, and review gates.
  [Product: Superpowers](https://github.com/obra/superpowers)

### User motivations

People adopt these systems because they want:

1. A specification that survives beyond one chat.
2. Smaller tasks that an agent can complete and a human can understand.
3. Consistent planning, testing, review, and handoff behavior.
4. Fresh context without losing project decisions.
5. Less time babysitting repetitive implementation and continuous integration (CI).
6. Parallel work without agents overwriting one another.
7. The longer-term dream of a software factory that converts approved intent into reviewed changes.

The software-factory aspiration is explicit in community projects that promise plan → code → review
→ pull request while the user sleeps. [Community:
BMAD Autonomous Development](https://www.reddit.com/r/BMAD_Method/comments/1scy3jf/bad_bmad_autonomous_development_a_fully/)

### Why users reject or slim these systems down

The same community reports planning overhead, large context loads, token cost, repetitive artifacts,
worktree friction, and “enterprise theatre.” One BMAD user described the full flow as valuable for
clarity but too expensive during execution, and proposed full planning followed by a lean build mode.
Another said the slower pace was worthwhile because it reduced rework and ended closer to the intended
result. [Community:
“Burning too many tokens with BMAD full flow”](https://www.reddit.com/r/BMAD_Method/comments/1ruregn/burning_too_many_tokens_with_bmad_full_flow/)

**Implication for AgentSmith:** progressive rigor is the product advantage. Keep a small universal
core; load specialized guidance when needed; make the next action visible; and scale from an attended
task to bounded parallel work. Do not copy a large role-playing organization into every repository.

## Independent resonance with AgentSmith's existing citations

The existing AgentSmith source base is not an isolated internal narrative:

- An independent review of Google's *The New SDLC With Vibe Coding* agreed that work moves from raw
  typing toward intent, context, supervision, review, validation, and operational judgment, while
  criticizing the whitepaper for presenting a cleaner picture than day-to-day reality.
  [The Lazy SRE review](https://thelazysre.com/posts/i-read-googles-the-new-sdlc/)
- Community members have adapted OpenAI's harness-engineering article into repository skills and
  playbooks, while also warning that such playbooks must be tailored and reviewed rather than copied
  once. [Community:
  repository playbook adaptation](https://www.reddit.com/r/OpenaiCodex/comments/1twvsmo/i_turned_openai_codex_engineers_public_talks_and/)
- A source-code study and a separate survey now treat harness engineering as an emerging research
  topic rather than a single-vendor phrase. [Source-code study](https://arxiv.org/abs/2609.00006) ·
  [survey](https://openreview.net/pdf?id=eONq7FdiHa)

These references support the category direction **agent-native software development lifecycle
(SDLC) harness**. They do not prove that AgentSmith itself improves outcomes; that requires product
and user evidence.

## Available AgentSmith proof and its limits

### Repository-owned proof

AgentSmith can currently prove installation behavior, canonical instruction assembly, work-type
profiles, evidence-based verification, safe update and rollback, native-client evaluations, and
bounded maker/checker runs through its repository checks.

### First-party operating proof

- The project lead reports using the framework in more than ten PromptPartner customer projects to
  improve delivery quality relative to ad-hoc vibe coding. This is useful discovery evidence, but the
  count should not become a public outcome claim until engagements, permission, and the meaning of
  “used” and “higher quality” are documented.
- The project lead reports using the approach for more than eight months while developing AI Admin
  Panel. The public site shows a substantial product in private beta, launched at CloudFest 2026,
  with a multi-layer architecture and extensive listed tests. The duration and causal contribution of
  AgentSmith remain first-party statements. [AI Admin Panel](https://aiadminpanel.com/)

The strongest next proof would be one traceable case study: initial state, specification, AgentSmith
configuration, change history, verification evidence, result, and what would likely have failed
without the harness.

## Channel implications

- **Reddit:** primary listening and conversation channel. Use it to learn language and answer real
  workflow questions. Do not mine isolated posts into fake statistics or arrive with promotional
  claims.
- **GitHub:** primary proof and conversion surface. Every claim should lead to a runnable example,
  check, change history, or concise documentation page.
- **LinkedIn:** secondary distribution channel for case evidence, diagrams, and lessons. Treat its
  autonomy and productivity claims as leads to verify, not evidence to repeat.
- **Technical communities and workshops:** promising for observing first use. One recorded beginner
  session will teach more about onboarding than a broad engagement campaign.

## Product and messaging hypotheses to test

1. **Control you can learn** is stronger than “autonomous software factory” for the primary path.
2. The first success should be a small specification and verified change, not a generated app.
3. AgentSmith should teach the minimum useful mental model at each consequential step.
4. Experienced developers should see the same product through an inspectable fast path with no
   beginner ceremony.
5. The autonomy story should be an adjustable ladder: attended task → bounded run → parallel work →
   recurring delivery only where deterministic gates exist.
6. “Agent-native SDLC harness” is defensible; “complete autonomous SDLC platform” is premature.

## Sources to revisit before publication

The following evidence is especially time-sensitive and should be rechecked before a launch:

- model-specific or tool-specific community complaints;
- BMAD, GSD, Archon, and Superpowers capability comparisons;
- security prevalence estimates from preprints;
- productivity estimates as agentic tools and measurement methods change;
- AI Admin Panel release status and any public customer evidence.
