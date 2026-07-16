# Quality Gate — <deliverable type>

A quality gate is a small set of **dimensions** that a deliverable must pass before it ships.
The point is to make "done" concrete and checkable instead of a vibe. Define the dimensions
once for a recurring deliverable type, then run the checklist every time. Each dimension is
**pass / fail / deferred-with-reason** — silence is never a pass.

## How to use
1. Pick the dimensions that matter for THIS deliverable (start from the profile's quality gates).
2. For each, write the **pass criterion** — the observable evidence, not an intention.
3. Run it before declaring done. Anything not passed is "deferred: <reason>", tracked (R7).

## The gate (fill in)

| # | Dimension | Pass criterion (observable evidence) | Status |
|---|---|---|---|
| 1 | Correctness | <does the thing actually do what's intended — proven how?> | ☐ |
| 2 | End-to-end | <verified across every layer/consumer it reaches — R3> | ☐ |
| 3 | Safety | <no secrets leaked (R8); reversible / backed up if destructive> | ☐ |
| 4 | Docs | <docs/help/comments the change touched are updated — R6> | ☐ |
| 5 | Rendered/real | <viewed in final form / run for real, not just source> | ☐ |
| 6 | <add your own> | | ☐ |

## Example dimension sets (steal what fits)

- **Service/infra:** Deploys · Reachable from outside · Healthy (no restart loop) · TLS valid ·
  Idempotent · Backup taken · Rollback documented · Secrets externalized.
- **Document:** Facts sourced · Links/cross-refs resolve · Images/tables render · Rendered
  export eyeballed · Voice/terminology consistent · Spelling/grammar.
- **Campaign:** Copy approved by human · Audience count confirmed · Merge tokens render ·
  Links + UTMs correct · Unsubscribe present · Compliance (consent/opt-out) met.
- **Dataset/analysis:** Row counts reconcile · No silent drops · Join cardinality checked ·
  Units/types validated · Reproducible from clean run · Provenance documented.
- **Code feature:** Build · Types · Lint · Tests (incl. a previously-failing one) · Real run /
  click-through · Reviewed (self + second pass) · Docs/changelog.
