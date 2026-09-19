# Pain-point analysis: AgentSmith

**Status:** Step 2 confirmed by the operator on 2026-09-17  
**Date:** 2026-09-17  
**Primary segment:** Technically curious first-time builder with a real professional problem  
**Evidence base:** [`01-icp-synthesis.md`](01-icp-synthesis.md) and
[`agentic-coding-user-struggles-2026.md`](../research/agentic-coding-user-struggles-2026.md)

## Executive priority

The strongest opening pain is not “coding is difficult.” AI has already made the first draft easier.
PromptPartner's delivery experience identifies verification as the more urgent problem:

> **You can get code quickly. The hard part is proving that it works across the whole project—not
> only in the agent's response or one convenient test.**

Lost context is the second urgent pain: a good result is difficult to repeat when the specification,
decisions, failed approaches, and next step disappear between sessions. Repair loops and uncontrolled
scope remain strong concrete symptoms beneath these two pains.

This priority also exposes a product gap. AgentSmith's verification approach is valuable, but its
continuous-integration configuration has not fit every PromptPartner case. A fixed command can be
green while missing the real path, or fail because the preset does not match the repository. The
promise must therefore be **project-owned, end-to-end evidence**, not “one universal CI file solves
verification.”

## Primary pain points

### Pain 1: The user cannot prove that the result is correct

| Attribute | Detail |
|---|---|
| **Who experiences it** | Non-developers, domain experts, and developers working outside their strongest domain |
| **When and where it occurs** | Data transformations, integrations, permissions, background jobs, edge cases, and polished interfaces that hide incorrect behavior |
| **Consequences** | False confidence; incorrect data or decisions; defects reach colleagues or customers; responsibility remains with a user who lacks usable evidence |
| **Current alternatives** | Judge by whether the page looks right; ask the same agent to review itself; trust one narrow test or a generic CI preset; seek expert review late |
| **Severity** | **Extreme as a risk**, although it may remain invisible before failure |
| **Pain type** | Risk and obstacle |
| **Buying motivations** | Get Comfort; Achieve Cleanliness/Hygiene; Escape Pain; Attain Health; Save Money |

**Evidence:** A 2026 survey describes a perception–action gap: non-developers recognize risks but
have less ability to debug and verify them. A separate study found business users could not reliably
identify important flaws in AI-generated analysis code. PromptPartner experience ranks verification
as the most urgent pain, including cases where AgentSmith's CI configuration did not fit the project.
[Vibe-coder survey](https://arxiv.org/abs/2605.24521) ·
[Non-programmers assessing AI-generated code](https://arxiv.org/abs/2508.06484)

**Product implication:** verification must be repository-owned and layered: deterministic checks for
known behavior, an exercised end-to-end path, and human or independent evaluation where judgment is
required. Configuration discovery and adaptation remain product work.

### Pain 2: The project outgrows the conversation

| Attribute | Detail |
|---|---|
| **Who experiences it** | Serious first-time builders, solo developers, founders, and small teams working over weeks or months |
| **When and where it occurs** | The prototype becomes a maintained product; sessions reset; decisions remain only in chat; several agents or clients touch the same repository |
| **Consequences** | Intent is re-explained; architecture and terminology drift; the agent reopens settled decisions; failed approaches repeat; nobody knows the safe next step |
| **Current alternatives** | Keep one chat alive; paste a large context prompt; trust automatic memory; create documents after problems appear; adopt a heavyweight methodology |
| **Severity** | **High** for long-running work; moderate during the first isolated task |
| **Pain type** | Obstacle and undesired outcome |
| **Buying motivations** | Save Time; Avoid Effort; Get Comfort; Achieve Cleanliness/Hygiene |

**Evidence:** The operator identifies lost context as the second urgent PromptPartner pain.
Community accounts describe useful projects becoming hard to understand as code and agent scaffolding
accumulate. BMAD, GSD, and similar systems preserve specifications, plans, state, and checkpoints,
which is product evidence of market attention—not proof of outcome.
[Research synthesis](../research/agentic-coding-user-struggles-2026.md#2-the-difficulty-moves-rather-than-disappears)

### Pain 3: Almost-right output becomes a repair loop

| Attribute | Detail |
|---|---|
| **Who experiences it** | First-time builders most visibly; experienced developers also encounter it in unfamiliar or mature repositories |
| **When and where it occurs** | After the first prototype works, during later changes, integrations, debugging, or attempts to make the result production-ready |
| **Consequences** | Repeated prompts; regressions; time spent explaining the same intent; growing code the user cannot judge; delayed release; eventual rewrite or expert rescue |
| **Current alternatives** | Keep re-prompting; accept “good enough”; restart; ask another model; hire a developer after the project becomes difficult to recover |
| **Severity** | **High**, becoming extreme when customers or operations depend on the project |
| **Pain type** | Undesired outcome and obstacle |
| **Buying motivations** | Escape Pain; Save Time; Save Money; Get Comfort; Achieve Cleanliness/Hygiene |

**Evidence:** In Stack Overflow's 2025 survey, 66% of respondents selecting AI frustrations reported
solutions that were “almost right, but not quite”; 45% said debugging AI-generated code took more
time. Community accounts describe the same cycle as fixes that create new work.
[Stack Overflow 2025](https://survey.stackoverflow.co/2025/ai)

**Customer-language hypothesis:** “Vibe code once, bug-fix forever.” This comes from the operator's
experience and should be tested as language, not presented as a statistic.

### Pain 4: The agent changes more than the user intended

| Attribute | Detail |
|---|---|
| **Who experiences it** | First-time builders who cannot quickly review the blast radius; experienced developers granting broad autonomy |
| **When and where it occurs** | Broad or ambiguous prompts, refactors, long sessions, large permission scopes, and tasks without named files or stopping conditions |
| **Consequences** | Unrelated files change; working behavior breaks; rollback becomes unclear; review cost grows; trust in the agent falls; the user starts supervising every action |
| **Current alternatives** | Babysit the session; repeatedly say “only change X”; manually inspect every diff; revert wholesale; use cautious permissions without a complete workflow |
| **Severity** | **High**; extreme when the repository contains production or customer-facing work |
| **Pain type** | Risk and undesired outcome |
| **Buying motivations** | Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene; Save Time |

**Evidence:** Community users repeatedly describe reliable use as small task → test → diff review →
correction because broader freedom causes unexpected changes. The operator independently named agents
“going wild” as a recurring trigger. Treat the community evidence as qualitative language rather
than prevalence. [Research synthesis](../research/agentic-coding-user-struggles-2026.md#3-agents-exceed-the-requested-scope)

### Pain 5: The safe workflow is harder to start than the coding agent

| Attribute | Detail |
|---|---|
| **Who experiences it** | First-time builders and experienced users moving among several coding clients or projects |
| **When and where it occurs** | Installation; choosing project versus central setup; selecting or switching profiles; distinguishing rules, skills, plugins, hooks, and Model Context Protocol connections |
| **Consequences** | The user skips the harness; installs too much; chooses the wrong profile; cannot tell what is active; returns to an unstructured prompt because it produces faster visible output |
| **Current alternatives** | Use the coding agent alone; copy a large instruction file; install a broad skill pack; follow scattered tutorials; ask the agent to configure itself |
| **Severity** | **Moderate to high as an adoption blocker**; not normally the user's original business pain |
| **Pain type** | Obstacle |
| **Buying motivations** | Avoid Effort; Save Time; Get Comfort; Achieve Cleanliness/Hygiene |

**Evidence:** The operator reports current difficulty selecting and switching profiles and
understanding central versus per-project installation. GitHub Skills' onboarding guidance supports a
template, a few steps, quick progress, and automated feedback. External validation specific to
AgentSmith onboarding does not yet exist. [GitHub Skills Quickstart](https://skills.github.com/quickstart)

**Interpretation:** this should be fixed and explained, not turned into the hero message. Marketing
cannot compensate for confusing activation.

## Secondary pain points

These matter most to the experienced-developer path. They strengthen retention and credibility, but
should not compete with the primary beginner story on the first screen.

### Pain 6: The quality bar is rebuilt for every repository and agent

| Attribute | Detail |
|---|---|
| **Who experiences it** | Solo developers, engineering leads, technical founders, and AI consultancies |
| **When and where it occurs** | Starting a repository, changing from Claude Code to Codex, onboarding a collaborator, or copying instructions between customer projects |
| **Consequences** | Configuration drift; repeated setup; inconsistent definitions of done; duplicated maintenance; one client behaves safely while another silently skips the rule |
| **Current alternatives** | Copy `AGENTS.md` or `CLAUDE.md`; maintain private templates; rely on personal habits; adopt a client-specific framework |
| **Severity** | **Moderate to high**, depending on repository and client count |
| **Pain type** | Obstacle and cost |
| **Buying motivations** | Save Time; Avoid Effort; Achieve Cleanliness/Hygiene; Save Money |

### Pain 7: More autonomy creates coordination and integration risk

| Attribute | Detail |
|---|---|
| **Who experiences it** | Experienced developers running long sessions, parallel agents, worktrees, or maker/checker loops |
| **When and where it occurs** | Two agents touch overlapping files or shared resources; branches diverge; checks pass in isolation; an autonomous loop repeats the wrong approach |
| **Consequences** | Merge conflicts; duplicate work; integration defects; hard-to-follow branch state; wasted model spend; false confidence from isolated green checks |
| **Current alternatives** | Manually assign worktrees; run agents sequentially; use an orchestration platform; grant broad autonomy and resolve collisions afterward |
| **Severity** | **High when parallelism is active**, but irrelevant before the user reaches that stage |
| **Pain type** | Risk and obstacle |
| **Buying motivations** | Save Time; Get Comfort; Achieve Cleanliness/Hygiene; Avoid Effort |

### Pain 8: Structured workflows become ceremony

| Attribute | Detail |
|---|---|
| **Who experiences it** | Developers and consultants who tried BMAD, GSD, large skill packs, or role-heavy orchestration systems |
| **When and where it occurs** | Small tasks inherit full planning workflows; static instructions consume context; similar artifacts repeat; the method becomes more visible than the product |
| **Consequences** | Token and time cost; slower iteration; users bypass the process; important rules disappear inside a large instruction surface; methodology fatigue |
| **Current alternatives** | Abandon structured workflows; use only selected pieces; create a private lightweight setup; accept inconsistent agent behavior |
| **Severity** | **Moderate**; high for frequent small tasks or large multi-client setups |
| **Pain type** | Obstacle and undesired outcome |
| **Buying motivations** | Avoid Effort; Save Time; Save Money; Get Comfort |

## Emotional versus functional pain matrix

| Pain | Functional dimension | Emotional dimension | Buying motivations |
|---|---|---|---|
| Almost-right repair loop | Rework, regressions, delayed release | Frustration; feeling trapped in a project that was supposed to become easier | Escape Pain; Save Time; Get Comfort |
| Agent exceeds scope | Unplanned files and behavior change | Loss of control; anxiety about what happened unseen | Get Comfort; Achieve Cleanliness/Hygiene |
| Cannot prove correctness | Weak evidence around data, security, and edge cases | False confidence followed by fear or embarrassment | Get Comfort; Attain Health; Escape Pain |
| Project outgrows the conversation | Lost decisions, context drift, repeated explanation | Overwhelm; “I no longer understand my own project” | Save Time; Get Comfort; Avoid Effort |
| Workflow is hard to start | Installation and concepts delay first value | Intimidation; concern that disciplined work is only for professional developers | Avoid Effort; Get Comfort |
| Quality bar is rebuilt | Repeated configuration and inconsistent behavior | Irritation; lack of trust across tools | Save Time; Achieve Cleanliness/Hygiene |
| Autonomy creates collisions | Worktree, branch, resource, and integration conflicts | Fear of surrendering control; supervision fatigue | Get Comfort; Save Time |
| Method becomes ceremony | Context, token, and artifact overhead | Skepticism; fatigue; resistance to “enterprise theatre” | Avoid Effort; Save Money |

## Pain priority matrix

Priority combines severity, observed frequency, fit with shipped AgentSmith capabilities, and value as
a clear opening problem. It is a strategic ranking, not a prevalence score.

| Rank | Pain | Severity | Evidence of frequency | AgentSmith ability to address | Message role |
|---:|---|---|---|---|---|
| 1 | Cannot prove correctness | Extreme risk | Studies plus first-party delivery experience | Moderate today: strong principle, configuration gap remains | Lead problem and product priority |
| 2 | Project outgrows the conversation | High over time | First-party, community, and category signal | Strong | Second lead and long-term story |
| 3 | Almost-right repair loop | High | Strong survey plus community signal | Strong | Concrete consequence |
| 4 | Agent exceeds scope | High | Strong qualitative signal | Strong | Concrete example |
| 5 | Workflow is hard to start | Moderate–high blocker | First-party; external pattern evidence | Moderate today | Product requirement, not hero claim |
| 6 | Quality bar is rebuilt | Moderate–high | First-party and product-category signal | Strong | Experienced-developer lead |
| 7 | Autonomy creates collisions | High when active | Product and community signal | Moderate and growing | Advanced path / roadmap proof |
| 8 | Method becomes ceremony | Moderate | Community signal | Strong design philosophy; outcome unproven | Differentiation against heavy methods |

## Pain-to-messaging implications

These are problem angles for later testing, not approved headlines.

| Pain | Problem-messaging angle | EPIC emphasis |
|---|---|---|
| Cannot prove correctness | “A green check is useful only when it checks the path that matters.” | Clear; Irrefutable; Personalized |
| Project outgrows conversation | “A chat remembers a session. A project needs durable decisions.” | Clear; Entertaining through analogy; Personalized |
| Almost-right repair loop | “Getting code is fast. Knowing when the change is dependable takes a process.” | Clear; Personalized; Irrefutable with survey and case evidence |
| Agent exceeds scope | “Your agent should not decide how large the job becomes.” | Personalized; Clear; Entertaining through a simple contrast |
| Workflow is hard to start | “Begin with one working path—not a wall of profiles and plugins.” | Clear; Personalized |
| Quality bar is rebuilt | “Define the quality bar once, then carry it across agents and repositories.” | Clear; Personalized; Irrefutable through repository demonstration |
| Autonomy creates collisions | “Parallel agents need lanes, checkpoints, and an integration rule.” | Clear; Entertaining through road analogy |
| Method becomes ceremony | “Use the amount of process the work deserves.” | Clear; Personalized |

## What AgentSmith should and should not claim

### Lead with

- Verification that fits the repository and exercises the real outcome.
- Durable specifications, decisions, evidence, and handoffs across sessions.
- Less uncontrolled rework.
- A plan the user can understand before files change.
- Visible, executable evidence after the change.
- A durable path from one safe task to a maintained project.
- Progressive rigor: more structure when the risk grows, not ceremony everywhere.

### Do not lead with

- “Build software without developers.” It ignores the verification and expertise boundary.
- “10× faster.” Current evidence varies by task, user, tool, and quality measure.
- “Autonomous software factory.” It overstates current integration and scheduling capability.
- “No bugs” or “safe by default.” A harness reduces specific risks; it does not prove all software.
- Profile, hook, plugin, or worktree terminology before the user recognizes the problem.

### Ecosystem boundary

Hosting and deployment are outside AgentSmith's primary current promise. The planned ecosystem bridge
is AI Admin Panel as the recommended hosting and operating environment. Until that integration and
customer path are shipped and verified, describe it as future direction—not a current AgentSmith
capability. Expert security review also remains outside the promise.

## Validation status

| Pain | Strongest current validation | Confidence | Next evidence needed |
|---|---|---|---|
| Cannot prove correctness | Two studies plus PromptPartner delivery experience | High as a pain; partial AgentSmith fit | Repository-type test matrix and case evidence that the configured checks exercise the real path |
| Project outgrows conversation | PromptPartner experience, community accounts, and framework demand | High | AI Admin Panel timeline showing preserved decisions and handoffs |
| Almost-right repair loop | Stack Overflow survey plus community accounts | High | PromptPartner case trace with before/after rework evidence |
| Agent exceeds scope | Community accounts plus operator experience | Medium-high | Three observed first-use sessions; count and classify unrequested changes |
| Workflow is hard to start | Operator experience and onboarding research | Medium | First-use completion and profile-selection observation |
| Expert workflow pains | Operator experience, product research, community evidence | Medium | Interviews with developers or consultancies using multiple agents and repositories |

## Decisions confirmed before Step 3

1. Verification is the lead pain. Lost context is second. Both have direct PromptPartner evidence.
2. Installation and profile confusion remain an acknowledged product blocker, not the headline.
3. Hosting and deployment remain outside AgentSmith's current primary promise. AI Admin Panel is the
   planned recommended hosting environment and future ecosystem bridge.
4. Expert security review and underlying model quality remain outside AgentSmith's promise.
5. Three permission-safe case reconstructions or interviews are authorized as placeholders now and
   will be completed later; public publication still requires claim-level evidence and permission.

## Proposed enhancements

- Convert three PromptPartner engagements into evidence cards: trigger, previous approach, failure
  pattern, AgentSmith surfaces used, observable outcome, evidence strength, and publication scope.
- During first-use testing, capture behavior instead of satisfaction alone: time to first verified
  loop, scope corrections, recovery success, and whether the user can explain the evidence.
- Treat installation/profile confusion as a product experiment. Compare one recommended default
  against the current choice-heavy path before writing “easy setup” copy.
- Build the AI Admin Panel case around one difficult change and the full chain from specification to
  customer-visible outcome. Do not make the eight-month duration the only proof.
- Test the lead problem in two forms with identical evidence: repair-loop framing for professionals
  new to coding, and portable-quality-bar framing for experienced developers.

---

**Gate passed:** the operator confirmed this revised pain hierarchy on 2026-09-17. Step 3 may
proceed.
