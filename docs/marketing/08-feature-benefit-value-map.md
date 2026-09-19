# Feature → benefit → value map: AgentSmith

**Status:** Step 8 confirmed by the operator on 2026-09-17  
**Date:** 2026-09-17  
**Content pillars:** Proof — Control — Continuity

## How to use this map

Features explain what AgentSmith contains. Benefits explain what changes for the user. Value explains
why that change matters in real work.

The public message should normally move from right to left:

> **Value → benefit → feature → proof**

For example, do not open with “hashed verification receipts.” Open with “Know what was checked,” then
show the receipt as evidence. The technical documentation can move in the opposite direction.

Each row below distinguishes current capability from planned improvement. Benefits are qualitative
until the case-evidence placeholders contain measured customer outcomes.

## Pillar 1: Proof

**Customer promise:** Prove it works.

| Feature and state | Customer benefit | Value delivered | Buying motivations | EPIC role | Proof and claim boundary |
|---|---|---|---|---|---|
| Repository-owned `.harness/verify.conf` and `agentsmith verify` — **current** | The project's real build, type, lint, and test commands live in one inspectable place | Completion depends on repeatable checks instead of the agent's confidence | Get Comfort; Achieve Cleanliness/Hygiene; Escape Pain | Irrefutable; Clear | Verification-runner tests and this repository's full gate. The configured commands may still be wrong or incomplete for a particular repository |
| Layered evidence contract — **current operating model** | Users distinguish automated checks, a real end-to-end exercise, and judgment-based evaluation | A green test result is less likely to hide a broken customer-visible path | Get Comfort; Escape Pain; Save Money | Clear; Personalized | [Verification model](../03-verify-means-evidence.md) and profile gates. The contract requires human or agent execution; prose alone does not enforce every layer |
| Redacted, hashed verification receipts — **current** | A later session or reviewer can see what ran, when it ran, and which Git state it covered | Evidence survives the chat and becomes auditable | Get Comfort; Achieve Cleanliness/Hygiene | Irrefutable | Receipt test suite. A receipt proves execution of named phases, not that the phases cover every risk |
| Native-client behavioral evaluation — **current for Claude Code and Codex** | Installation claims can be checked against observable agent behavior | Support is described by evidence rather than logos | Get Comfort; Achieve Cleanliness/Hygiene | Irrefutable | Evaluation schema, isolated runner, explicit budgets, and fake-client tests. Native evidence is not equally deep for all certification targets |
| Independent maker/checker gate — **current advanced mode** | A fresh checker can reject work instead of letting the same context approve itself | Autonomous work has an independent completion boundary | Get Comfort; Save Time; Achieve Cleanliness/Hygiene | Irrefutable; Personalized | Autonomous-run suite. The checker remains an AI reviewer plus deterministic checks, not a guarantee of correctness |
| Secret scan and named security checks — **current** | Some high-consequence mistakes are detected mechanically and security review cannot disappear behind “looks fine” | Lower chance of shipping an obvious credential or authorization mistake | Get Comfort; Escape Pain; Save Money | Irrefutable; Clear | Secret-scanner, consent, and policy tests. This does not make generated software secure |
| Adaptive verification discovery and coverage map — **planned priority** | Users would receive proposed checks that fit the repository and see what remains untested | The lead promise becomes easier to activate without false confidence | Avoid Effort; Get Comfort; Save Time | Personalized; Clear | No shipped proof yet. Do not market as current capability |

### Proof value chain

```text
Project-owned checks
        ↓
Visible automated + end-to-end + judgment evidence
        ↓
Know what was checked and what remains uncertain
        ↓
Make real delivery decisions with more confidence
```

## Pillar 2: Control

**Customer promise:** Keep it in scope.

| Feature and state | Customer benefit | Value delivered | Buying motivations | EPIC role | Proof and claim boundary |
|---|---|---|---|---|---|
| Canonical operating agreement plus work-type profiles — **current** | One inspectable source defines how the agent should work and what “done” means for the task | The user does not rebuild the quality bar in every prompt | Avoid Effort; Save Time; Get Comfort | Clear; Personalized | Assembly, profile, adapter, and leanness tests. Client enforcement still varies |
| Specification, repository-grilling, and decision workflows — **current** | Ambiguity is resolved before files change, with non-goals and acceptance checks recorded | Less work is spent building or repairing the wrong thing | Escape Pain; Save Time; Get Comfort | Personalized; Clear | Bundled skills, templates, and guard tests. The quality of a decision still depends on operator judgment |
| Atomic-change and scope rules — **current operating model** | A task stays small enough to inspect, test, and reverse | Smaller blast radius and clearer responsibility when something fails | Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene | Clear | Canonical rules and autonomous scope enforcement. Attended clients may follow prose imperfectly |
| Cautious permissions and first-external-write consent — **current** | Consequential actions become visible instead of being silently inferred from tool availability | The operator retains authority over external systems and higher-risk actions | Get Comfort; Escape Pain | Personalized; Clear | Native configuration, consent scenarios, and migration tests. Native sandboxes remain an additional required layer |
| Managed installation, ownership, update, uninstall, and rollback — **current** | Users can inspect what AgentSmith owns and reverse it without destroying unrelated configuration | Adopting the harness is not a one-way platform decision | Get Comfort; Avoid Effort; Achieve Cleanliness/Hygiene | Irrefutable; Clear | Idempotence, ownership, update, integrity, uninstall, and rollback tests |
| `doctor`, dry run, and compatibility reporting — **current** | The user can inspect likely changes, active surfaces, and evidence boundaries before trusting the setup | Fewer invisible configuration collisions and fewer support guesses | Get Comfort; Save Time | Irrefutable; Clear | Doctor, dry-run, and registry tests. The current output does not yet explain central, project, and profile state simply enough |
| Unified active-state explanation — **planned priority** | One view would show central installation, project configuration, active profile, generated adapters, ownership, and verification | Users can change the right source without guessing which copy is authoritative | Avoid Effort; Get Comfort; Save Time | Clear; Personalized | Not yet shipped as a coherent beginner-facing experience |

### Control value chain

```text
Accepted outcome + visible boundaries
        ↓
Small, inspectable, reversible changes
        ↓
Fewer scope surprises and repair loops
        ↓
Stay responsible for the result without supervising every keystroke
```

## Pillar 3: Continuity

**Customer promise:** Continue without starting over.

| Feature and state | Customer benefit | Value delivered | Buying motivations | EPIC role | Proof and claim boundary |
|---|---|---|---|---|---|
| Repository-owned specifications, decisions, handoffs, research, and evidence — **current** | Intent and progress survive context resets, model changes, and tomorrow's session | Less time is spent reconstructing why the work exists and what should happen next | Save Time; Avoid Effort; Get Comfort | Personalized; Clear | Shipped templates, skills, handoff tests, and repository use. Multiple artifacts can create cognitive load until the primary flow is simplified |
| Incident → feedback record → bounded harness edit → non-regression check — **current** | A repeated failure can improve the system instead of producing another reminder | The working environment compounds from real experience | Save Time; Achieve Cleanliness/Hygiene; Escape Pain | Irrefutable; Personalized | Feedback records, guard tests, and harness-review process. Each proposed rule still has to earn its context cost |
| Canonical source with client adapters and compatibility contract — **current** | Teams can carry one working agreement across supported agents while seeing where support differs | Switching agents does not require starting the governance model again | Avoid Effort; Save Time; Get Comfort | Irrefutable; Clear | Registry and conformance tests. Claude Code and Codex have the deepest native integration |
| Work-type profiles and dynamic skills — **current** | The same project can load the quality gates relevant to software, research, data, documents, marketing, or other work | Rigor adapts without forcing every task through one large methodology | Avoid Effort; Save Time; Get Comfort | Personalized | Profile assembly and skill compatibility tests. Profile choice and switching need a clearer user experience |
| Finite maker/checker runs with durable stop and resume — **current advanced mode** | One accepted item can continue without constant attendance and can be interrupted without losing its state | More delegation without surrendering scope or recovery | Save Time; Avoid Effort; Get Comfort | Personalized; Irrefutable | Autonomous-run tests. Current authority ends at local commits; it is not a full autonomous delivery platform |
| Worktree and resource-collision controls — **current advanced mode** | Parallel tasks can be isolated and overlapping work can fail closed before changes begin | Higher throughput with fewer agents overwriting each other's work | Save Time; Get Comfort; Achieve Cleanliness/Hygiene | Irrefutable | Collision, lock, stale-recovery, and scope tests. Multi-ticket scheduling and integration remain roadmap work |
| Guided sandbox and simplified continuity path — **planned priorities** | A new user would learn one complete loop and one obvious way to save and resume work | Faster path from first use to responsible repeated use | Avoid Effort; Get Comfort; Save Time | Entertaining; Personalized; Clear | Not shipped or user-tested; beginner suitability remains a target |
| AI Admin Panel development-to-hosting bridge — **future ecosystem** | Governed local work could move into a recommended operating environment | One path from development discipline to ongoing operation | Avoid Effort; Get Comfort; Make Money | Personalized | Future direction only; exclude from present-tense product claims |

### Continuity value chain

```text
Durable intent + evidence + next step
        ↓
Clean resume across sessions, agents, and isolated work
        ↓
Increase delegation without losing the project's memory
        ↓
Build a dependable long-term development practice
```

## Four hero mappings

These are the strongest candidates for the website, deck, README opening, and first demonstrations.
They combine a high-priority pain, a shipped mechanism, and an honest boundary.

| Customer situation | Lead value | Supporting benefit | Mechanism | Proof to show |
|---|---|---|---|---|
| “The agent says it is finished, but I cannot tell whether it works.” | **Make completion evidence-based** | See which checks ran and exercise the real outcome | Repository verification, layered evidence, and receipts | One change with baseline failure, passing checks, end-to-end exercise, and receipt |
| “The agent changed more than I asked for.” | **Keep the task inside an accepted boundary** | Review the plan, affected scope, and recovery path before the change grows | Specification, non-goals, atomic changes, permissions, and diff review | Same request with declared scope and an out-of-scope change rejected or surfaced |
| “Every new session starts by reconstructing the old one.” | **Preserve the project's working memory** | Resume from approved intent, evidence, and a named next step | Specifications, decisions, handoff, research, and feedback artifacts | Stop one session and resume in a fresh session without re-explaining the decision |
| “I want more autonomy, but not an agent that runs forever.” | **Delegate a bounded item with an independent stop condition** | Isolate the work, cap attempts, check it independently, and escalate when needed | Accepted spec, worktree, maker/checker, collisions, durable state, stop/resume | One finite local run showing scope, attempts, verification, checker result, and no push/merge authority |

## Buying-motivation coverage

| Motivation | Features addressing it | Coverage | Messaging constraint |
|---|---|---|---|
| Make Money | Real professional outcomes; future hosting bridge; PromptPartner delivery context | Weak today | Do not claim revenue impact without case evidence |
| Save Money | Reduced rework; secret/security gates; reusable setup | Moderate | No savings number until measured |
| Save Time | Verification reuse; durable handoffs; portable rules; bounded autonomous runs | Strong | Say “less repeated setup/reconstruction,” not a percentage |
| Avoid Effort | Profiles; dynamic skills; managed lifecycle; continuity artifacts | Strong | First-use complexity is still a gap |
| Escape Pain | Scope control; failing checks; recovery; feedback loop | Strong | Use observed failure language, not fear-based exaggeration |
| Get Comfort | Evidence, cautious authority, rollback, doctor, checker | Strong | Confidence must remain tied to named evidence |
| Achieve Cleanliness/Hygiene | Tests, receipts, atomic changes, secret scan, ownership | Strong | Avoid implying compliance certification |
| Attain Health | Fewer endless repair loops; finite retries; clean handoffs | Moderate | Treat reduced stress as a hypothesis until user evidence exists |
| Gain Praise/Love | Responsible-builder trail; explainable decisions and evidence | Moderate | Do not shame “vibe coders” or promise professional status |
| Increase Social Status | Advanced but inspectable practice; open-source contribution | Moderate | Avoid “elite” or replacement narratives |

## EPIC coverage

| Element | Features or benefits demonstrating it | Coverage | Improvement needed |
|---|---|---|---|
| Entertaining | “It runs” versus “it is proven”; agent exceeded scope; finite autonomous-run diary | Moderate | Produce concrete visual stories and demonstrations without manufacturing drama |
| Personalized | First-time and expert variants; repository-owned checks; work-type profiles | Strong in strategy | Validate wording with actual users in each path |
| Irrefutable | Executable repository tests, receipts, compatibility records, exact capability boundaries | Moderate–strong for mechanics | Complete case evidence and observed beginner outcomes |
| Clear | Three customer promises; plain-English boundaries; feature names stay below the promise | Strong as a target | Usability-test “control-and-evidence layer,” profile state, and continuity terminology |

## Pillar-to-feature fit assessment

| Assessment | Findings |
|---|---|
| **Strong fits** | Verification and receipts → Proof; specifications, permissions, and reversible ownership → Control; handoffs, adapters, feedback, and bounded runs → Continuity |
| **Cross-pillar features** | Profiles support Control and Continuity; maker/checker supports all three; `doctor` supports Proof and Control |
| **Weak fits** | Standard-library implementation, status line, raw client/profile/skill counts, and individual MCP or hook support are useful product details but weak value stories |
| **Gaps** | Proof lacks adaptive verification; Control lacks one simple active-state view; Continuity lacks a proven beginner sandbox and simplified memory path |
| **Orphans** | None require a fourth pillar. Technical hygiene belongs in reference documentation unless a real customer story makes it relevant |

## Claim discipline

### Safe now

- AgentSmith makes project rules, verification configuration, continuity artifacts, and managed
  ownership inspectable.
- It can run a repository-owned verification chain and write evidence receipts.
- It supports finite local maker/checker runs with current authority and platform limits stated.
- It is open source and can be used without a PromptPartner engagement.

### Requires a qualifier

- “Works across agents” → support depth differs; Claude Code and Codex have the deepest native
  integration.
- “Prevents scope creep” → it supplies rules and enforces scope in autonomous mode; attended client
  behavior can still deviate.
- “Verifies your work” → only the configured checks and exercised paths are proven.
- “Beginner-friendly” → designed for it, not yet validated through observed first-use evidence.

### Not yet safe

- quantified time, cost, quality, security, or productivity improvements;
- universal compatibility or equal native support across all targets;
- automatic verification configuration for every repository;
- complete autonomous software delivery; or
- a current AgentSmith-to-AI-Admin-Panel hosting flow.

## Product and evidence enhancements

1. Ship adaptive verification discovery and a visible coverage map.
2. Add one active-state explanation for installation scope, profile, owned surfaces, and verify path.
3. Build and observe the prepared sandbox with at least three first-time users.
4. Complete the AI Admin Panel evidence trace and two permission-safe customer case cards.
5. Record one honest autonomous-run diary, including rejection or intervention if it occurs.
6. Demonstrate the four hero mappings before turning them into high-confidence public claims.

## Decisions confirmed before Step 9

1. The four hero mappings are verification, scope, continuity, and bounded autonomy.
2. Benefits remain qualitative until the case evidence contains measured outcomes.
3. Reversible installation and configuration ownership sit under **Control**; cross-agent portability
   sits under **Continuity**.
4. Adaptive verification, the active-state view, and the guided sandbox remain visible product gaps
   rather than being softened in marketing.
5. Messaging uses one shared stack with separate first-time-builder and experienced-developer
   variants.

---

**Gate passed:** the operator confirmed this map on 2026-09-17. Step 9 may proceed.
