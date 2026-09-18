# First Verified Loop Wave: Brainstorm / Discovery Notes

Date: 2026-09-17 · Goal: Define one implementation-ready product wave that turns the approved
AgentSmith strategy into a complete first verified loop before the next context reset.

## Summary / key decisions

- The operator wants a larger, spec-led implementation wave while enough context and token budget
  remain to resolve it properly.
- The approved marketing framework makes adaptive verification, active-state clarity, guided first
  use, simplified continuity, and public proof the connected product sequence.
- Working recommendation: treat these as one vertical product wave named **First Verified Loop**,
  with separate atomic delivery slices and evidence gates.
- The presentation and launch-package architecture may be planned in parallel, but public claims
  remain limited to shipped and linked evidence.
- The wave ends with the updated documentation and one public proof demonstration, not merely a
  locally working implementation.
- The active-state view derives from the existing `.agentsmith/state.json`, instruction chain, and
  verification config. No second project-state file is added.
- The public sandbox uses a dependency-free launch-readiness checker with an intentional `any`
  versus `all` defect. It works in disposable copies across supported operating systems.
- Parallel multi-ticket orchestration and the integration train remain the next wave rather than
  entering this release.

## Q&A log

### Q0 — Planning mandate

- **Asked:** What should follow the completed marketing foundation?
- **Captured:** Plan a larger implementation wave from a durable specification. Use the remaining
  session capacity to settle the work before the scheduled context reset.
- **Flags:** Resolved by Q1 and repository review.

### Q1 — Release boundary

- **Asked:** Should the implementation wave finish with the public proof demonstration and updated
  documentation, or stop once the local product experience works?
- **Captured:** Follow the recommendation: include updated documentation and the public proof
  demonstration in the wave's definition of done.
- **Flags:** Resolved: use the dependency-free Python launch-readiness fixture defined in the
  accepted spec.

## Open flags (pending input)

- None. Implementation findings may create bounded technical decisions, but the product boundary,
  sequence, proof requirement, and deferred work are settled in
  `docs/specs/first-verified-loop-wave.md`.
