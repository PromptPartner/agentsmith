# Ideal customer profile synthesis: AgentSmith

**Status:** Step 1 confirmed by the operator on 2026-09-17  
**Date:** 2026-09-17  
**Evidence base:** [`00-intake.md`](00-intake.md) and
[`agentic-coding-user-struggles-2026.md`](../research/agentic-coding-user-struggles-2026.md)

## Working market frame

AgentSmith is a portable, local **agent-native software development lifecycle (SDLC) harness**. It
helps a person and their coding agent agree on how work should be planned, changed, verified, and
handed off.

The primary path is not “no-code.” The user is willing to learn a limited amount. The product's job
is to teach the smallest useful mental model at the moment it matters, while making risky or
irreversible operations explicit.

The secondary path serves experienced developers who already know the mental model and want a
repeatable, inspectable starting environment without adopting a large methodology.

## Ideal customer profile snapshot

### Primary segment: the technically curious first-time builder

| Attribute | Definition |
|---|---|
| **Segment name** | Technically curious first-time builder |
| **Typical roles** | Designer, operator, founder, product manager, marketer, analyst, consultant, or domain expert |
| **Project profile** | A real internal tool, automation, prototype, or small product that has become important enough to maintain; usually an individual or a small, founder-led team |
| **Experience** | Comfortable with digital tools and structured thinking; little or no professional software-development experience; willing to learn concepts when they affect the result |
| **Buying/adoption triggers** | Someone says non-developers should not use coding agents; a first prototype works but later changes keep breaking it; the agent touches unrelated files; bad output creates a correction loop; the user discovers that a specification, tests, Git, or rollback should have existed earlier; the project is about to reach colleagues or customers |
| **Decision criteria** | Plain international English; safe defaults; works with familiar agents such as Claude Code or Codex; explains why before how; shows the plan and affected scope; produces evidence; permits rollback; teaches without forcing a programming course |
| **Initial success hypothesis** | Within 30 minutes, the user completes one safe loop in a prepared template repository: short specification, baseline prediction, bounded change, visible and automated verification, diff inspection, and recovery. They can then name a suitable first task in their own project. This needs usability testing. |
| **Ongoing success metrics** | Fewer unrequested changes; fewer repeated repair prompts; one understandable specification per meaningful change; a visible verification result; the user can resume after a break; the user knows when expert help is required |
| **Primary buying motivations** | **Get Comfort** (feel in control), **Escape Pain** (end correction loops), **Achieve Cleanliness/Hygiene** (tests, docs, safe repository state), **Save Time** (less rework), **Avoid Effort** (reusable setup), and **Gain Praise/Love** (prove that a non-developer can deliver responsible work) |

#### Explicit boundary

This segment should not be encouraged to ship customer data, authentication, payment, regulated, or
other high-consequence systems without qualified review. AgentSmith can make the workflow safer; it
cannot manufacture missing domain expertise.

### Secondary segment: the agentic developer seeking a reliable baseline

| Attribute | Definition |
|---|---|
| **Segment name** | Agentic developer seeking a reliable baseline |
| **Typical roles** | Solo developer, senior engineer, technical founder, staff engineer, engineering lead, or AI-enabled consultancy |
| **Project profile** | Existing repositories, several coding clients, long-running product work, or multiple parallel tasks where inconsistent agent behavior creates rework |
| **Experience** | Understands repositories, tests, architecture, and delivery; does not need beginner teaching but values inspectable automation and explicit risk boundaries |
| **Buying/adoption triggers** | Repeating the same setup in every project; rules drift between Claude Code and Codex; a multi-hour session loses intent; “green” tests miss the end-to-end path; an autonomous run exceeds scope; BMAD-style structure helps but feels heavy; parallel agents collide or create integration work |
| **Decision criteria** | Portable source-of-truth configuration; small static context; work-type profiles; deterministic verification; native-client support; safe updates; durable handoffs; bounded autonomy; worktree isolation; no mandatory hosted platform or role-playing bureaucracy |
| **Initial success hypothesis** | Within 10 minutes, the developer can inspect what AgentSmith will install, select or confirm a profile, run a repository-owned verification path, and see exactly which files and client adapters AgentSmith owns. This needs testing. |
| **Ongoing success metrics** | Lower setup time per repository; fewer agent-caused regressions and out-of-scope changes; less rework; more runs that finish with evidence; clean resume across sessions; safe parallel throughput; less time maintaining duplicated agent instructions |
| **Primary buying motivations** | **Save Time**, **Escape Pain**, **Achieve Cleanliness/Hygiene**, **Get Comfort**, **Avoid Effort**, and **Increase Social Status** (operate an advanced workflow without performative complexity) |

### Audience sequence: professionals first, not professionals only

Initial distribution should focus on people with a real professional problem: founders, designers,
operators, consultants, and developers responsible for an outcome. Their urgency creates the clearest
path to adoption, proof, and PromptPartner work.

Students and hobbyists remain important. Agentic coding is closer to the early consumer internet than
to a settled profession: today's learners may become tomorrow's practitioners, contributors, and
buyers. They should receive a guided learning path after the professional activation route is proven,
rather than making the first launch speak equally to every audience.

## Adoption committee map

AgentSmith is currently open source, so “buying committee” usually means the people who permit or
block adoption rather than a procurement process.

| Role | Typical person | Motivations | Typical objections | Win themes |
|---|---|---|---|---|
| **Self-serve champion and end user** | Designer, operator, founder, or developer with a real project | Get Comfort; Escape Pain; Save Time | “This may add more terminology and setup than it removes.” | One guided first loop; plain-English explanations; reversible installation; visible proof |
| **Economic buyer** | Usually the same individual; for a team, a founder or engineering lead | Save Time; Save Money; Achieve Hygiene | “Why pay attention to process when the model is already improving?” | Better models still need project-specific intent, permissions, verification, and continuity; the harness is inspectable and portable |
| **Technical evaluator** | Experienced collaborator, lead developer, or consultant | Achieve Hygiene; Get Comfort; Save Time | “This is just another large prompt file.” “Our existing workflow is enough.” | Small universal core; dynamic skills; deterministic checks; explicit ownership; evidence from the repository |
| **Security or infrastructure reviewer** | Developer, DevOps engineer, security lead, or managed-service provider | Get Comfort; Achieve Hygiene; Escape Pain | “A non-developer should not run an agent with shell access.” | Cautious defaults; no tracked secrets; scoped writes; approval boundaries; named security checks; honest boundary that the harness does not replace expert review |
| **Social blocker** | Colleague who equates non-developer use with irresponsible vibe coding | Get Comfort; Achieve Hygiene; Gain Praise/Love | “They cannot review the code, so they should not build.” | Separate code literacy from process literacy; show the specification, risk gates, evidence, and escalation path; never claim expertise is unnecessary |
| **Methodology skeptic** | Experienced developer who has tried BMAD, GSD, or large skill packs | Avoid Effort; Save Time; Escape Pain | “This will become token-heavy enterprise theatre.” | Progressive rigor; one concern per task; load guidance only when needed; make advanced orchestration optional |

## Priority use-case clusters

### 1. Start one real project responsibly

| Attribute | Detail |
|---|---|
| **Description** | Turn an idea or work problem into a small specification, an understandable plan, a bounded change, and visible evidence |
| **Primary persona** | Technically curious first-time builder |
| **Current approach** | Open a coding agent, describe the desired result in one prompt, accept the first implementation, and repair what breaks |
| **Success metrics** | Specification exists before code; user can explain the plan; scope remains bounded; verification is visible; next step is clear |
| **Buying motivations** | Get Comfort; Avoid Effort; Save Time; Gain Praise/Love |

#### First-use bridge into this use case

The first 30 minutes should use a prepared, disposable repository rather than the user's valuable
project. It teaches the real control loop with low risk: specify → predict → plan → change → verify →
inspect → recover. The user then transfers the method to one small task in their own repository.

Research supports this as a product decision, not a proven AgentSmith outcome. GitHub Skills uses
template repositories, a few short steps, and automated feedback; current developer tools use sample
or isolated tasks; PRIMM and worked-example research support scaffolded modification before open
creation. The complete source and caveat record is in the
[research brief](../research/agentic-coding-user-struggles-2026.md#what-should-happen-in-the-first-30-minutes).

### 2. Recover control of a growing vibe-coded project

| Attribute | Detail |
|---|---|
| **Description** | Understand the current repository, stop uncontrolled expansion, capture decisions, and establish tests, verification, and safe checkpoints before the next change |
| **Primary persona** | First-time builder whose useful prototype has become difficult to understand |
| **Current approach** | Ask the same agent what to fix next, add more rules after each failure, or restart parts of the project without a reliable baseline |
| **Success metrics** | Named current state; bounded next item; no unrelated edits; reproducible verification; known risks and escalation points; safe rollback |
| **Buying motivations** | Escape Pain; Get Comfort; Achieve Cleanliness/Hygiene; Attain Health (reduce anxiety and burnout) |

### 3. Standardize coding-agent behavior across projects and clients

| Attribute | Detail |
|---|---|
| **Description** | Reuse one operating model across Claude Code, Codex, and other supported clients while retaining project-specific profiles and verification |
| **Primary persona** | Experienced developer, technical founder, or AI consultancy |
| **Current approach** | Copy instruction files and scripts between repositories, then discover that they drift or conflict |
| **Success metrics** | Setup time falls; ownership is visible; profile is correct; client adapters match the canonical source; updates are reviewable and reversible |
| **Buying motivations** | Save Time; Avoid Effort; Achieve Cleanliness/Hygiene; Save Money |

### 4. Run longer work without losing the plot

| Attribute | Detail |
|---|---|
| **Description** | Preserve approved intent, progress, evidence, and the next step across context resets or multi-hour sessions |
| **Primary persona** | Experienced developer or serious first-time builder with an established project |
| **Current approach** | Keep one chat alive, repeatedly re-explain context, or trust opaque automatic memory |
| **Success metrics** | Durable handoff; clean resume; no re-derived decisions; context remains focused; explicit stopping points |
| **Buying motivations** | Save Time; Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene |

### 5. Increase autonomy without surrendering control

| Attribute | Detail |
|---|---|
| **Description** | Move from an attended task to a finite maker/checker run and eventually parallel work, with scope, attempts, verification, and interruption controls |
| **Primary persona** | Experienced developer or technical founder; later-stage use for beginners |
| **Current approach** | Run a long agent session with broad permissions, or adopt a complex orchestration framework before the repository has reliable checks |
| **Success metrics** | Every run is bounded; work is isolated; conflicts are detected; verification is independent; failure escalates instead of looping; the operator can stop and resume safely |
| **Buying motivations** | Save Time; Avoid Effort; Get Comfort; Increase Social Status |

## Segment and message hierarchy

| Layer | Primary path | Secondary path |
|---|---|---|
| **Shared truth** | AI can produce code quickly; trustworthy software still needs intent, boundaries, and evidence. | Same |
| **Opening problem** | “The agent built something, but you cannot tell whether it is safe, correct, or still under your control.” | “Every agent and repository needs the same engineering discipline rebuilt by hand.” |
| **Desired progress** | Understand enough to direct one real project responsibly. | Encode the team's quality bar once and apply it across agents and projects. |
| **Proof needed** | Guided first loop, plain-English plan, rollback, visible checks, beginner observation. | Installation diff, profile behavior, full verification, behavioral evaluation, long-run and worktree evidence. |
| **Autonomy posture** | Begin attended; increase only after the checks are trustworthy. | Start at the level the repository can prove; bounded autonomy is available but not the opening promise. |

## Key insights

1. **The common need is control, not skill level.** Beginners need control explained; experts need it
   compressed and automated.
2. **The product should teach a ladder, not a profession.** Explain specifications, scope, tests,
   Git checkpoints, and risk when they become relevant. Do not turn onboarding into a programming
   course.
3. **The first product moment should be a plan the user understands.** Code generation is already
   supplied by the model; AgentSmith's distinct value begins before and after generation.
4. **Speed is not the lead claim.** The defensible promise is less uncontrolled rework and more
   confidence in what ships. Quantified speed or quality claims require case evidence.
5. **The software-factory dream belongs on the roadmap, not the hero.** It attracts attention but
   overpromises for beginners and invites comparison with larger orchestration platforms.
6. **Progressive rigor is the differentiation.** BMAD validates demand for structure; complaints
   about token and process cost validate AgentSmith's small-core, load-when-needed design.
7. **Reddit and GitHub play different roles.** Reddit supplies honest problem language and
   conversation. GitHub supplies proof. LinkedIn can distribute the proof after it exists.
8. **Open source and lead generation must reinforce one another.** The repository, quickstart, and
   first proof loop should remain ungated. Interested teams should enter PromptPartner's existing
   audit and delivery journey; AgentSmith should not create a competing service line.
9. **Proof should be a portfolio, not one heroic story.** AI Admin Panel can be the named flagship.
   Anonymous cases can show repeated patterns—AI foundations, Claude configuration, skills, plugins,
   and governed workflows—without exposing customers or inventing unsupported outcome numbers.

## Assumptions and confidence

| Statement | Confidence | Basis / next test |
|---|---|---|
| First-time builders should be the primary communication path | High | Operator direction plus direct community evidence |
| “Control you can learn” is a stronger promise than “autonomous software factory” | Medium-high | Research convergence; requires message testing |
| A prepared 30-minute sandbox loop followed by transfer to the user's project is the right activation event | Medium-high | Learning research and current product patterns converge; no direct comparison study, so observe at least three first-time users |
| Experienced developers value all five proposed pains | Medium-high | Product and community evidence; lead pain still needs ranking through interviews or behavior |
| More than ten customer projects constitute a publishable proof point | Low today | First-party report; define framework use and outcome, then obtain permissioned evidence |
| AI Admin Panel can become the flagship case study | High as a case choice; medium as outcome proof | Operator approval and public product evidence; causal case narrative still needs reconstruction |
| Anonymous PromptPartner AI-foundation cases can show repeatability | Medium | Operator report; each case needs a permission-safe evidence record before public use |
| Open GitHub proof can feed PromptPartner's existing audit and build journey | Medium-high | Website and operator direction align; attribution and conversion still need testing |

## Decisions confirmed before Step 2

1. The first activation uses a prepared sandbox, followed by the user's repository.
2. The sample loop repairs a visible defect so fail → fix → verify → recover is concrete.
3. AgentSmith, the quickstart, and the complete first loop remain open on GitHub. PromptPartner's
   existing audit and build journey is the commercial next step; AgentSmith remains a free,
   project-tailored component when relevant.
4. Anonymous PromptPartner cases may be grouped by problem and capability when every public claim
   has a permission-safe evidence record.

## Proposed enhancements

- Observe three first-time users—ideally a designer, operator, and founder—completing the proposed
  sandbox activation loop. Record completion, where they hesitate, whether they can recover, and
  whether they can correctly scope the first task in their own project.
- Build one small “first loop” repository around a visible, non-security-critical defect. Keep the
  environment preconfigured, the acceptance checks readable, and the rollback observable.
- Reconstruct one AI Admin Panel feature from request → specification → change → verification →
  customer-visible result, including failures the harness caught.
- Create a lightweight evidence form for the 10+ PromptPartner projects: project type, AgentSmith
  surfaces used, AI-foundation components involved, defect/rework avoided, evidence available, and
  publication permission. Permit anonymous publication only when the evidence remains specific.
- Test a two-step conversion path: open repository → PromptPartner's existing audit and build
  journey. Measure both GitHub activation and qualified conversations; do not trade trust for an
  early email gate or invent an AgentSmith-specific service.
- Test two messages with the same proof: **“Control you can learn”** for beginners and
  **“Engineering discipline that travels with your agents”** for experienced developers.

---

**Gate passed:** the operator confirmed this profile on 2026-09-17. Step 2 may proceed.
