---
schema: 2
status: draft
decision_ticket: <tracker link/id or paste-ready draft name>
research: <docs/research/<slug>.md, the research note this spec builds on>
route: <direct | grill | wayfinder> — <one-line reason>
reviewer_receipt: <path to the verdict file of a reviewer who did not draft this spec>
accepted_by:
accepted_at:
---

# Spec: <destination name>

## Destination

<The observable end state this effort is finding a route to.>

## Non-goals

- <A deliberate boundary; include why it is outside this destination.>

## Edge cases

- <An input, state or failure the implementation must handle, and the expected behaviour.>

## Assumptions

- `<path/to/file>` <what this spec assumes about it; the file must exist at the run's base commit>
- `<path/to/file>::<symbol>` <the symbol must occur as a whole word in that file there>
- <A prose assumption; an item that does not open with a backticked reference is not checked.>

## Decision map

### Frontier

- [ ] **<decision name>** — <sharp question>; blocked by: none

### Blocked

- [ ] **<decision name>** — <sharp question>; blocked by: <decision name>

### Fog

- <In-scope uncertainty that is not yet sharp enough to state as a decision.>

## Decision index

- [<resolved decision name>](<ticket or durable artifact>): <answer gist> — <one-line rationale>

## Explicit deferrals

- <Non-blocking uncertainty intentionally deferred, with reason and future owner/item.>

## Needs operator

- <A human-preference decision or gate an agent may not answer, and the decisions it blocks.>

## Acceptance and evidence

- <End-to-end observable that proves the destination was reached.>

## Review resolution

- <Each reviewer finding and what changed, or why it was declined.>

## Decision-ticket drafts

### <decision name>

**Question:** <one decision this ticket resolves>

**Blocked by:** <decision name or none>

**Resolution:** <leave open until decided>

## Implementation-ticket drafts

> These are new work items created only after this spec is accepted. They do not reuse or reopen
> the decision ticket.

### <implementation ticket title>

- **Outcome:** <one independently deliverable result>
- **In scope:** <bounded work>
- **Out of scope:** <boundary>
- **Depends on:** <accepted decision or preceding implementation ticket>
- **Acceptance/evidence:** <checks and observable result>
