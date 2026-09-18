# Content pillars: AgentSmith

**Status:** Step 7 confirmed by the operator on 2026-09-17  
**Date:** 2026-09-17  
**Positioning:** The portable control-and-evidence layer for AI-assisted work

## Design criteria

The pillars must do more than divide a content calendar. Together they need to:

- challenge the belief that a capable model is sufficient on its own;
- lead with verification, followed by scope control and continuity;
- work for first-time builders and experienced developers without splitting the product in two;
- support awareness, consideration, activation, and long-term use;
- make room for bounded autonomy without turning AgentSmith into “software factory” marketing;
- provide useful open-source material before asking for anything; and
- create credible PromptPartner interest through evidence, not a separate AgentSmith service pitch.

The five options below are strategic systems. The pillar names are internal organizing labels, not
automatically website navigation or campaign headlines.

## Option 1: Proof — Control — Continuity

| Pillar | Definition | Themes and content |
|---|---|---|
| **Proof** | Replace “the agent says it works” with evidence appropriate to the real outcome | Almost-right output; tests versus end-to-end exercise versus judgment; adaptive verification; CI that fits the repository; security boundaries; evidence receipts; before/after demonstrations; research and case evidence |
| **Control** | Keep the work aligned with the requested outcome and make consequential change visible and reversible | Small specifications; scope boundaries; plans before changes; permissions; diff inspection; Git checkpoints in plain language; reversible installation; ownership; recovery; when to stop or seek expert review |
| **Continuity** | Preserve intent and quality across sessions, agents, projects, and increasing levels of autonomy | Context loss; specifications and handoffs; decision memory; profiles; portable working agreements; system feedback; attended → bounded autonomous work; isolated worktrees; future AI Admin Panel bridge |

**Strategic rationale:** This option follows the operator's confirmed pain order. It explains why the
harness exists before describing its machinery. It also creates a natural progression: prove one
result, control how work changes, then continue and scale the process safely.

**Ideal-customer-profile alignment:** Proof addresses the biggest uncertainty for both audiences.
Control helps first-time builders avoid unrequested changes and gives experts inspectable governance.
Continuity matters once a real project lasts longer than one impressive session.

**Buying motivations:** Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene; Save Time; Avoid
Effort.

**EPIC alignment:**

- **Entertaining:** concrete tensions such as “it runs” versus “it is proven.”
- **Personalized:** separate examples can address a designer's internal tool and a developer's
  multi-repository workflow without changing the pillars.
- **Irrefutable:** Proof makes evidence a permanent content requirement.
- **Clear:** each pillar names one customer problem in ordinary language.

**Risk:** “Continuity” is less immediately vivid than Proof or Control. Customer-facing copy should
translate it into “continue without starting over.”

## Option 2: Specify — Verify — Advance

| Pillar | Definition | Themes and content |
|---|---|---|
| **Specify** | Decide what success means before the agent changes anything | Problem framing; acceptance checks; repository grilling; short specifications; risk and non-goals; plans |
| **Verify** | Test the deterministic parts and evaluate the judgment-dependent parts | Failing checks; full-chain exercises; CI design; security review; evidence receipts; independent checking |
| **Advance** | Move from one attended task to durable and increasingly autonomous delivery | Handoffs; feedback loops; profile maturity; worktrees; maker/checker; multi-agent roadmap; hosting bridge |

**Strategic rationale:** This is the cleanest description of the operating sequence. It is useful for
tutorials, onboarding, and product education.

**Ideal-customer-profile alignment:** Strong for first-time builders who need a step-by-step path;
credible for developers because it mirrors disciplined engineering.

**Buying motivations:** Get Comfort; Achieve Cleanliness/Hygiene; Save Time; Increase Social Status.

**EPIC alignment:** Very clear and teachable. Less personalized around the emotional trigger and less
distinctive because many development methods use a similar sequence.

**Risk:** It can make AgentSmith look like another methodology and understate reversible ownership,
scope control, and cross-work-type portability.

## Option 3: Learn — Build — Own

| Pillar | Definition | Themes and content |
|---|---|---|
| **Learn** | Teach the smallest useful mental model at the moment it affects the result | Plain-English specifications, Git concepts, verification, permissions, risk, and escalation |
| **Build** | Use capable agents to create real software and other professional work | Guided sandbox; practical tasks; agent comparisons; profiles; skills; PromptPartner delivery examples |
| **Own** | Keep control of the output, context, configuration, and future direction | Local-first operation; open source; reversible setup; durable artifacts; portability; handoff; autonomy |

**Strategic rationale:** This option has the best emotional fit for non-developers who reject both
gatekeeping and irresponsible vibe coding. “Own” also connects well to PromptPartner's existing
service language.

**Ideal-customer-profile alignment:** Strong for first-time builders, students, and future community
education. Moderate for experienced developers who may perceive “Learn” as introductory content.

**Buying motivations:** Get Comfort; Gain Praise/Love; Increase Social Status; Avoid Effort; Make
Money.

**EPIC alignment:** Personal and potentially memorable. Irrefutability is weaker because proof is not
structural to the pillar system.

**Risk:** It pulls the launch toward education and aspiration before the professional proof path is
established.

## Option 4: Rules — Evidence — Autonomy

| Pillar | Definition | Themes and content |
|---|---|---|
| **Rules** | Give agents an explicit, project-owned operating agreement | Core rules; profiles; permissions; scope; compatibility; central versus project installation |
| **Evidence** | Make completion depend on checks rather than confidence | Verification; end-to-end exercises; evaluation; receipts; security; case studies |
| **Autonomy** | Delegate larger units of work inside finite authority and independent review | Maker/checker; worktrees; parallelism; collision management; stop/resume; orchestration boundaries |

**Strategic rationale:** This option maps directly to the system architecture and makes the advanced
destination visible.

**Ideal-customer-profile alignment:** Strong for experienced developers, technical founders, and
consultancies. Weaker for a first-time builder who does not yet know why rules, evidence, or worktrees
matter.

**Buying motivations:** Achieve Cleanliness/Hygiene; Get Comfort; Save Time; Increase Social Status.

**EPIC alignment:** Irrefutable and specific when backed by repository demonstrations. Less clear and
personal for newcomers; “Autonomy” may attract the wrong software-factory expectation.

**Risk:** It starts from AgentSmith's components rather than the user's lived problem.

## Option 5: Start — Recover — Scale

| Pillar | Definition | Themes and content |
|---|---|---|
| **Start** | Begin one real task with safe defaults and a clear definition of success | Sandbox onboarding; first specification; profile choice; cautious permissions; first verified change |
| **Recover** | Bring an almost-right or growing AI-built project back under control | Repository diagnosis; scope reset; adaptive verification; documentation; checkpoints; repair-loop stories |
| **Scale** | Reuse the discipline across projects, agents, teams, and autonomous work | Portable setup; profiles; updates; handoffs; worktrees; multi-agent direction; PromptPartner and AI Admin Panel bridge |

**Strategic rationale:** This option organizes content around three customer situations and creates
obvious calls to action.

**Ideal-customer-profile alignment:** Strong across the journey and especially useful for landing
pages or solution navigation.

**Buying motivations:** Escape Pain; Save Time; Avoid Effort; Make Money; Get Comfort.

**EPIC alignment:** Highly personalized and concrete. Proof becomes one theme among many instead of
the non-negotiable standard across all content.

**Risk:** “Scale” can imply team, hosting, and orchestration capabilities beyond the current product.

## Comparison matrix

Scores use a five-point scale. The total is out of 35. These scores are strategic judgments to make
the recommendation inspectable; they are not market-test results.

| Criterion | Proof–Control–Continuity | Specify–Verify–Advance | Learn–Build–Own | Rules–Evidence–Autonomy | Start–Recover–Scale |
|---|---:|---:|---:|---:|---:|
| Value Proposition Canvas alignment | 5 | 4 | 4 | 4 | 4 |
| Positioning strength | 5 | 4 | 3 | 4 | 3 |
| Content range | 5 | 4 | 4 | 4 | 5 |
| Customer-journey coverage | 4 | 4 | 4 | 3 | 5 |
| Competitive differentiation | 5 | 3 | 3 | 4 | 3 |
| EPIC framework fit | 5 | 4 | 4 | 3 | 4 |
| Buying-motivation coverage | 5 | 4 | 4 | 4 | 5 |
| **Total** | **34** | **27** | **26** | **26** | **29** |

## Recommendation

### Choose Option 1: Proof — Control — Continuity

This system is closest to what customers actually notice. It begins with the confirmed lead pain—can
I prove the result?—then addresses unwanted scope and the need to resume or expand the work. It also
prevents the content strategy from becoming a product-manual index. Skills, profiles, worktrees,
receipts, and installers appear only when they support one of the three customer outcomes.

The pillars are broad enough for years of content but strict enough to prevent drift. Every proposed
piece must answer at least one of these questions:

1. **Proof:** How do I know the result works where it matters?
2. **Control:** How do I keep the agent and the system inside the intended boundary?
3. **Continuity:** How do I continue tomorrow, in another agent, or with more autonomy without
   rebuilding the work from memory?

### Customer-facing translations

The internal nouns are useful for planning. Public copy should translate them into direct promises:

| Internal pillar | Customer-facing line | Short explanation |
|---|---|---|
| Proof | **Prove it works.** | Check the real outcome, not only the agent's confidence. |
| Control | **Keep it in scope.** | See the plan, the boundaries, the changes, and the recovery path. |
| Continuity | **Continue without starting over.** | Preserve the decisions, evidence, and next step across sessions and agents. |

Autonomy is a cross-pillar maturity story rather than a fourth pillar:

- **Proof:** an independent checker needs evidence it can trust.
- **Control:** the run needs finite authority, attempts, resources, and interruption.
- **Continuity:** durable state and isolated work make stop, resume, and parallel progress possible.

## Content architecture

### Recommended launch weighting

| Pillar | Share | Why |
|---|---:|---|
| Proof | 40% | Lead pain, strongest point of contrast, and the path to credible marketing |
| Control | 35% | Names the unrequested-change and repair-loop problem that creates urgency |
| Continuity | 25% | Differentiates long-term use and introduces progressive autonomy after trust exists |

The weighting should change with evidence. If user interviews or GitHub behavior show stronger demand
for continuity or autonomy, adjust the mix without changing the pillar system immediately.

### Content by buying stage

| Stage | Proof | Control | Continuity |
|---|---|---|---|
| Awareness | “It runs” versus “it is proven”; almost-right output; verification stories | Agent went beyond the request; why a short specification matters | Why long chats lose the plot |
| Consideration | Verification model; adaptive checks; evidence demo | Operating agreement; permissions; reversible setup; profile selection | Handoffs; portable rules; project memory; model switching |
| Activation | Complete one sandbox loop and inspect both visible and automated evidence | Define scope, approve plan, inspect diff, demonstrate recovery | Save the decision and next step; transfer to the real repository |
| Retention | Improve the repository's checks as the product grows | Evolve rules from incidents and keep ownership clear | Resume, update, delegate, and use bounded autonomous runs |
| Service bridge | Evidence-backed AI Admin Panel and anonymous customer cases | Governance, security, and architecture needs larger than a local harness | PromptPartner delivery and ownership transfer; future hosting bridge |

### Repeatable content formats

| Format | Best pillar use | Evidence requirement |
|---|---|---|
| Same task, two workflows | Proof and Control | Show request, plan, diff, checks, and result; do not manufacture a failure |
| Failure anatomy | Any | Reproduce or cite the failure and separate observation from inference |
| Five-minute concept | Control and Continuity | One concept, one analogy, one action; expand abbreviations |
| Repository proof note | Proof | Link to the exact test, command, receipt, or source file |
| Build-in-public decision | Control | State the trade-off, rejected alternative, and resulting product obligation |
| Case evidence card | Any | Named or permission-safe source, dated artifact, measurable outcome, and claim boundary |
| Beginner/expert paired guide | Any | Same outcome; optional explanation layer rather than two different products |
| Autonomous-run diary | All three | Accepted scope, checks, attempt count, intervention, result, and explicit authority boundary |

## Editorial guardrails

- Each piece has one primary pillar. Secondary tags are allowed; three-pillar pieces are usually too
  broad.
- Lead with a situation, not an AgentSmith component name.
- Explain the abbreviation or technical term once, then use the correct term.
- Use short sentences and plain international English. Avoid idioms and insider jokes.
- Use analogies only when they reduce explanation. One useful analogy is enough.
- Never turn “good enough alone” into an insult. Agree that the model is capable, then show which
  project responsibilities remain outside the model.
- Do not use speed, quality, security, beginner success, or customer-result claims without the named
  evidence.
- Do not make PromptPartner a fourth content pillar. It appears through real cases and at the point
  where the problem expands beyond the open-source harness.
- Do not make autonomy a spectacle. Show the scope, checks, stop condition, and result before calling
  a run autonomous.

## Decisions confirmed before Step 8

1. **Proof — Control — Continuity** is the content-pillar system.
2. The public translation is **“Prove it works. Keep it in scope. Continue without starting over.”**
3. The initial weighting is **40% Proof, 35% Control, and 25% Continuity**.
4. Autonomy remains a cross-pillar maturity story rather than becoming a fourth pillar.
5. PromptPartner appears through evidence and the service boundary instead of becoming a recurring
   promotional pillar.

---

**Gate passed:** the operator confirmed this content-pillar system on 2026-09-17. Step 8 may proceed.
