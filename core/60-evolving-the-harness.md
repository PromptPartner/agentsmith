<!-- CORE · system-evolution mindset · universal · this is what makes the harness compound -->
## Evolving the Harness (the System-Evolution Mindset)

**Most agent failures are configuration failures** — a missing rule, a vague instruction, an
absent guardrail, a tool that wasn't reached for, or a context window stuffed with noise. So when
you stumble, fix the system, not just the symptom. The triggers:
- you had to be corrected on something a rule could have prevented,
- you iterated more than you should have to get something right,
- the human had to step in before you'd have caught a problem,
- you re-derived a decision that a past session already made.

Then, *after* fixing the immediate thing, **propose the harness change** that makes that class of
mistake less likely next time. Small, specific, traceable to the incident.

- **Keep a durable feedback record** under `docs/feedback/` — run `/new-feedback`, or
  `agentsmith new-feedback <symptom>` for the five-stage template.
- **Prefer the deterministic fix over the reminder, and prove it** (R2): a harness edit isn't done
  until a check — a verify phase, a guard test, a lint, or a hook where hooks are enabled — fails if
  the mistake recurs. Until that guard exists, the change is a draft, not a fix.
- **Respect the context load.** This assembled file is paid for on every turn. Specialized
  knowledge belongs behind a pointer — a skill, a template, a `docs/` page — that loads only when
  needed. Before a line earns a place here, apply the **no-op test**: delete it; does behaviour
  change? Writing anything an agent reads → `/writing-rules`.
