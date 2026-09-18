# Positioning and strategic narrative: AgentSmith

**Status:** Step 6 confirmed by the operator on 2026-09-17  
**Date:** 2026-09-17  
**Primary market entry:** Professionals using coding agents for real work  
**Primary communication path:** Technically curious first-time builder  
**Secondary communication path:** Experienced agentic developer

## Positioning components

This positioning follows the April Dunford sequence: competitive alternatives → unique attributes →
value → target segment → market category. It uses the confirmed [competitive analysis](05-competitive-alternatives.md),
not a feature-count comparison.

### 1. Competitive alternatives

The primary alternative is not another framework. It is:

> **“Claude Code or Codex is already good enough. I do not need anything around it.”**

The model may indeed be good enough to produce a strong first result. The hidden assumption is that
model capability also supplies the project's accepted scope, definition of done, verification
coverage, durable decisions, and recovery path. It does not unless those things already exist and are
made available to the agent.

The other alternatives remain relevant but secondary:

- a private instruction file or copied prompt collection;
- Superpowers, BMAD, or GSD Core as a software-development method;
- Archon as an adjacent workflow and orchestration engine; or
- an internally maintained harness.

Named comparisons belong in technical documentation and fair comparison content. The website and
main deck should explain the category difference without making competitors the story.

### 2. Unique attributes

No individual primitive below is unique. The defensible attribute is how AgentSmith combines them
into a portable, project-owned system with explicit lifecycle boundaries.

| Attribute | Type | Relative to which alternative | Current proof |
|---|---|---|---|
| Canonical core plus work-type profiles assembled into inspectable project instructions | Technology and expertise | Bare agent; copied private rules; software-only methods | Assembly, profile, idempotence, and leanness tests; generated canonical and client instruction files |
| Project-owned verification configuration with layered evidence and optional receipts | Technology and process | Bare agent; static rules; methods whose checks are not adapted to the repository | Verification runner and receipt tests; the repository's own full verification chain |
| Durable specifications, decisions, handoffs, research, and incident-to-guardrail feedback | Process and expertise | Session memory; prompt collections | Shipped skills, templates, feedback records, handoff tests, and repository examples |
| Reversible ownership of installation, configuration, updates, and rollback | Technology | Copied files; runtime-specific installs; internal scripts without managed ownership | Dry run, doctor, ownership, update-plan, integrity, uninstall, and rollback tests |
| Capability-level compatibility evidence instead of undifferentiated support logos | Technology and trust model | “Works everywhere” claims | Machine-readable registry, conformance tests, compatibility report, and native-client evaluation runner |
| One contract from attended work to bounded maker/checker autonomy | Technology and process | Bare long-running sessions; immediate adoption of a workflow engine | Worktree isolation, finite attempts, independent checking, collision control, durable stop/resume, and local-only authority tests |

### 3. Value

| Attribute | Value delivered | Buying motivations |
|---|---|---|
| Canonical rules and profiles | The agent receives the same quality baseline while the project defines what “done” means | Get Comfort; Avoid Effort; Achieve Cleanliness/Hygiene |
| Project-owned evidence | The operator can distinguish “the agent says it is done” from a result checked in the path that matters | Get Comfort; Escape Pain; Save Time |
| Durable continuity | Work survives context resets, model changes, and tomorrow's session without rebuilding the reasoning from scratch | Save Time; Avoid Effort; Get Comfort |
| Scope and recovery controls | Surprises have a smaller blast radius, and the user can see what changed and return to a known state | Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene |
| Reversible lifecycle ownership | Adoption is not a one-way configuration change; the operator remains able to inspect, update, or remove the system | Get Comfort; Avoid Effort; Save Time |
| Progressive autonomy | The user can begin with supervision and later run bounded work without replacing the underlying quality contract | Save Time; Get Comfort; Avoid Effort |

The value hierarchy is:

1. **Strategic:** make AI-assisted work dependable enough to become part of real delivery.
2. **Operational:** keep work scoped, verified, resumable, and recoverable across agents and sessions.
3. **Individual:** understand what happened, know what remains uncertain, and stay in control without
   learning every internal detail.

### 4. Target segment

#### Primary market segment: professional AI-assisted builders

Professionals responsible for a real outcome who use Claude Code, Codex, or another coding agent.
They include designers, operators, founders, consultants, product people, analysts, and developers.
The first communication path focuses on people who have not developed software professionally but
are willing to learn the small amount needed to make the next responsible decision.

**Segment characteristics**

- **Situation:** a prototype or internal tool has become important, an agent has exceeded scope, a
  repair loop has started, or the result is approaching colleagues or customers.
- **Trigger:** “The model produced something useful, but I cannot prove it is correct, resume the
  work cleanly, or explain everything it changed.”
- **Decision criteria:** low-friction start, plain international English, visible plan and scope,
  repository-specific checks, safe recovery, and no mandatory hosted service.
- **Existing tools:** Claude Code or Codex, Git, a local repository, and whichever build or document
  tools the work already uses.
- **Commercial relevance:** a professional problem creates urgency and a natural bridge to
  PromptPartner when the need expands beyond the open-source harness.

#### Secondary segment: experienced agentic developers

Developers, technical founders, engineering leads, and consultancies who already understand the
mechanics. They want the explanation compressed, the setup reusable, the evidence deterministic,
and autonomy bounded. They should be able to skip beginner teaching without losing the controls.

Students and hobbyists remain a later learning and community path. They are not excluded; the first
launch simply prioritizes people with a current professional outcome.

### 5. Market category

AgentSmith needs two category layers because one phrase cannot be both broadly understandable and
technically precise.

#### Public category

> **The portable control-and-evidence layer for AI-assisted work.**

This says what AgentSmith contributes without asking a first-time user to understand “harness” or
“software development lifecycle.” It also leaves room for document, research, data, marketing, and
administrative profiles. Initial examples should still lead with agentic coding because that is where
the pain, product maturity, and proof are strongest.

#### Technical category

> **An open-source, agent-native software development lifecycle (SDLC) harness.**

This gives experienced developers a familiar frame: AgentSmith surrounds the coding agent with the
rules, verification, continuity, and control needed across the delivery lifecycle. “Harness” is more
accurate than “platform”; “SDLC” is justified by shipped planning, implementation, verification,
handoff, feedback, and bounded-autonomy primitives. It does not imply a complete autonomous software
factory or full workflow engine.

#### Category rationale

- **Clear:** the public phrase says what the product controls and what it produces.
- **Believable:** the repository already proves the main mechanics; gaps are named rather than hidden.
- **Differentiated:** it does not claim to be a better model, another universal methodology, or an
  Archon-style orchestration engine.
- **Expandable:** the public layer supports non-software profiles while the technical layer remains
  precise for the strongest current use case.
- **Searchable:** “AI agent harness,” “agentic coding,” “verification,” and “SDLC” remain available in
  technical copy and metadata.

#### Alternative categories considered

| Category | Advantage | Problem | Verdict |
|---|---|---|---|
| Coding agent | Familiar and large market | False: AgentSmith does not supply the model or primary execution runtime | Reject |
| Agentic-development methodology | Explains specifications and disciplined workflows | Understates installation ownership and overstates how prescriptive the product should be | Supporting description only |
| Agent workflow engine | Makes autonomy and parallelism legible | Invites a direct orchestration comparison AgentSmith cannot and need not win today | Reject as current category |
| Autonomous software factory | Attention-grabbing aspiration | Overpromises current authority, scheduling, integration, and delivery | Vision language only, if ever |
| Developer tool | Easy to understand | Too broad to explain the difference | Metadata/category tag only |
| AI agent harness | Accurate emerging category | Unfamiliar to newcomers and says little about customer value | Use in technical copy |
| Agent-native SDLC harness | Precise for developers | Too technical and software-specific for the public umbrella | **Choose as technical category** |
| Portable control-and-evidence layer | States the distinct job and spans work types | Requires examples because “layer” is abstract | **Choose as public category** |

## Positioning statements

### Full positioning statement

> For **professionals using AI agents to build real work** who need more than a fast first draft,
> **AgentSmith** is an **open-source, portable control-and-evidence layer** that keeps work scoped,
> verified, resumable, and reversible. Unlike relying on **Claude Code or Codex alone**, AgentSmith
> makes the project's operating rules, evidence standard, memory, and path to bounded autonomy
> explicit and owned by the project.

### First-time-builder variant

> For professionals who can describe what they need but do not want to vibe-code forever,
> AgentSmith adds a clear plan, boundaries, proof, and a recovery path around the coding agent they
> already use. It teaches the next useful concept when it matters without pretending expertise is no
> longer necessary.

### Experienced-developer variant

> AgentSmith is an open-source, agent-native SDLC harness that makes your engineering discipline
> portable across projects and coding agents: one inspectable contract for scope, verification,
> continuity, reversible configuration, and bounded autonomous work.

### PromptPartner relationship

> AgentSmith is open-source infrastructure developed from PromptPartner's AI-delivery practice. It
> is included and tailored at no additional licence cost in relevant PromptPartner projects. The
> paid work is the wider audit, build, launch, scale, and ownership journey—not an AgentSmith add-on.

## Strategic narrative

### The shift: capable agents are becoming normal tools

Claude Code, Codex, and their peers can now plan, write, inspect, and run substantial work. People who
could not previously build software can create useful tools. Experienced developers can delegate
larger pieces of implementation. The cost of producing a first version has fallen sharply.

This shift is real. AgentSmith should not market against it. Better agents make the harness more
valuable because more consequential work can now be attempted.

### The stakes: generation became easier; responsibility did not disappear

The model can write the change, but the operator still owns the outcome. A polished interface can
hide incorrect data, missing authorization, incomplete edge cases, or a background process that was
never exercised. A long session can lose an earlier decision. A confident agent can finish the wrong
scope.

The faster the vehicle becomes, the more the driver depends on brakes, instruments, and a route. The
harness plays that role. It does not make the engine less capable; it makes the capability usable for
work that matters.

### The old way: trust the agent, then add rules after each failure

The common starting point is reasonable: open Claude Code or Codex, describe the task, and let the
model work. When something goes wrong, add another sentence to a rule file, paste more context, or ask
the same agent to verify its own result. Over time, the setup becomes a pile of local fixes that no
one can confidently update or remove.

The other reaction is to install a complete methodology or workflow platform immediately. Those
systems can be excellent when their additional structure is needed. They can also add more concepts
than a first task requires.

### The new way: let the model be capable and make the project explicit

Use the agent for reasoning and execution. Let the project own the contract around it:

1. state one bounded outcome;
2. show the plan and affected scope;
3. run checks that fit this repository;
4. exercise the result where a person or downstream system sees it;
5. preserve the evidence, decisions, and next step; and
6. increase autonomy only when the same contract can check the work independently.

This is progressive rigor. A small repair gets a small loop. A customer-facing or autonomous change
gets stronger gates. The operator does not adopt a software factory to fix one bug, and does not use
a one-shot prompt to run a software business.

### The proof: inspectable system first, outcome claims second

Current repository evidence supports the mechanics:

- canonical assembly and work-type profiles;
- repository-owned verification and evidence receipts;
- native Claude Code and Codex evaluation paths;
- reversible install, update, ownership, uninstall, and rollback behavior;
- durable specifications, handoffs, research, and feedback records; and
- finite maker/checker runs with worktree isolation, collision controls, stop/resume, and no push or
  merge authority.

The AI Admin Panel case and the reported PromptPartner project portfolio support the direction, but
their public outcome claims remain placeholders until artifacts, dates, permission, and measurable
results are collected. Beginner suitability also remains a design target until observed sandbox
sessions provide evidence.

### Our role: keep the control layer open and earn the right to help with more

AgentSmith should be useful without PromptPartner, an email gate, or a hosted account. The repository
is the product proof and the first call to action. It demonstrates how PromptPartner approaches
scope, evidence, safety, continuity, and ownership in customer delivery.

When the problem is broader than a harness—architecture, security, integration, organizational
adoption, or a production AI foundation—PromptPartner offers the wider service already described on
its website. AI Admin Panel may later become the recommended hosting and operating environment, but
that bridge remains future direction until it is shipped and verified.

## Message hierarchy

| Layer | Message | Purpose |
|---|---|---|
| Category | The portable control-and-evidence layer for AI-assisted work | Explain what AgentSmith adds |
| Problem | A capable model can still complete the wrong scope, verify the wrong thing, or forget why a decision was made | Challenge the “good enough alone” assumption without attacking the model |
| Promise | Keep work scoped, verified, resumable, and reversible | State the user outcome |
| Method | Project-owned rules, evidence, memory, and progressive autonomy | Explain how the promise is delivered |
| Boundary | AgentSmith does not replace expertise, security review, continuous integration, or a workflow engine | Preserve trust |
| Proof | Open repository, executable checks, inspectable ownership, cases as they are validated | Make the claim testable |
| Commercial bridge | Open source first; PromptPartner helps when the delivery problem is larger | Generate qualified interest without weakening the lead magnet |

## Positioning validation

| Criterion | Assessment | Evidence and remaining risk |
|---|---|---|
| **True** | Pass | The named mechanics are shipped and covered by repository checks; future hosting and broader orchestration are excluded from present-tense claims |
| **Relevant** | Pass | Verification, scope control, continuity, and repair loops lead the confirmed pain hierarchy |
| **Differentiated** | Pass with a bundle caveat | Individual features exist elsewhere; portable evidence, continuity, work-type breadth, and reversible ownership form the distinction |
| **Provable** | Partial | Product mechanics are provable; customer outcomes, beginner success, and adaptive verification still need evidence |
| **Sustainable** | Moderate | Better models may absorb more workflow behavior, but project-specific intent, evidence, authority, and ownership remain external responsibilities |
| **Clear** | Pass for the promise; test category language | “Scoped, verified, resumable, and reversible” is concrete; “control-and-evidence layer” needs examples |
| **Memorable** | Untested | The vehicle analogy and contrast with “good enough alone” are candidates, not evidence |
| **Actionable** | Pass | The narrative leads to one verified sandbox loop, a real project, repository adoption, and a PromptPartner bridge when needed |

## Product implications carried by the positioning

Positioning creates obligations. These are not optional marketing polish:

1. **Adaptive verification is the first product priority.** AgentSmith must detect likely checks,
   explain coverage, and exercise a real path without pretending every repository is identical.
2. **The active state must be understandable.** Users need one view of central installation, project
   installation, active profile, generated adapters, owned surfaces, and verification command.
3. **The first loop must be simpler than the current system.** A prepared sandbox should teach
   specification → scope → change → verification → inspection → recovery.
4. **Autonomy must remain continuously available but earned.** Every suitable project should have a
   visible route from attended work to a bounded autonomous run; missing checks should block or
   narrow the route rather than hide the capability.
5. **Coexistence must not add default complexity.** AgentSmith should stand alone. Integrations with
   another method or engine should ship only when the use case is clear, conflicts are resolved, and
   compatibility is tested.
6. **Examples should lead with coding while the architecture supports more.** This keeps the launch
   credible without abandoning document, research, data, marketing, and administrative profiles.

## Decisions confirmed before Step 7

1. The narrative challenges **“the model is good enough on its own”** while explicitly agreeing that
   the model itself may be excellent.
2. **“Keep AI-assisted work scoped, verified, resumable, and reversible”** remains the positioning;
   **“Know what changed. Prove it works. Continue with confidence.”** is shorter campaign copy to test.
3. Public examples lead with agentic coding even though the category extends to AI-assisted work.
4. The autonomy path remains visible, but trustworthy checks are required before broader unattended
   execution.
5. The PromptPartner bridge uses **“Built in the open from the delivery discipline we use in customer
   projects”**, followed where relevant by the approved no-additional-licence-cost wording.

---

**Gate passed:** the operator confirmed this positioning for now on 2026-09-17 and plans a later
review through a separate market-positioning engine. Step 7 may proceed.
