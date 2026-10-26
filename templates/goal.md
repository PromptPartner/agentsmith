# Goal: take one item through the development pipeline

Use the text in the box as a goal in Claude Code (`/goal <text>`) or in Codex (a goal set with
`/goal`). Replace `<item>`, `<slug>`, `<verify command>`, `<turns>` and `<tokens>` first. Keep
the result under 4,000 characters, the length limit of a Claude Code goal condition.

Why it is written this way:

- **"Done" is evidence in the conversation.** Claude Code's goal evaluator is a separate small
  model that reads only the conversation; it runs no commands. Codex's working model marks its
  own goal complete. Printing both commands and their output gives each something concrete to
  judge.
- **Waiting on the operator is a legitimate end.** A goal removes the prompt between turns. Without
  this clause an agent pushed to finish is tempted to accept its own spec.
- **Bounded in both dialects.** Claude Code has no token budget, so the text carries a turn limit.
  Codex keeps a token budget per goal; reaching it leaves the goal budget-limited, which is not
  completion.
- Claude Code needs a trusted workspace for `/goal`, and the command is unavailable while all
  hooks are disabled. In a project without the autonomous controller, replace the `check-specs`
  path with the one your installation provides.

```text
Take <item> through the development pipeline in order: Goal, Research, Shape, Route, Spec review, Accept, Implement, Prove, Land. The stages, the artifact each one must leave and the routing rules are in the `wayfinder` skill ("Pipeline and route"); follow them, do not skip a stage. The spec is docs/specs/<slug>.md.

This goal is done when one of these is true:
1. Both commands below exit 0, and you printed both commands and their full output in this conversation:
   python3 .agentsmith/autonomous-run.py check-specs docs/specs/<slug>.md
   <verify command>
2. The item waits on the operator: the open question or gate is recorded under "Needs operator" in the spec, and you printed that section in this conversation. Waiting on the operator counts as done for this goal.

Rules while you work:
- Never set `status: accepted` yourself. Only the operator accepts a spec; until then the item waits on the operator.
- Do not weaken a test, the verifier or check-specs to make them pass.
- Never push, merge, deploy or write to an external system.
- Claude Code: stop after <turns> turns and report what is left.
- Codex: this goal has a token budget of <tokens>. Reaching it is not completion; stop and report what is left.
```
