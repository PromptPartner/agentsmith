# The development pipeline

A change that matters goes through the same stages every time. Each stage leaves a file, and the
next stage starts only when that file exists. The order then lives in files a check can read, not
in prose an agent can skip. `python3 .agentsmith/autonomous-run.py check-specs` is that check.

## Stages

| # | Stage | The artifact it must leave | Gate to the next stage |
|---|---|---|---|
| 0 | **Goal** | The goal and the problem, restated by the agent in its own words, in the spec | The restatement is in the spec |
| 1 | **Research** | `docs/research/<slug>.md`: sources, verified and inferred claims marked, the premise reproduced | The spec's `research:` names that file |
| 2 | **Shape** | The draft spec `docs/specs/<slug>.md` (`status: draft`): destination, non-goals, alternatives, "Needs operator" | The draft exists |
| 3 | **Route** | `route:` with a one-line reason (see below) | `route` is set; for `wayfinder`, no open in-scope decision remains |
| 4 | **Spec review** | A verdict file from a reviewer who did not draft the spec, named in `reviewer_receipt:`, and a "Review resolution" section | The verdict accepts, or every requested change is resolved |
| 5 | **Accept** | `status: accepted`, `accepted_by`, `accepted_at` | Only the operator accepts. An agent never accepts a spec |
| 6 | **Implement** | Commits with a red-first proof | The project verifier is green |
| 7 | **Prove** | Verifier output and `check-specs` output, both shown | Both exit 0 |
| 8 | **Land** | A commit or pull request with the evidence | The operator's delivery rule; nothing auto-merges |

Why the early stages matter:

- **Restating the goal** costs one paragraph and catches drift between the operator and the agent
  before any work starts.
- **Ticket text is a hypothesis.** Research reproduces the premise before a spec builds on it.
  Work that starts on a premise nobody checked often has to be redone.
- **A reviewer who did not write the spec** finds the gaps its author cannot see. A thin spec is
  a frequent reason an unattended run stops halfway.

`autonomous-run` is the usual way to do stage 6: it implements one separately tracked ticket from
an accepted spec, with a fresh maker, the sandboxed verifier and an independent checker. See
[autonomous runs](21-autonomous-runs.md).

## Route: how much planning an item needs

| Route | Use it when | Example |
|---|---|---|
| `direct` | The work is decision-complete, fits one session, and "done" is clear | A bug with a reproduction, a flaky test, a docs fix |
| `grill` | The shape is unclear but the work fits one session, and the operator is there to answer | A small feature whose behavior is not settled |
| `wayfinder` | Two or more open decisions depend on each other; or it needs several sessions; or it crosses subsystems or owners; or it changes a data model, a security boundary or a failure mode; or an earlier run on it stopped on a gap in the spec | A redesign of tenant isolation |

Rules:

- When the case is unclear, take the heavier route.
- `direct` skips only the decision map. It still needs research, a spec review and acceptance.
- Record the route and its reason in the spec (`route: direct — one bug with a reproduction`), so
  the choice can be checked later.
- **A list of bugs is not one pipeline item.** Work it as a numbered checklist with one `direct`
  item per bug. A single brainstorm over a long bug list can lose many of the bugs in a
  mid-session change of direction.

## Attended and unattended work

Wayfinder normally resolves one decision per session with the operator. In an unattended batch,
an agent may resolve several decisions in one session when an agent can answer them, and records
the rationale for each one. A decision that needs the operator's preference goes under "Needs
operator" in the spec. It blocks only the decisions and tickets that depend on it; the rest of the
map moves on. An item that waits on the operator, recorded there, is a legitimate stopping point.

## Optional adapter: superpowers

The pipeline does not need any plugin. When the `superpowers` plugin is enabled, a stage may use
its skill; when it is not, the built-in fallback applies.

| Stage | superpowers enabled | Built-in fallback, attended | Built-in fallback, unattended |
|---|---|---|---|
| Shape | `superpowers:brainstorming` | `grill-with-docs` | The agent writes the alternatives and puts each preference question under "Needs operator" |
| Plan | `superpowers:writing-plans` | The spec's implementation-ticket drafts | Same |
| Implement | `superpowers:subagent-driven-development` | `autonomous-run` or an attended session | `autonomous-run` |

Four conflicts and how the pipeline settles them:

1. **Session-start instruction.** superpowers injects its own "use superpowers" instruction when a
   session starts. AgentSmith's order wins: a superpowers skill runs only for the stage above, not
   by its own trigger rules.
2. **Where specs go.** Brainstorming saves to `docs/superpowers/specs/`. Save the spec as
   `docs/specs/<slug>.md` instead; Wayfinder, `check-specs` and `autonomous-run` read only that
   folder.
3. **The forced next step.** Brainstorming says that the only next skill is `writing-plans`. In
   this pipeline the next stage after Shape is Route, then Spec review.
4. **Its human review wait.** Brainstorming waits for the operator to review the written spec. In
   an unattended batch, use the unattended fallback instead; the operator still accepts at stage 5.

## Running the pipeline under a goal

Claude Code's `/goal` and Codex goals keep an agent working until a condition holds.
[`templates/goal.md`](../templates/goal.md) is one goal text for both. It points at this pipeline
instead of restating it, and it defines "done" as the guard and the verifier exiting 0, with
both outputs printed in the conversation, or the item waiting under "Needs operator".
