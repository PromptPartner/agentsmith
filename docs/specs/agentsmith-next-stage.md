---
status: accepted
decision_ticket: "paste-ready draft: Define AgentSmith's next-stage product boundary and roadmap"
accepted_by: Lukas Hertig
accepted_at: 2026-09-17T06:35:42Z
---

# Spec: AgentSmith's next-stage product update

## Destination

Ship a focused AgentSmith update that is easier to install and operate correctly, adapts its
context guidance to measured model behavior, supports skill/plugin development explicitly, and
coordinates several bounded coding tickets through isolated worktrees and an integration gate.

The result should deserve the description **an agent-native SDLC harness and local control layer**:
it connects planning, implementation, verification, integration, handoff, and learning without
becoming a hosted workflow platform. Its documentation and marketing must make the boundary clear
and let a new user choose the right installation and profile without understanding AgentSmith's
internal architecture first.

The product must serve two adjacent entry paths without forcing them through the same explanation:

- **Primary learning path:** technically curious people who may never have developed software, such
  as designers and operators trying agentic coding for the first time.
- **Experienced path:** developers who want a strong, inspectable starting environment and can skip
  introductory explanation without losing the quality and safety controls.

Both paths use friendly, collaborative, plain international English. Explanations give the reason
before the action, use short analogies where they reduce confusion, expand abbreviations on first
use, and break unfamiliar operations into explicit steps. Progressive disclosure keeps this usable
for beginners without padding every expert workflow.

## Non-goals

- Build an Archon clone, hosted control plane, web dashboard, database, or proprietary workflow
  language. The existing local files, Git, and controller remain the foundation.
- Replace the user's issue tracker or create a second source of truth for product priorities.
- Push, open pull requests, merge, deploy, or write to external systems without an explicit human
  authority boundary.
- Add a single broad `office` profile. Office work already has useful work-type boundaries; the
  missing piece is selection and switching UX.
- Remove verification, handoff, security, or evidence rules merely because newer models follow
  prompts better. A rule is retired only after behavioral evaluation shows that removing it does
  not regress the protected outcome.
- Optimize for GitHub stars by adding visible surface area. Adoption work should make the existing
  value legible before it makes the product larger.

## Research basis

- Long-context reliability is a real concern, but no source establishes a universal occupancy
  threshold. [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/),
  [NoLiMa](https://arxiv.org/abs/2502.05167), and
  [Context Length Alone Hurts](https://aclanthology.org/2025.findings-emnlp.1264/) show positional,
  task, and model-dependent degradation. They support measurement, retrieval, and deliberate
  rollover—not a universal claim that all models work best below 25–30% context used.
- AgentSmith's finite-run controller already supplies isolated maker/checker worktrees, durable
  state, bounded retries, resource/path collision checks, and safe resume. The missing layer is a
  small scheduler and integration train; see [`docs/21-autonomous-runs.md`](../21-autonomous-runs.md).
- [Archon](https://github.com/coleam00/Archon) validates typed workflow state, resumability,
  approval nodes, worktree lifecycle management, and explicit delivery stages. Its server,
  database, dashboard, adapter breadth, and workflow DSL solve a larger problem than AgentSmith
  needs to solve now.
- Doctor already detects duplicate global and project cores, but detection has not yet become an
  easy mental model or switching workflow; see
  [`feedback/0006-effective-global-and-project-context-duplication.md`](../feedback/0006-effective-global-and-project-context-duplication.md).

## Decision map

### Frontier

- [ ] **Context-signal contract** — What replaces the hard-coded 25–30% guidance in prose,
  status lines, and the opt-in nudge hook while preserving useful early-handoff behavior?;
  blocked by: none
- [ ] **Installation and profile state contract** — Which small, repository-owned state artifact
  and CLI verbs make global, project, layered, and self-contained installs understandable and make
  profile changes safe?; blocked by: none
- [ ] **Orchestration contract** — What is the minimum task-DAG, worktree, resume, and integration
  state needed above `autonomous-run.py`, and where do human authority gates remain?;
  blocked by: none
- [ ] **Marketing message hierarchy** — Which primary audience, painful job, proof points, and
  category language should lead the README/site/content without overstating present capability?;
  blocked by: none

### Blocked

- [ ] **Profile interaction design** — How should users recommend, explain, add, remove, and switch
  profiles without rerunning opaque install commands?; blocked by: Installation and profile state
  contract
- [ ] **Extension-development profile** — What quality gates belong in a new
  `agent-extension-dev` profile without duplicating `software-dev` or creator-skill knowledge?;
  blocked by: Installation and profile state contract
- [ ] **Multi-worktree scheduler** — How are ready tasks dispatched in parallel while path,
  resource, branch, and budget conflicts stay deterministic?; blocked by: Orchestration contract
- [ ] **Integration train** — How are independently verified commits rebased or merged, retested as
  a composition, and presented for human merge/PR approval?; blocked by: Orchestration contract,
  Multi-worktree scheduler
- [ ] **Long-term development lifecycle** — How do discovery, accepted specs, task execution,
  integration, CI, release, observation, maintenance, and harness feedback form one documented
  operating loop?; blocked by: Profile interaction design, Integration train
- [ ] **Release and launch slice** — Which decisions and implementation tickets form the next
  coherent release, and which marketing claims become true only after it ships?; blocked by:
  Context-signal contract, Installation and profile state contract, Orchestration contract,
  Marketing message hierarchy

### Fog

- Whether the next coherent release should be numbered `v0.4` or held for a larger version boundary.
- Whether orchestration state should be committed, local-only, or split into a committed contract
  plus local execution state.
- The cost and model coverage of a repeatable context-reliability evaluation for Codex, Claude,
  and future runtimes.
- Whether the first integration train should create a local candidate branch only or optionally
  prepare a pull-request body without posting it.
- Whether marketing needs a standalone website now, or a strong README, worked examples, demo, and
  launch content first.

## Decision index

- [Context research](#research-basis): remove the universal 25–30% performance claim; keep context
  visibility and deliberate handoffs, then calibrate interventions by model, runtime, and task.
- [`docs/07-how-to-pick-a-profile.md`](../07-how-to-pick-a-profile.md): keep distinct office
  profiles (`data-crunching`, `document-creation`, `marketing-outreach`, `general-admin`) and make
  their selection easier instead of collapsing their different quality gates.
- [`docs/21-autonomous-runs.md`](../21-autonomous-runs.md): extend the existing finite-run
  controller with coordination and integration rather than introducing a second execution engine.
- [Archon comparison](#research-basis): borrow typed state, resume, approval, worktree lifecycle,
  and delivery-stage ideas; explicitly reject platform-scale infrastructure for this update.
- [Product boundary](#destination): describe AgentSmith today as an agent-native SDLC harness; use
  stronger "complete SDLC system" language only when integration and lifecycle evidence exists.
- [Audience and language](#destination): lead with a learning path for technically curious
  first-time builders and provide a faster experienced-developer path; use friendly, collaborative,
  plain international English with useful analogies, expanded abbreviations, and explicit steps.
- [`skills/grill-with-docs/SKILL.md`](../../skills/grill-with-docs/SKILL.md): use repository-native
  context and ADRs for fuzzy single-session decisions; retain Wayfinder for multi-session efforts.

## Explicit deferrals

- Hosted or team-server orchestration: revisit only after local multi-run use proves a concrete
  synchronization problem that files and Git cannot solve.
- Cross-repository portfolios: the first scheduler coordinates one repository.
- Automatic remote writes and deployment: retain human approval for push, PR, merge, release, and
  production changes.
- A visual workflow builder or large built-in workflow catalog: prove a small typed contract first.
- A general plugin marketplace: unrelated to the installation/profile and SDLC gaps in scope.
- Model-specific instruction forks: prefer behavioral evaluation and dynamic configuration before
  duplicating the core by model name.

## Suggested delivery slices

| Slice | Outcome | Why this order |
|---|---|---|
| 1. Evidence correction | Context policy is accurate, configurable, and tested | Removes a false universal claim before amplifying the product |
| 2. Operability | Persistent project topology, profile explain/recommend/switch UX, and `agent-extension-dev` | Users need to understand the harness before more modes are added |
| 3. Coordination | Typed work graph and parallel dispatch through existing finite runs | Reuses the trusted controller and makes multi-hour work manageable |
| 4. Integration | Deterministic composition, cross-run verification, resume, and human handoff | Parallel output is only useful when it can land safely |
| 5. SDLC story | End-to-end lifecycle docs, examples, and recurring capability review | Makes the system teachable and keeps it current |
| 6. Marketing | Positioning, demo, comparison, launch assets, and content cadence | Markets verified capability and evidence rather than promises |

Marketing discovery can run beside slices 1–4. Claims and launch assets that depend on new
features wait until those features pass their end-to-end gates.

## Acceptance and evidence

- Every normative 25–30% statement is removed or converted into historical/research context. The
  UI still exposes context use, and any automated nudge is explicitly configurable and documented
  as a heuristic. A guard test prevents the universal claim from returning.
- A new user can inspect an installation and answer, from one command: where the core comes from,
  which profiles are active, whether the project is self-contained or layered, what is duplicated,
  and the exact safe action to change it.
- A technically curious person with no development background can complete a clean first project
  from the beginner path and explain what the major commands changed. An experienced developer can
  reach the reference setup without being forced through the teaching material.
- Behavioral evaluation covers tone and teaching quality: friendly collaboration, plain
  international English, a short analogy where useful, abbreviation expansion, reason before
  command, and step-by-step explanation for unfamiliar operations. These are tested outcomes, not
  extra paragraphs added blindly to the static core.
- Profile switching updates instructions and verification presets together, shows the proposed
  change before writing, preserves foreign content, and is reversible through the existing update
  safety model.
- `agent-extension-dev` assembles within the leanness budget and proves the relevant skill/plugin
  manifest, validation, fixture, compatibility, documentation, and install-path gates without
  copying creator manuals into static context.
- Office workflows have copy-ready installation recipes for data + spreadsheet, document + Word,
  presentation/design, research, and marketing combinations, including when MCP/skills are useful
  and when they are unnecessary.
- In a fixture repository, two independent implementation tickets run concurrently in separate
  worktrees; a conflicting ticket waits; an interrupted run resumes; each result retains its
  evidence and lineage.
- The integration train composes the verified results in a deterministic order, reruns the full
  project gate on the composed candidate, stops on conflict or regression, and never pushes or
  merges without authorization.
- The lifecycle guide traces one feature from discovery through accepted spec, tickets, parallel
  execution, integration, CI/release approval, observation, and feedback into the harness.
- Marketing claims map to repository evidence. At minimum: revised README opening, one concise
  architecture diagram, one real end-to-end demo, a comparison page, and a small founder-led
  launch/content sequence. No claim depends only on an agent-generated assertion.
- Repository-wide verification passes on macOS, Linux, and Windows fixtures, with end-to-end tests
  added for every new state transition and recovery boundary.

## Decision-ticket drafts

### Context-signal contract

**Question:** Should the percentage hook be disabled by default, retain a neutral configurable
default, or use model/runtime calibration data—and what exact user-visible behavior follows?

**Blocked by:** none

**Resolution:** Open. The universal 25–30% quality claim is already rejected; this decision chooses
the replacement behavior, migration, and evaluation method.

### Installation and profile state contract

**Question:** Should `.agentsmith/project.json` become the canonical description of scope,
core/profile topology, enabled capabilities, and task mode, with current manifests migrated into it
or referenced by it?

**Blocked by:** none

**Resolution:** Open. The answer must cover fresh, legacy, global, project, layered, and
self-contained installs without taking ownership of foreign configuration.

### Orchestration contract

**Question:** What minimal schema and state machine can represent ticket dependencies, scopes,
resources, budgets, run lineage, readiness, integration order, and escalation while reusing
`autonomous-run.py` unchanged where possible?

**Blocked by:** none

**Resolution:** Open. A local, file-backed, one-repository design is the starting constraint.

### Marketing message hierarchy

**Question:** Who is the first audience, what painful job should AgentSmith own for them, which
three proof points earn belief, and what category language distinguishes it from agent CLIs and
workflow platforms?

**Blocked by:** none

**Resolution:** Open. The accepted audience shape has two paths: technically curious first-time
builders first, and experienced developers seeking a strong starting environment second. The
remaining decision chooses the painful job, proof hierarchy, and category language for those paths.

### Release and launch slice

**Question:** Which accepted decisions and implementation tickets form one releasable promise, and
which later capabilities stay visibly on the roadmap?

**Blocked by:** Context-signal contract, Installation and profile state contract, Orchestration
contract, Marketing message hierarchy

**Resolution:** Open.

## Implementation-ticket drafts

> These are candidate work items. Final scopes are created only after this spec is accepted and do
> not reuse the decision ticket.

### Replace the universal context threshold with an evidence-calibrated policy

- **Outcome:** Context guidance and optional automation reflect model/task uncertainty accurately.
- **In scope:** research artifact, prose/statusline/hook behavior, migration note, regression test,
  and a repeatable calibration protocol.
- **Out of scope:** benchmarking every model before release.
- **Depends on:** accepted Context-signal contract.
- **Acceptance/evidence:** context-policy acceptance items above plus full verification.

### Make installation topology and profile changes self-explanatory

- **Outcome:** Users can see and safely change global/project/layered topology and active profiles.
- **In scope:** project-state contract, inspection and change UX, dry-run, migration, rollback,
  verification-preset synchronization, docs, and fixtures.
- **Out of scope:** ownership of arbitrary user runtime configuration.
- **Depends on:** accepted Installation and profile state contract.
- **Acceptance/evidence:** fresh and legacy fixture matrix, duplicate-core scenario, reversible
  profile switch, and full verification.

### Add the `agent-extension-dev` profile

- **Outcome:** Skill, plugin, hook, MCP, and harness-extension work has explicit completion gates.
- **In scope:** profile, verify preset, selection guidance, recommended creator skills, examples,
  leanness checks, and assembly/install tests.
- **Out of scope:** embedding full skill/plugin authoring manuals in the profile.
- **Depends on:** installation/profile UX contract.
- **Acceptance/evidence:** one skill and one plugin fixture pass end to end; malformed manifests and
  broken installation paths fail for the expected reasons.

### Publish office-work recipes without creating an omnibus profile

- **Outcome:** A user can choose a profile stack and optional capabilities for common office work.
- **In scope:** data/MCP/spreadsheet, document/Word, presentation/design, research, marketing, and
  general-admin recipes; switching examples and rendered-output verification.
- **Out of scope:** bundling or authenticating every third-party connector.
- **Depends on:** installation/profile UX contract.
- **Acceptance/evidence:** copy-ready recipes validate against supported CLI options and point to
  the correct end-to-end quality gates.

### Add a typed local work graph

- **Outcome:** Several accepted tickets can be represented with dependencies, scopes, resources,
  budgets, and expected evidence.
- **In scope:** schema/template, validation, status derivation, migration/versioning, and CLI
  inspection.
- **Out of scope:** execution, remote tracker synchronization, and cross-repository graphs.
- **Depends on:** accepted Orchestration contract.
- **Acceptance/evidence:** invalid graphs fail closed; ready/blocked/conflicting nodes derive
  deterministically from fixtures.

### Dispatch ready work through isolated autonomous runs

- **Outcome:** Ready non-conflicting nodes run in parallel through the existing maker/checker
  controller and can resume after interruption.
- **In scope:** orchestration command, worktree/run lifecycle, concurrency cap, budgets, event log,
  failure propagation, resume, and cleanup policy.
- **Out of scope:** automatic integration, push, PR, merge, or deployment.
- **Depends on:** typed local work graph.
- **Acceptance/evidence:** parallel, conflicting, failed, cancelled, and resumed fixture runs leave
  auditable state and no orphaned AgentSmith-owned worktrees.

### Add a deterministic local integration train

- **Outcome:** Successful task branches become one verified local release candidate with a human
  approval handoff.
- **In scope:** ordering, ancestry and cleanliness checks, conflict handling, composed verification,
  evidence lineage, rollback, and prepared handoff/PR text.
- **Out of scope:** remote writes, auto-merge, release publishing, and deployment.
- **Depends on:** multi-worktree scheduler.
- **Acceptance/evidence:** two compatible branches compose and pass; conflicts/regressions stop;
  source branches and research artifacts remain recoverable.

### Document the long-term agent-native development lifecycle

- **Outcome:** Operators know how to move from idea to maintained release across sessions and agents.
- **In scope:** lifecycle guide, architecture diagram, worked repository example, operating modes,
  role/model selection as a dated example rather than permanent policy, and failure recovery.
- **Out of scope:** claiming that AgentSmith owns external CI/CD or trackers.
- **Depends on:** profile UX and integration train.
- **Acceptance/evidence:** a clean-room reader can follow one example end to end and every command
  and artifact exists in the shipped product.

### Establish recurring model-capability and harness-deletion reviews

- **Outcome:** Stronger models can simplify AgentSmith when evidence shows a guard is redundant.
- **In scope:** a dated capability matrix, behavioral ablations, protected-outcome criteria,
  deprecation rules, and a quarterly or release-bound review checkpoint.
- **Out of scope:** deleting rules because of vendor benchmarks or a single impressive session.
- **Depends on:** context calibration protocol and existing `agentsmith evaluate` framework.
- **Acceptance/evidence:** at least one rule/heuristic is evaluated with harness-on versus
  harness-removed trials, and the record supports either retention or bounded removal.

### Build the truthful marketing foundation and launch package

- **Outcome:** AgentSmith's audience, category, value, and proof are understandable in minutes.
- **In scope:** separate beginner and experienced-developer journeys, positioning brief, message
  hierarchy, voice guide, README rewrite, comparison page, beginner-safe demo script, architecture
  visual, launch post, and a small recurring founder-content plan.
- **Out of scope:** paid acquisition, a large website rebuild, or unsupported competitor claims.
- **Depends on:** accepted Marketing message hierarchy; feature-dependent claims also depend on the
  relevant implementation evidence.
- **Acceptance/evidence:** every product claim links to a test, document, demo, or repository
  artifact; comprehension testing includes at least one technically curious non-developer and one
  experienced developer, and both can explain the product, its boundary, and the next step after
  reviewing their respective path.
