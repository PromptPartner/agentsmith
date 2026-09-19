# Value Proposition Canvas: AgentSmith

**Status:** Step 3 confirmed by the operator on 2026-09-17  
**Date:** 2026-09-17  
**Segment:** Technically curious first-time builder with a real professional problem  
**Inputs:** [`01-icp-synthesis.md`](01-icp-synthesis.md),
[`02-pain-point-analysis.md`](02-pain-point-analysis.md), and
[`case-evidence-placeholders.md`](case-evidence-placeholders.md)

## Scope and evidence posture

This canvas covers the primary segment first. The experienced-developer path shares much of the
value map, but its job hierarchy differs and should receive a separate variant after this one is
confirmed.

The canvas distinguishes four states:

- **Current:** shipped behavior with repository evidence.
- **Needs improvement:** the approach exists, but the fit is incomplete or difficult to use.
- **Planned:** accepted direction that is not yet a current capability.
- **Service:** optional PromptPartner help, separate from the open-source product.

## Customer profile

### Jobs to be done

| Job | Type | Importance | Current approach | Buying motivations |
|---|---|---:|---|---|
| Turn a real work problem into a maintained software result | Functional | 5 | Prompt a coding agent, accept a prototype, then repair it as needs grow | Escape Pain; Save Time; Make Money |
| Prove that a change works in the path that matters | Functional | 5 | Look at the interface, trust the agent's report, or run whichever test already exists | Get Comfort; Achieve Cleanliness/Hygiene; Escape Pain |
| Preserve intent and decisions across sessions | Functional | 5 | Keep one chat alive, paste context again, or trust automatic memory | Save Time; Avoid Effort; Get Comfort |
| Keep the agent inside the requested scope | Functional | 4 | Supervise each action, repeat constraints, and inspect changes manually | Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene |
| Recover safely when a change is wrong | Functional | 4 | Ask the agent to undo it, restore files manually, or restart | Get Comfort; Escape Pain; Save Time |
| Learn only the engineering concepts needed for the next responsible decision | Functional | 4 | Search scattered tutorials or ask the same agent that produced the work | Avoid Effort; Get Comfort; Save Time |
| Know when qualified help is required | Functional | 5 | Discover the boundary after a security, deployment, data, or architecture problem appears | Get Comfort; Save Money; Escape Pain |
| Feel in control of a project they did not know how to build before | Emotional | 5 | Alternate between excitement and uncertainty about what the agent changed | Get Comfort; Attain Health |
| Be seen as a responsible builder, not a reckless “vibe coder” | Social | 3 | Defend the result through effort or screenshots rather than inspectable evidence | Gain Praise/Love; Increase Social Status; Achieve Cleanliness/Hygiene |

### Pains

| Pain | Type | Severity | Buying motivations |
|---|---|---|---|
| The user cannot prove the result is correct across the whole path | Risk and obstacle | Extreme | Get Comfort; Achieve Cleanliness/Hygiene; Escape Pain |
| Generic or incorrect CI configuration checks the wrong thing or fails to fit the repository | Obstacle and false-confidence risk | High | Get Comfort; Escape Pain; Save Time |
| Specifications, decisions, evidence, and failed approaches disappear between sessions | Obstacle and undesired outcome | High | Save Time; Avoid Effort; Get Comfort |
| Almost-right output creates repeated repair prompts and regressions | Undesired outcome | High | Escape Pain; Save Time; Save Money |
| The agent changes more than the user requested | Risk and undesired outcome | High | Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene |
| Installation, project/global scope, and profile selection delay first value | Obstacle | Moderate–high | Avoid Effort; Save Time; Get Comfort |
| A polished interface hides errors in data, permissions, background work, or edge cases | Risk | Extreme | Get Comfort; Save Money; Escape Pain |
| The user cannot distinguish a safe learning task from work requiring expert review | Risk | High | Get Comfort; Escape Pain; Attain Health |

### Gains

| Gain | Type | Relevance | Buying motivations |
|---|---|---|---|
| Evidence that matches the repository and the real user-visible path | Required | Essential | Get Comfort; Achieve Cleanliness/Hygiene |
| A short plan the user understands before any files change | Required | Essential | Get Comfort; Escape Pain |
| Durable specifications, decisions, proof, and next steps across sessions | Required | Essential | Save Time; Avoid Effort; Get Comfort |
| A safe recovery path with understandable checkpoints | Required | Essential | Get Comfort; Escape Pain |
| One guided first loop that teaches specification → change → verification → recovery | Expected | Essential | Avoid Effort; Get Comfort; Save Time |
| The same quality bar can travel across supported coding agents and projects | Desired | High | Save Time; Achieve Cleanliness/Hygiene; Avoid Effort |
| The workflow becomes stricter only when risk and project complexity grow | Desired | High | Avoid Effort; Save Time; Get Comfort |
| The user can explain what was changed and why it is acceptable | Desired | High | Gain Praise/Love; Get Comfort |
| A clear bridge to PromptPartner's existing audit and build journey when the need is broader than the harness | Desired | Moderate | Get Comfort; Escape Pain; Save Time |
| A future path from disciplined local development to an AI Admin Panel hosting environment | Unexpected / future | Moderate | Avoid Effort; Get Comfort; Make Money |

## Value map

### Products and services

| Product or service | State | Category | Customer role |
|---|---|---|---|
| AgentSmith local agent-native software development lifecycle harness | Current | Core product | Provides the shared operating model around coding agents |
| Canonical operating agreement with generated client adapters | Current | Core capability | Keeps rules inspectable and reduces instruction drift across supported clients |
| Work-type profiles | Current; usability needs improvement | Core capability | Defines what “done” and “verified” mean for the work at hand |
| Repository-owned verification configuration and full verification command | Current; fit needs improvement | Core capability | Runs deterministic checks selected by the project |
| Specification and repository-questioning skills | Current | Content and workflow | Turns an unclear request into bounded, reviewable intent |
| Durable handoff and feedback records | Current | Core capability | Preserves progress, decisions, evidence, and the next step |
| Cautious permissions, update plans, receipts, and rollback | Current | Core capability | Makes consequential change visible and recoverable |
| Finite maker/checker autonomous runs in isolated worktrees | Current advanced capability | Ancillary | Adds bounded autonomy when the repository has trustworthy checks |
| Guided first-loop sandbox | Planned | Onboarding resource | Teaches one safe, complete workflow before touching valuable work |
| Verification discovery and adaptation | Needs improvement | Product enhancement | Helps the user configure checks that fit the repository and exercise the real path |
| PromptPartner's existing audit, build, launch/scale, and ownership-transfer services | Existing service context | Supporting service | Uses AgentSmith as a free, tailored delivery component where relevant; AgentSmith is not a separate service or paid add-on |
| AI Admin Panel hosting and operating bridge | Planned / separate product | Ecosystem adjacency | Future recommended environment after AgentSmith-guided development |

### Pain relievers

| Pain addressed | Pain reliever | How it works | Fit today | Buying motivations |
|---|---|---|---|---|
| Cannot prove correctness | Layered evidence contract | Combines repository checks, a real exercised path, and judgment-based evaluation instead of accepting the agent's assertion | **Moderate:** principle is strong; project configuration and proof need better discovery | Get Comfort; Achieve Cleanliness/Hygiene |
| CI does not fit the repository | Project-owned verification configuration | Keeps commands in the repository instead of hiding them in a hosted black box | **Weak–moderate:** flexible in principle, but selection and adaptation have failed in some cases | Get Comfort; Save Time; Escape Pain |
| Context disappears | Durable specifications, decision records, handoffs, and feedback | Stores project memory in version-controlled artifacts that fresh sessions can read | **Strong:** shipped; usability and case proof still needed | Save Time; Avoid Effort; Get Comfort |
| Repair loop | Small units, failing checks, full verification, and explicit completion gates | Detects a mismatch before it becomes another broad repair prompt | **Moderate–strong:** shipped process; outcome evidence pending | Escape Pain; Save Time |
| Agent exceeds scope | Operating agreement, cautious permissions, atomic changes, and diff review | Names allowed behavior, asks at consequential boundaries, and keeps work reversible | **Strong for governance; bounded by client enforcement** | Get Comfort; Achieve Cleanliness/Hygiene |
| Setup is confusing | Profiles, installer, doctor, and a planned guided default | Makes the active work type and installed surfaces visible | **Weak–moderate:** product blocker remains | Avoid Effort; Save Time |
| Visual success hides defects | End-to-end exercise plus named security and data checks | Requires evidence at the last layer the user sees and at hidden risk boundaries | **Moderate:** depends on project-specific checks and expertise | Get Comfort; Escape Pain |
| User exceeds expertise | Explicit high-consequence boundary and escalation path | Makes clear when the harness cannot replace qualified review | **Strong as an honest boundary; not a substitute for service access** | Get Comfort; Save Money |

### Gain creators

| Gain addressed | Gain creator | How it works | Fit today | Buying motivations |
|---|---|---|---|---|
| Understandable plan before change | Plain-language specification and plan workflow | Explains why, scope, risks, and success checks before implementation | Strong | Get Comfort; Escape Pain |
| Durable continuity | Repository-owned memory and handoff | Lets the next session resume from evidence rather than reconstructing the conversation | Strong | Save Time; Avoid Effort |
| Safe recovery | Atomic Git state, update receipts, rollback, and isolated worktrees | Gives the operator named checkpoints and bounded blast radius | Strong for supported flows | Get Comfort; Escape Pain |
| Guided learning | Prepared defect-repair sandbox | Teaches the method through one real but low-risk loop | Planned; requires usability testing | Avoid Effort; Get Comfort |
| Portable quality bar | Canonical source plus supported adapters | Reuses one operating model while keeping repository-specific verification | Moderate–strong; support depth varies by client | Save Time; Achieve Cleanliness/Hygiene |
| Progressive rigor | Core rules plus task-specific profiles and skills | Loads specialized guidance when the work needs it instead of forcing one large methodology everywhere | Strong as architecture; outcome proof pending | Avoid Effort; Save Time |
| Responsible-builder credibility | Specifications, checks, receipts, and case evidence | Replaces “trust me” with an inspectable trail | Moderate; customer proof placeholders remain incomplete | Gain Praise/Love; Get Comfort |
| Expert help at the boundary | PromptPartner's existing PROVE · SECURE · LAUNCH · SCALE · OWN journey | Adds forward-deployed engineering and business-operator judgment around the customer's systems; the harness is included and adapted where relevant | Existing service model; AgentSmith attribution path needs measurement | Get Comfort; Escape Pain |
| Development-to-hosting path | Future AI Admin Panel bridge | Connects governed development with a recommended operating environment | Future; do not use as present-tense proof | Avoid Effort; Get Comfort |

## Fit analysis

### Fit matrix

| Customer element | Matched value-map element | Fit strength | Gap or risk |
|---|---|---|---|
| Job: prove that the result works | Layered evidence contract plus repository-owned verification | **Moderate** | Highest-priority gap: configuration may not fit the project or exercise every relevant path |
| Job: preserve intent across sessions | Durable specifications, decision records, and handoffs | **Strong** | Needs case evidence and a simpler view of which artifact to use when |
| Job: keep the agent in scope | Operating agreement, cautious permissions, and atomic changes | **Strong** | Client behavior and permissions differ; cannot imply perfect enforcement |
| Job: recover safely | Rollback, receipts, Git checkpoints, and isolated worktrees | **Strong** | Git mental model still needs beginner-friendly teaching and proof |
| Job: learn only what is needed | Profiles, skills, and guided sandbox | **Moderate** | Profile/install choices are still confusing; sandbox is planned, not shipped |
| Job: know when expert help is required | Explicit boundary plus PromptPartner's existing audit and delivery journey | **Moderate–strong** | The service exists; AgentSmith must route into it without confusing the product and service roles |
| Pain: repair loops | Failing checks, small tasks, and completion gates | **Moderate–strong** | Need before/after case evidence; checks are only useful when correctly configured |
| Gain: portable quality bar | Canonical rules and adapters | **Moderate–strong** | Native evidence is deepest for Claude and Codex; avoid implying equal support everywhere |
| Gain: responsible-builder credibility | Inspectable artifacts and proof trail | **Moderate** | Three case placeholders contain no approved outcomes yet |
| Future gain: recommended hosting path | AI Admin Panel ecosystem bridge | **Gap / future** | Keep outside current product promise until integration is shipped and verified |

### Fit narrative

AgentSmith fits users who have discovered that code generation is only the visible first part of the
job. It gives them a shared way to state intent, constrain the change, preserve decisions, and ask
for evidence. The emotional transformation is from “I hope the agent handled it” to “I know what was
requested, what changed, what was checked, and where I still need help.” This primarily addresses
**Get Comfort**, **Escape Pain**, **Save Time**, and **Achieve Cleanliness/Hygiene**.

The fit is strongest around continuity, explicit operating rules, reversible work, and progressive
rigor. It is not yet strongest at the highest-priority pain: verification that adapts cleanly across
different repositories. Under the EPIC standard, the proposition is **Personalized** and **Clear**,
but it becomes **Irrefutable** only after adaptive verification is improved and the case placeholders
contain observed evidence. The controlled-loop and car-park analogies can make it memorable
(**Entertaining**) without exaggerating autonomy or speed.

## Identified gaps and decisions

| Gap | Why it matters | Recommended response |
|---|---|---|
| Verification discovery and adaptation | The lead pain is also an incomplete product fit | Make verification configuration a guided, testable product surface: detect the stack, propose commands, show coverage limits, and require one exercised real path |
| Whole-chain coverage | A green CI result can miss the outcome the user actually sees | Separate deterministic checks from end-to-end exercise and judgment-based evaluation in product and documentation |
| Profile and install clarity | Users may not reach the value map | Provide one recommended default, show active scope and ownership, and move advanced choices behind progressive disclosure |
| Lost-context usability | Multiple durable artifacts can become another cognitive burden | Define one visible session memory flow: approved intent → progress/evidence → next step, with deeper records behind it |
| Beginner outcome proof | Beginner suitability remains a target, not demonstrated value | Run at least three observed sandbox sessions and measure comprehension, recovery, and transfer |
| Customer proof | PromptPartner credibility cannot rest on first-party assertions alone | Complete the three [case-evidence placeholders](case-evidence-placeholders.md) with permission-safe artifacts |
| PromptPartner conversion alignment | AgentSmith could accidentally look like a separate consulting offer | Route the open-source lead magnet into the existing audit and delivery journey; measure attribution without adding a new service line |
| AI Admin Panel bridge | The future ecosystem can become a distraction or premature claim | Keep it in vision and roadmap language until the development-to-hosting flow is integrated and verified |

## Decisions confirmed before Step 4

1. Verification improvement becomes the first product priority: discover the stack, propose checks,
   explain coverage gaps, and exercise one real path.
2. Continuity should connect the approved specification at the start with evidence, decisions, and a
   handoff at the end; the exact artifact UX remains product work.
3. AgentSmith is an open-source lead magnet and a free, tailored component inside relevant
   PromptPartner projects. It does not become a standalone diagnostic, migration service, or paid
   add-on. Leads enter PromptPartner's services already listed on its website.
4. AI Admin Panel appears only as future ecosystem direction, not a current AgentSmith benefit.
5. Later messaging leads with confidence through evidence, followed by continuity and reduced repair
   work.

## Proposed enhancements

- Build a verification-coverage map that distinguishes build, type checking, linting, tests,
  end-to-end exercise, security review, and judgment-based evaluation. Show explicitly which cells
  are configured and which remain unsupported.
- Prototype a single “active AgentSmith state” explanation: where it is installed, which profile is
  active, what is project-specific, what is central, and which verification command will run.
- Use the AI Admin Panel case to trace one value through specification → implementation → CI → real
  environment → customer-visible result, including where the original verification configuration was
  insufficient.
- Turn the three case placeholders into internal evidence cards before extracting public copy.
- Create the experienced-developer VPC only after this primary canvas is confirmed, then record the
  differences rather than duplicating the entire strategy.

---

**Gate passed:** the operator confirmed this revised Value Proposition Canvas on 2026-09-17. Step 4
may proceed.
