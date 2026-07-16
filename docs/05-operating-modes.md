# Operating modes — sessions and loops

There are two ways to run this harness, and they differ in one thing only: **whether a human sees
the output before it lands.** In an attended session you're in the loop — reading results,
answering questions, merging PRs. In an autonomous loop the work takes effect with nobody
watching. The dividing question, from the `autonomous-loops` profile: *"if this is wrong, will
anyone notice before it lands?"* If yes, you're in session mode. If no, everything about how you
operate has to change.

Rules live in the profiles (they're static context — restating them here would pay for them
twice and drift). This doc is the part the profiles don't carry: when each mode fits, and how you
actually run each one.

## Session mode (the default — start here, stay here longer than you think)

**The shape.** One session takes **one tracked item** — an issue, a ticket, a one-line task
description. That description is the contract. The session runs plan → do → verify → finalize →
hand off, with real autonomy in between: the agent decides routing and scope, and pauses only for
the things it genuinely can't decide (a missing credential, an external surprise, the first write
to an outside system).

**Your job as operator** is smaller than you expect and different than you expect:

- **Pick the item and write it well.** A crisp description with intent ("why we want this") beats
  a long one with implementation detail. The agent researches the *how*; only you know the *why*.
- **Start the session with the previous handoff's kickoff block** if there is one — that paste is
  the entire memory bridge between sessions.
- **Answer the pauses.** They're rare by design. When one comes, it's real.
- **Read the outcome, not the keystrokes.** Judge the PR, the report, the evidence — the way you'd
  review a colleague's work, not the way you'd watch over their shoulder.

**Two altitudes within a session.** *Conductor* — hands-on, watching each change — for debugging,
unfamiliar ground, high-stakes edits. *Orchestrator* — define the goal, let the agent delegate to
subagents, review outcomes — for well-specified features and parallelizable sweeps. Neither is
more advanced; pick per task, and the rule of thumb is absolute: **the moment something surprises
you, drop to conductor.**

**End early, on purpose.** Hand off at ~25–30% of context *used* — quality degrades as the window
fills, and the handoff note written while the agent still remembers everything is worth ten
written at the bitter end. Saying "handoff" is not stopping work; it's how work survives.

## Loop mode (autonomy you earn, not configure)

A loop is a harness **plus a schedule, durable state, and a verification chain** — a cron'd
triage agent, a nightly dependency-bumper, a `/loop` that watches CI. The `autonomous-loops`
profile carries the load-bearing rules (add it *on top of* the work profile — it's a modifier:
`software-dev,autonomous-loops`). What follows is how to operate one; for the concrete,
step-by-step build of your first one, see [`06-your-first-loop.md`](06-your-first-loop.md).

**When a loop fits:** bounded, repetitive work whose success a machine can measure — triage and
labeling, dependency bumps behind a green suite, log sweeps, report generation. **When it
doesn't:** design work, first-of-a-kind anything, and — the subtle one — any work where a checker
can't measure real success. A checker is worthless unless it measures something the maker
*structurally cannot fake*; an LLM reading another LLM's summary and approving it is theater, not
verification.

**Wiring the maker/checker split.** Two agents, not one agent twice. The maker does the work. The
checker is a *separate* agent — different instructions, ideally a stronger model for anything
unattended — told explicitly to **find reasons to reject**, and required to run the checks itself
and quote their output. "Tests passed" from the maker is a claim; the checker reruns them. This
isn't redundancy — the agent that did the work is structurally the worst judge of it, exactly
like a developer reviewing their own PR at 2am.

**Where the loop's memory lives.** A session has a context window; a loop has *runs*, and each
run starts with total amnesia. So the loop's memory must be a **durable state file, committed,
outside any conversation** — read at the start of every run, written at the end, pruned of
resolved items every run (or the loop acts on ghosts). Minimal shape:

```
## PR-1042 · flaky test quarantine
attempts: 2/3        # the cap lives HERE — a fresh run has no memory of the last two tries
status: escalated    # found | attempted | escalated | done
last: 2026-07-15 — second fix rejected by checker (test still flaky on rerun)
```

The attempt count in the state file is what makes the profile's attempt cap *real*: three tries
on one item, then escalate to a human with full context. Never widen a threshold to keep a loop
converging — escalation is the feature.

**Budget and kill switch — before the first unattended run, not after.** A daily token cap, a
rule that degrades the loop to report-only near the cap, and a documented one-move stop. Then the
step everyone skips: **actually stop it once, on purpose.** A kill switch you've never pulled is
a hypothesis. The run that needs it is the one you didn't expect.

**Climbing the ladder.** Autonomy is earned in stages, and the first stage does no work at all:

- **L1 — report-only.** The loop watches and writes its state file; it changes nothing. Run this
  for about two weeks and *read every report*. You're measuring the noise rate — if more than
  ~20% of what it flags is noise, it's not ready (and unleashing it would be automating noise).
- **L2 — small auto-wins.** Narrow, reversible actions, each behind the checker, isolated (one
  worktree per attempt), attempt-capped.
- **L3 — unattended.** Only with the full kit: denylist (secrets, auth, payments, infra — never
  auto-touched), budget, kill switch, a named success metric with a review date.

Skipping L1 means acting on a signal you never calibrated. It's the loop-mode equivalent of
deploying a service whose error rate you've never measured.

**How a loop hands off.** There's no conversation to hand off — the state file and an append-only
run log (found / did / escalated, per run) *are* the handoff, readable without opening any chat
transcript. An escalation is the loop handing off to *you*: attempt cap hit, denylist touched,
budget near — those page a human. Everything else stays in the log, because a loop that pings you
every run trains you to miss the one ping that matters.

## Which model for which phase

There's a third axis besides mode and altitude: *which model runs the step*. Planning and
execution have different economics. A plan is a few high-leverage decisions where being wrong is
expensive and being slow is cheap — it rewards the deepest-reasoning model you have. Execution is
many mechanical steps where a fast, capable model wins on throughput and the checker catches
mistakes anyway. So the strongest move is often to **split the model by phase**, not just the
session: plan with the reasoner, build with the fast model, and hand the plan over as an artifact
(which is the "plan in one session, build in another" discipline, now with a model swap at the
seam — `/model` switches it).

*As of July 2026*, that pairing is **Fable 5 for planning and design, Opus 4.8 for execution** —
but treat the names as this month's instance of a durable principle, not the principle itself.
Model lineups turn over fast; what lasts is *match the model's strength to the phase's cost of
being wrong*. The same seam also crosses tools — some teams plan in Claude and execute in Codex
([`12-platforms-and-tools.md`](12-platforms-and-tools.md) covers running the harness across
agents). Whatever the split, verification doesn't move: the checker runs the real check
regardless of which model or tool produced the work ([`03-verify-means-evidence.md`](03-verify-means-evidence.md)).

## Choosing, and moving between them

Start everything in session mode. Notice what's become routine — the items where you merge
without reading closely, the sweeps you've watched succeed ten times. That's the work that's
earned a loop, and the calibration you did watching it *was* L1. Move it out, one loop at a time,
each with its own state file and metric.

And the reverse rule is stricter: **a loop that surprises you drops back to session mode** —
same day, no debate. Autonomy is cheap to revoke and expensive to over-extend. When a loop's work
stops passing under your eyes entirely, that's when its profile stack needs `autonomous-loops`
(see [`07-how-to-pick-a-profile.md`](07-how-to-pick-a-profile.md)); when you're watching each step
again, drop the modifier.

One closing caution from the profile, because it's the failure mode that creeps: a loop that
runs green all week but produces output nobody reads hasn't succeeded — it's just spending.
Measure loops against the metric you named when you created them, not against the absence of
alarms.
