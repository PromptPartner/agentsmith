# Marketing intake: AgentSmith

**Status:** Step 0 complete; awaiting operator confirmation before ICP synthesis
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
| First successful 30-minute outcome | Defines onboarding, demo, and activation metric | Choose one observable beginner journey and usability-test it |
| Experienced-developer priority pain | Prevents the secondary path from becoming generic | Select the strongest pain from real use: portability, quality drift, setup time, autonomy, or handoff continuity |
| Customer/user evidence | Needed for irrefutable claims | Collect permissioned quotes, before/after examples, screenshots, and repository outcomes |
| Distribution starting point | Determines format and content cadence | Choose the first channel before producing a broad content calendar |
| Commercial/support model | Changes buyer, trust, and call to action | Decide whether the near-term goal is adoption, community, services, sponsorship, or product revenue |

## Planned marketing artifacts

| Step | Artifact | Status |
|---|---|---|
| 1 | Ideal customer profile (ICP) synthesis for the primary path, with secondary-path differences | Waiting for intake confirmation |
| 2 | Pain-point analysis | Not started |
| 3 | Value Proposition Canvas | Not started |
| 4 | Evidence-backed feature inventory | Not started |
| 5 | Competitive alternatives analysis | Not started |
| 6 | Positioning statement and strategic narrative | Not started |
| 7 | Content pillars | Not started |
| 8 | Feature → benefit → value map | Not started |
| 9 | Headlines, taglines, and layered messaging | Not started |
| 10 | Proof points and product vision | Not started |
| Final | Consolidated marketing framework and launch plan | Not started |

## Assumptions requiring confirmation

- The technically curious first-time builder is the primary communication path, while experienced
  developers are an important secondary path rather than a co-equal message in every asset.
- The near-term call to action is to try AgentSmith on a real local project, not to purchase a
  hosted service.
- Trust, learning, and control matter more initially than raw speed or “replace your developers”
  claims.
- GitHub and founder-led technical content are likely initial discovery surfaces, but the primary
  channel has not been selected.

## Questions before Step 1

1. What frustrating event should make a technically curious beginner look for AgentSmith?
2. What should that person have produced or understood after their first successful 30 minutes?
3. For an experienced developer, which pain should lead: inconsistent agent quality, repeated
   setup, weak verification, long-session continuity, or safe autonomy?
4. Which real user stories, screenshots, quotes, or outcome metrics can we use with permission?
5. Where should initial discovery happen: GitHub, LinkedIn, technical communities, workshops, or
   somewhere else?

## Proposed intake enhancements

- Observe one first-time builder completing the current install and first task; record where they
  hesitate rather than asking whether it felt easy.
- Build a proof inventory that links every planned public claim to its exact repository check,
  demonstration, or user source.
- Record one short beginner journey and one expert journey using the same project so the two paths
  can be compared without presenting two different products.
