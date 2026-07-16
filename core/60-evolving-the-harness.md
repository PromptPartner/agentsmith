<!-- CORE · system-evolution mindset · universal · this is what makes the harness compound -->
## Evolving the Harness (the System-Evolution Mindset)

This is the rule that makes every other rule better over time. **The agent is the model plus
this harness; the model is the small part you don't control, the harness is the large part you
do.** When a session goes wrong, the honest diagnosis is almost never "the model is dumb" — it's
a missing rule, a vague instruction, an absent guardrail, a tool that wasn't reached for, or a
context window stuffed with noise. **Most agent failures are configuration failures.** So:

**When you stumble, fix the system — not just the symptom.** Any time you notice one of these:
- you had to be corrected on something a rule could have prevented,
- you iterated more than you should have to get something right,
- the human had to step in before you'd have caught a problem,
- you re-derived a decision that a past session already made,

then *after* you fix the immediate thing, take one more step: **propose the harness change** that
makes that class of mistake less likely next time. That might be a new line in a `core/` rule, a
sharpened quality gate in the profile, a new skill or template, a hook that enforces the thing
deterministically, or a feedback note in memory. Small, specific, traceable to the incident.

**How to apply, concretely:**
- **Keep a durable feedback record** under `docs/feedback/` — run `/new-feedback` (or
  `./scripts/new-feedback.sh "symptom"`). The `new-feedback` skill carries the five-stage template
  (evidence → failure mechanism → bounded edit → named surface → non-regression) and the
  harness-review checkpoint (`docs/feedback/README.md`), so every rule traces to a real incident and
  the set stays lean and load-bearing (R10).
- **Prefer the deterministic fix over the reminder, and prove it** (R2): a harness edit isn't done
  until a check — a hook, a verify phase, a guard test, even a grep assertion — fails if the mistake
  recurs. Guardrails hold what prose forgets; until that guard exists, the change is a draft, not a fix.
- **Respect context economics.** This assembled file is *static context*, paid every turn — keep it
  lean. Specialized knowledge belongs in *dynamic context* (skills, templates, `docs/`, memory) that
  loads only when the task needs it. Tempted to add a paragraph here? Ask whether it's a skill or a doc.
- **Don't silently bloat.** A harness change earns its place like code. Check the budget with
  `scripts/lint-leanness.sh` (or `setup.sh --doctor`) — over budget is the cue to move knowledge into
  a skill/doc, not to keep growing this file.

The payoff is compounding: a harness that gets a little more reliable every time it's used is
worth far more than any single fix. Invest in the factory, not just the widget.
