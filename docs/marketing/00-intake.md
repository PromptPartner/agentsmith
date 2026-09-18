# Marketing intake: AgentSmith

**Status:** Complete; Steps 0–10 and final consolidation confirmed on 2026-09-17
**Date:** 2026-09-17

## Materials reviewed

| Material | What it establishes | Status |
|---|---|---|
| [`README.md`](../../README.md) and [`INSTALL.md`](../../INSTALL.md) | Current product description, install paths, safety modes, supported surfaces | Reviewed |
| [`01-harness-philosophy.md`](../01-harness-philosophy.md) | Product belief: reliable agent behavior comes from the model plus its harness | Reviewed |
| [`03-verify-means-evidence.md`](../03-verify-means-evidence.md) | Evidence standard and maker/checker distinction | Reviewed |
| [`05-operating-modes.md`](../05-operating-modes.md) | Attended sessions, finite autonomous runs, and recurring loops | Reviewed |
| [`12-whats-built-in.md`](../12-whats-built-in.md) | Profiles, skills, hooks, verification, and bundled capabilities | Reviewed |
| [`22-compatibility-contract.md`](../22-compatibility-contract.md) | Evidence-backed support boundary across coding agents | Reviewed |
| [`agentsmith-next-stage.md`](../specs/agentsmith-next-stage.md) | Approved roadmap direction, product boundary, audience paths, and open decisions | Reviewed |
| [PromptPartner website](https://promptpartner.ai/) | Current service model, delivery method, calls to action, governance layer, and role of the coding and agent harness | Reviewed 2026-09-17 |
| Profiles, six worked examples, architecture image, CI, compatibility registry, and native-client evaluation records | Repository-owned proof surfaces | Inventoried; proof strength still to be scored |

## Initial product understanding

**Product:** AgentSmith is a portable, local harness that gives coding agents shared operating
rules, work-specific quality gates, evidence-based verification, safe update/rollback behavior,
and durable handoffs.

**Initial value hypothesis:** It helps people begin and continue agentic coding in an environment
that teaches disciplined work while reducing the chance that an agent silently skips planning,
verification, documentation, or safety boundaries.

**Current-description gap:** “Shared working rules for coding agents” is accurate but undersells
the existing local software development lifecycle (SDLC) primitives. “Complete autonomous SDLC
platform” would overstate the missing multi-ticket scheduling, integration train, and remote
delivery stages. The current defensible category hypothesis is **agent-native SDLC harness** or
**portable quality and control layer for agentic coding**.

## Accepted audience shape

### Primary learning path: technically curious first-time builders

People comfortable with technology who may never have developed software. Examples include
designers, operators, founders, and domain experts opening Claude Code or Codex for the first time.
They need a safe starting environment that also teaches a limited, useful mental model of what is
happening.

### Secondary path: experienced developers

Developers who already understand repositories, tests, and delivery workflows but want a strong,
inspectable starting point across coding agents. They need direct reference material and the
ability to skip teaching layers without losing the controls.

These paths share the product but should not be forced through identical onboarding or copy.

## Accepted voice and teaching constraints

- Friendly and collaborative, without sounding childish or overexcited.
- Plain international English for readers who may not be native English speakers.
- Short sentences and one main idea per sentence.
- Explain why before how.
- Use a brief analogy when it makes an unfamiliar idea easier to hold.
- Expand abbreviations the first time they appear.
- Explain unfamiliar or consequential operations step by step.
- Use progressive disclosure: beginners can learn enough to proceed; experts can move directly to
  the reference path.
- Avoid unexplained jargon, idioms, slang, and unsupported superlatives.

## Defensible proof available today

| Proof surface | Defensible claim | Current limitation |
|---|---|---|
| Standard-library Python installer and native CI | The core installer runs without third-party Python packages and is tested across macOS, Linux, and Windows fixtures | Fixture support is not the same as live validation for every listed client |
| Canonical `AGENTS.md` with generated adapters | Projects can keep one canonical operating agreement across supported instruction surfaces | Native configuration is deeper for Claude and Codex than for other clients |
| Profiles and full verification gate | Different work types receive explicit definitions of done and repository-owned checks | Profile selection and switching are not yet easy enough |
| Staged updates and rollback receipts | Managed updates are planned, fingerprinted, applied at an approval boundary, and recoverable | The update flow needs simpler beginner-facing explanation |
| Behavioral evaluation for Claude and Codex | Native clients can be evaluated on observable behavior, not only configuration presence | Evaluation evidence does not yet prove beginner comprehension |
| Finite autonomous runs | Bounded maker/checker runs use isolated worktrees, attempt caps, durable state, and safe resume | Multi-ticket scheduling and integration are planned, not shipped |

## Competitive alternatives to investigate

- Use Claude Code, Codex, or another coding agent with no additional harness.
- Maintain a hand-written `AGENTS.md` or `CLAUDE.md` file.
- Install a focused agent workflow such as Superpowers.
- Use methodology packs such as BMAD or GSD.
- Use a broader workflow platform such as Archon or OpenHands.
- Build and maintain a private team harness.

This is an intake list, not a comparison verdict. Strengths, weaknesses, and current claims require
source-backed competitive research before publication.

## Known constraints

- Marketing claims must link to repository evidence, real demonstrations, or user evidence.
- Beginner suitability is a target requirement, not yet a proven customer outcome.
- The project is open source and currently has limited adoption proof relative to larger projects.
- Product terminology must distinguish instructions, profiles, skills, hooks, Model Context
  Protocol (MCP) connections, and autonomous runs without making the first page feel like a glossary.
- The marketing lane may describe shipped behavior and clearly labeled roadmap direction, but may
  not present planned orchestration as current capability.

## Information gaps

| Gap | Why it matters | Proposed way to resolve it |
|---|---|---|
| Beginner buying/activation trigger | Determines which problem the opening message should name | Operator experience plus 3–5 short user conversations |
| First successful 30-minute outcome | Defines onboarding, demo, and activation metric | Research supports a prepared sandbox first, then the user's real repository; confirm and usability-test it |
| Experienced-developer priority pain | Prevents the secondary path from becoming generic | Select the strongest pain from real use: portability, quality drift, setup time, autonomy, or handoff continuity |
| Customer/user evidence | Needed for irrefutable claims | Use AI Admin Panel as the named flagship; build a permission-safe portfolio of anonymous AI-foundation, Claude, skills, and plugin cases; publish only supported counts and outcomes |
| Distribution starting point | Determines format and content cadence | Choose the first channel before producing a broad content calendar |
| Lead-magnet conversion path | Connects GitHub adoption to the existing PromptPartner offer | Keep AgentSmith fully open; route interested teams into PromptPartner's current audit and build journey without creating a separate AgentSmith service |

## Planned marketing artifacts

| Step | Artifact | Status |
|---|---|---|
| 1 | Ideal customer profile (ICP) synthesis for the primary path, with secondary-path differences | Confirmed 2026-09-17 |
| 2 | Pain-point analysis | Confirmed 2026-09-17 |
| 3 | Value Proposition Canvas | Confirmed 2026-09-17 |
| 4 | Evidence-backed feature inventory | Confirmed 2026-09-17 |
| 5 | Competitive alternatives analysis | Confirmed 2026-09-17 |
| 6 | Positioning statement and strategic narrative | Confirmed for now 2026-09-17; external positioning review planned |
| 7 | Content pillars | Confirmed 2026-09-17 |
| 8 | Feature → benefit → value map | Confirmed 2026-09-17 |
| 9 | Headlines, taglines, and layered messaging | Confirmed 2026-09-17 |
| 10 | Proof points and product vision | Confirmed 2026-09-17 |
| Final | Consolidated marketing framework and launch plan | Confirmed 2026-09-17 |

## Confirmed direction and remaining assumptions

- **Confirmed:** the technically curious first-time builder is the primary communication path,
  while experienced developers are an important secondary path rather than a co-equal message in
  every asset.
- **Confirmed:** initial go-to-market should focus on professionals with a real work problem. Students
  and hobbyists remain an important later learning path, not an excluded audience.
- The near-term call to action is to complete one open, verified sandbox loop and then apply
  AgentSmith to a real local project—not to purchase a hosted service.
- **Confirmed:** trust, limited learning, and control matter more initially than raw speed or
  “replace your developers” claims.
- **Confirmed:** Reddit is the first listening and discovery community. GitHub should be the proof
  and conversion surface. LinkedIn may distribute evidence-backed material, but should not be
  treated as a reliable source of market truth.

## Operator answers received on 2026-09-17

1. **Beginner trigger:** someone says non-developers should not use Claude Code or Codex; the user
   wants to learn only the programming needed for the task; an agent changes more than requested;
   one-shot “vibe coding” turns into an endless repair loop; the user discovers too late that a
   specification should have come first; or prior coding-agent output is poor.
2. **Expectation reset:** the first working draft can be fast, but reliable AI-assisted engineering
   takes more planning, testing, review, and iteration than the demo suggests. The 30-minute
   activation outcome still needs to be chosen and tested.
3. **Experienced-developer pain:** all five candidate pains matter—inconsistent quality, repeated
   setup, weak verification, long-session continuity, and safe autonomy. Research should determine
   the lead pain instead of forcing an unsupported ranking.
4. **Available proof:** AI Admin Panel has been developed with this approach for more than eight
   months and is entering customer release; it is approved as the named flagship case. The operator
   also reports more than ten PromptPartner customer projects, including anonymous engagements where
   PromptPartner built the AI foundation with Claude, skills, plugins, and related workflow layers.
   The duration, customer count, and outcomes are first-party statements until backed by repository
   evidence or permissioned customer material.
5. **Discovery:** begin with Reddit and other communities where practitioners describe real
   failures. Use existing AgentSmith citations and find independent people who reference, test, or
   challenge those sources. Treat LinkedIn claims cautiously.
6. **Audience sequence:** professionals come first because they have an immediate work problem and a
   clearer path to PromptPartner. Students and hobbyists still matter because today's agentic-coding
   environment resembles an early internet adoption phase: the category is not yet settled, and
   learning users may become future practitioners and advocates.
7. **Business goal:** use AgentSmith to create PromptPartner leads and credibility while increasing
   GitHub adoption. It is an open-source lead magnet and a free delivery component included and
   tailored where relevant in PromptPartner projects—not a separate paid offer. The repository
   should remain useful without requiring an email address.
8. **Activation research:** the strongest current recommendation is a prepared, disposable template
   repository for the first verified loop, followed immediately by an “apply this to your project”
   path. This is a researched hypothesis, not yet user-tested evidence.

## Proposed intake enhancements

- Observe one first-time builder completing the current install and first task; record where they
  hesitate rather than asking whether it felt easy.
- Build a proof inventory that links every planned public claim to its exact repository check,
  demonstration, or user source.
- Record one short beginner journey and one expert journey using the same project so the two paths
  can be compared without presenting two different products.
