# Evidence-backed feature inventory: AgentSmith

**Status:** Step 4 confirmed by the operator on 2026-09-17  
**Date:** 2026-09-17  
**Primary segment:** Technically curious first-time builder with a real professional problem  
**Secondary lens:** Agentic developer seeking a portable quality baseline

## Evaluation standard

This inventory separates what exists from what is strategically important. A feature is not a
differentiator merely because AgentSmith has it. Each entry names:

- the customer use case it supports;
- the buying motivations it activates;
- the available repository evidence;
- whether it is a differentiator, expected capability, or gap;
- the claim boundary that prevents marketing from overstating it.

The current product evidence comes from the [README](../../README.md),
[built-in inventory](../12-whats-built-in.md), [compatibility contract](../22-compatibility-contract.md),
[verification model](../03-verify-means-evidence.md), and passing repository verification.

## Core features

### 1. Canonical operating agreement and profile assembly

| Attribute | Detail |
|---|---|
| **What it is** | A universal core plus one or more work-type profiles assembled into the project's canonical `AGENTS.md`; Claude receives an equivalent generated `CLAUDE.md` |
| **Customer use cases** | Start responsibly; standardize agent behavior; switch work types without rewriting the full rule set |
| **Customer benefit** | The user can inspect one source of working rules while each project receives a definition of “done” that fits its work |
| **Buying motivations** | Get Comfort; Achieve Cleanliness/Hygiene; Save Time; Avoid Effort |
| **Evidence** | Assembly, idempotence, adapter, and token-budget tests; ten shipped profiles |
| **Competitive status** | **Differentiating bundle, not unique primitive.** Instruction files are common; canonical assembly plus work-type gates and ownership lifecycle is less common |
| **Claim boundary** | Do not imply every supported client enforces instructions identically |

### 2. Project-owned verification and evidence receipts

| Attribute | Detail |
|---|---|
| **What it is** | `.harness/verify.conf` defines ordered project checks; `agentsmith verify` runs them and can write redacted, hashed receipts with Git and phase context |
| **Customer use cases** | Prove a change; reduce repair loops; preserve evidence across handoffs; give maker/checker runs a deterministic gate |
| **Customer benefit** | “Done” becomes a repeatable project command and an inspectable artifact rather than the agent's confidence |
| **Buying motivations** | Get Comfort; Achieve Cleanliness/Hygiene; Escape Pain; Save Time |
| **Evidence** | Verification-runner and receipt tests; repository's own 25-phase verification chain |
| **Competitive status** | **Potential lead differentiator**, especially receipts and explicit evidence classes |
| **Claim boundary** | Current configuration does not adapt reliably to every project. A green command proves only the phases it actually covers; end-to-end and judgment evidence may remain separate |

### 3. Durable specifications, handoffs, research, and feedback

| Attribute | Detail |
|---|---|
| **What it is** | Repository-owned skills and templates for specifications, decision records, session handoffs, research notes, and post-incident system improvement |
| **Customer use cases** | Preserve context; resume long work; avoid repeating failed approaches; evolve the harness from observed failures |
| **Customer benefit** | The project remembers approved intent, produced evidence, and the next step even when the chat does not |
| **Buying motivations** | Save Time; Avoid Effort; Get Comfort; Achieve Cleanliness/Hygiene |
| **Evidence** | Shipped skills, format templates, handoff tests, feedback records, and repository examples |
| **Competitive status** | **Differentiating system design.** Individual memory files are common; the closed loop from incident → bounded harness change → non-regression evidence is stronger |
| **Claim boundary** | Multiple artifacts can themselves create cognitive load; the primary continuity path still needs simplification and user evidence |

### 4. Reversible installation, inspection, update, and ownership

| Attribute | Detail |
|---|---|
| **What it is** | Cross-platform installer, dry run, doctor, managed blocks, ownership tracking, uninstall, staged semantic-version update plans, integrity binding, and rollback receipts |
| **Customer use cases** | Understand what AgentSmith owns; avoid configuration collisions; update safely; remove it without destroying foreign settings |
| **Customer benefit** | The user can see and reverse harness changes instead of trusting a one-way setup script |
| **Buying motivations** | Get Comfort; Achieve Cleanliness/Hygiene; Save Time; Avoid Effort |
| **Evidence** | Native Ubuntu/macOS/Windows tests, ownership and idempotence tests, update planning/apply/rollback tests |
| **Competitive status** | **Strong technical differentiator** for a portable open-source harness |
| **Claim boundary** | Powerful lifecycle machinery does not automatically make first-use choices easy |

### 5. Explicit multi-client compatibility contract

| Attribute | Detail |
|---|---|
| **What it is** | A machine-readable registry separates instruction discovery, skills/tools, and native runtime integration across 16 targets; Claude Code and Codex are the native integrations |
| **Customer use cases** | Use one operating model across clients; inspect unsupported versus unverified capabilities; avoid client-specific marketing guesses |
| **Customer benefit** | The user sees which parts travel and which parts require a client-specific adapter or remain unproven |
| **Buying motivations** | Get Comfort; Save Time; Achieve Cleanliness/Hygiene; Avoid Effort |
| **Evidence** | Registry schema, strict conformance tests, CLI compatibility report, and isolated native-client evaluation runner |
| **Competitive status** | **Differentiating transparency.** Multi-client support is not unique; separating capability claims from evidence is meaningful |
| **Claim boundary** | Fourteen targets are certification targets, not 14 equally verified integrations. Native evidence is deepest for Claude Code and Codex |

### 6. Safety, consent, and secret guardrails

| Attribute | Detail |
|---|---|
| **What it is** | Cautious permission defaults, explicit trusted opt-in, first-external-write consent, managed organization policy, secret scanning, unattended-work denylist, and prompt-injection posture |
| **Customer use cases** | Bound agent scope; prevent accidental external actions; keep credentials out of tracked files; operate on shared or client machines |
| **Customer benefit** | Consequential actions become explicit and some non-negotiable rules are enforced mechanically |
| **Buying motivations** | Get Comfort; Escape Pain; Achieve Cleanliness/Hygiene; Save Money |
| **Evidence** | Behavioral evaluation scenarios, secret-scanner tests, tracker-consent tests, and safety migration tests |
| **Competitive status** | **Differentiating cross-client governance layer**, though native agent sandboxes provide parts of the same protection |
| **Claim boundary** | Agent safety is not product security. These controls do not prove that generated software is secure |

### 7. Bounded autonomous maker/checker runs

| Attribute | Detail |
|---|---|
| **What it is** | Accepted specs feed finite maker/checker attempts in isolated worktrees with attempt caps, scope/resource collision checks, durable state, stop/resume, and no push or merge authority |
| **Customer use cases** | Run one well-specified item unattended; isolate parallel work; escalate instead of looping forever |
| **Customer benefit** | Autonomy is bounded by a contract and independent checking rather than broad permission alone |
| **Buying motivations** | Save Time; Get Comfort; Avoid Effort; Achieve Cleanliness/Hygiene |
| **Evidence** | Autonomous state and run suites, including collision, mutation, retry, interruption, and stale-recovery tests |
| **Competitive status** | **Advanced capability with partial parity.** Archon and other systems also use worktrees and approval gates; AgentSmith's conservative local boundary is distinctive but not unique |
| **Claim boundary** | Not an autonomous software factory. Current authority ends at local commits; controller isolation is macOS/Linux only |

## Supporting features

| Feature | Customer role | Evidence | Competitive status | Buying motivations |
|---|---|---|---|---|
| Ten work-type profiles | Supplies quality gates for software, DevOps, documents, data, research, design, administration, marketing, security, and unattended loops | Profile assembly and leanness tests | Differentiating breadth; profile systems themselves are not unique | Get Comfort; Avoid Effort |
| Bundled dynamic skills | Loads planning, verification, handoff, research, feedback, and writing guidance only when needed | Compatibility metadata and skill-specific tests | Expected in modern agent ecosystems; curated small pack is a design advantage | Avoid Effort; Save Time |
| Skills, MCP, and hook installation | Connects supported native client surfaces while preserving foreign configuration | Idempotence, ownership, and adapter tests | Table stakes with unusually explicit ownership | Save Time; Achieve Cleanliness/Hygiene |
| `doctor` | Shows effective instruction chain, duplicate context, safety, skills, MCP, hooks, scanner, and runtime ownership | Doctor test suite | Strong supporting differentiator | Get Comfort; Save Time |
| Behavioral `evaluate` runner | Tests installed Claude Code and Codex behavior in isolated repositories with explicit budgets | Evaluation schema and fake-client tests | Differentiating evidence posture | Get Comfort; Achieve Cleanliness/Hygiene |
| Integration checkpoint validator | Validates structured package checkpoints without installing or launching the integration | Integration-validation tests | Specialized support feature | Get Comfort; Escape Pain |
| Status line and context signal | Makes model, directory, and context information visible where supported | Status-line and context-nudge tests | Convenience feature, not strategic differentiation | Get Comfort |
| Worked examples and documentation | Shows completed profile configurations and explains safety, verification, and operating modes | Six repository examples and linked docs | Expected; current beginner path remains incomplete | Avoid Effort; Save Time |
| Standard-library Python core | Reduces dependency and cross-platform installation surface | Import guard, compilation, and native OS CI | Technical hygiene, not a hero benefit | Get Comfort; Achieve Cleanliness/Hygiene |

## Differentiation assessment

The defensible differentiation is the system, not one feature:

> **AgentSmith turns project-specific intent, working rules, evidence, and memory into a portable,
> reversible layer around the coding agent.**

### Sustainability test

| Candidate differentiator | True now? | Relevant to priority pains? | Unique or meaningfully combined? | Sustainable for 18 months? | Verdict |
|---|---|---|---|---|---|
| Evidence before assertion, including whole-chain checks | Yes as operating contract | **Very high**: verification is the lead pain | Principle is not unique; depth across profiles, receipts, and checker flows is meaningful | **Medium**: models improve, but evidence remains necessary | Lead differentiation after adaptive verification improves |
| Durable, repository-owned intent and handoff | Yes | **Very high**: lost context is second | Many tools offer memory; inspectable version-controlled continuity is a strong combination | **Medium-high** | Lead supporting differentiation |
| One canonical layer across agents | Yes, with explicit support limits | High for experienced users | Multi-client rules exist elsewhere; lifecycle and evidence contract add distinction | **Medium** as standards converge | Use as expert value, not sole moat |
| Reversible managed lifecycle | Yes | Medium during buying; high during trust evaluation | Unusually complete for a harness | **High** because safe ownership is operational work competitors must reproduce | Strong proof and trust differentiator |
| Progressive rigor and small dynamic surface | Yes architecturally | High for users rejecting heavy methodologies | Positioning combination is distinctive, not proprietary | **Medium** | Strong philosophy; needs user outcome proof |
| Explicit support evidence instead of compatibility logos | Yes | Medium–high | Meaningfully transparent | **High** if records stay current | Trust differentiator |
| Bounded autonomous local runs | Yes with limits | High as the destination; later-stage in the user journey | Partial parity with orchestration systems | **Low–medium** because platforms are converging rapidly | Visible advanced mode and continuing product priority; do not oversell current scope |
| Ten profiles / 16 targets / ten bundled skills | Yes | Low as raw counts | Counts are easy to copy and hide unequal depth | **Low** | Never lead with counts alone |

## Table stakes, differentiators, and gaps

| Classification | Features |
|---|---|
| **Table stakes** | Markdown instructions; profiles or templates; skills; MCP support; cautious client permissions; documentation; tests |
| **Current differentiators** | Reversible ownership lifecycle; evidence receipts; capability-by-capability compatibility contract; repository-owned system-evolution loop; conservative maker/checker boundaries |
| **Differentiating bundle** | Canonical rules + project-specific profiles + layered evidence + durable memory + reversible lifecycle |
| **Critical gaps** | Adaptive verification discovery; clear central/project/profile state; guided first-loop sandbox; beginner outcome evidence; simplified continuity path |
| **Future ecosystem** | AI Admin Panel as the recommended hosting and operating environment after the bridge is shipped and verified |

## Feature-to-use-case summary

| Use case | Features that carry it | Current fit |
|---|---|---|
| Start responsibly | Core/profile assembly; cautious defaults; planning skills; planned sandbox | Moderate: sandbox and choice simplification remain |
| Recover a growing project | Doctor; specifications; verification; handoff; feedback records | Moderate–strong: verification adaptation is the limiting factor |
| Standardize across agents | Canonical rules; adapters; registry; doctor; managed lifecycle | Strong for instructions; variable for skills, MCP, and hooks |
| Continue long-running work | Specifications; decisions; handoff; research; feedback | Strong architecture; primary UX needs simplification |
| Increase autonomy carefully | Accepted specs; verify command; worktrees; maker/checker; collision controls | Strong within the finite local-run boundary; not full SDLC orchestration |

## What to emphasize and downplay

### Emphasize

- Evidence that is configured for the repository and exercised at the user's real outcome.
- Durable intent and handoff across sessions.
- Reversible, inspectable changes to both the project and the harness installation.
- One portable quality layer with honest capability boundaries.
- Progressive rigor instead of a large method for every task.

### Downplay

- Raw counts of agents, profiles, skills, or tests.
- MCP and hook support without a customer problem attached.
- Autonomous-run implementation detail on the beginner path. Keep the bounded autonomous option
  visible, but teach it after the attended workflow and state its current platform and authority
  limits.
- Context percentages or model-specific advice as durable product value.
- Any suggestion that AgentSmith is a separate PromptPartner service or paid add-on.

## Decisions confirmed before Step 5

1. The differentiating bundle—canonical rules, adaptive evidence, durable memory, and reversible
   lifecycle—matches the delivery direction.
2. Customers and collaborators notice the combined system. Verification and scope control lead,
   followed by continuity, portability, and safe installation.
3. Bounded autonomous runs remain a visible product option and an improvement priority. The user
   journey begins attended, but AgentSmith should always offer a credible path to autonomy.
4. Public commercial wording may say: “Included and tailored at no additional licence cost in
   relevant PromptPartner projects.” The paid work remains the wider customer delivery.
5. Raw counts, status-line features, MCP/hook details, and autonomous implementation internals stay
   out of the main website and deck. They remain available in technical documentation.

## Proposed enhancements

- Turn adaptive verification into a named product surface before treating verification as the hero
  benefit. The first version can inspect the repository, propose phases, explain what remains
  untested, and require one end-to-end exercise.
- Add one state explanation to `doctor`: global core, project profile, generated adapters, active
  verification, and which source owns each piece.
- Instrument the first-loop sandbox around comprehension and recovery, not installation success
  alone.
- Connect GitHub attribution to PromptPartner's existing website calls to action without creating a
  separate AgentSmith service funnel.
- Use the case placeholders to identify which technical features actually changed delivery outcomes;
  remove any feature from hero messaging that no case supports.

---

**Gate passed:** the operator confirmed this feature inventory on 2026-09-17. Step 5 may proceed.
