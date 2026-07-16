# Feedback — the harness's self-improvement log

This directory is the **durable feedback record** that [`core/60-evolving-the-harness.md`](../../core/60-evolving-the-harness.md)
is built around. It's how the harness *compounds*: every time a session stumbles, the lesson is
captured here as a small, traceable change to the **system** — not just a one-off fix to the bug
in front of you.

> **The agent is the model plus the harness.** The model is the ~10% you don't control; the
> harness is the ~90% you do. A failure is almost never "the model is dumb" — it's a missing
> rule, a vague instruction, an absent guardrail, an unreached tool, or a noisy context window.
> **Most agent failures are configuration failures**, and this log is where you fix the config.

## When to file one

File a feedback entry the moment you notice any of the four System-Evolution triggers (core/60):

- you had to be **corrected** on something a rule could have prevented,
- you **iterated more** than you should have to get something right,
- the **human stepped in** before you'd have caught a problem,
- you **re-derived a decision** a past session already made.

Don't wait for permission and don't batch them up — the cost of a forgotten lesson is it
recurs. One entry per incident.

## How

```bash
./scripts/new-feedback.sh "short symptom title"
```

That scaffolds the next numbered entry (`0007-short-symptom-title.md`) with the five sections
below. Numbers are stable references ("feedback 0007") and never reused. Like research, **feedback
is never silently deleted** — if an entry is genuinely obsolete, move it to `_archive/`, don't
remove it (R9). The history of *why* each rule exists is the thing that keeps the rule set lean.

## The five sections (the self-improving-harness loop)

Each entry walks one incident through the same five stages. This ordering is the discipline — it
forces you past "patch the symptom" into "change the system":

1. **Evidence / symptom** — what was *observed*, concretely. Quote the correction, the loop, the
   human catch. No diagnosis yet.
2. **Failure mechanism** — *why the system allowed it*. The missing rule / vague instruction /
   absent guardrail / unreached tool / noisy context. The actual root cause.
3. **Bounded edit** — the *smallest* change that prevents the whole class. One rule line, one
   gate, one hook. If it feels big, the mechanism is mis-scoped — narrow it.
4. **Named surface** — *where* the edit lands, exactly: a `core/` rule, a profile gate, a skill,
   a hook, a template, or a `verify.conf` phase. Prefer a **deterministic** surface (hook /
   verify phase the agent *can't* skip) over prose it might.
5. **Non-regression validation** — how you confirmed it's fixed *and stays fixed*: the failing
   case that now passes, the hook that now blocks it, the verify phase that's now red on
   regression. Evidence, not intention. Until this is real, the entry's **Status** stays `open`.

A good entry is small and load-bearing. If you can't name a surface and a non-regression check,
you haven't found the system fix yet — you've only described the bug.

## The recurring harness-review checkpoint

Capturing lessons isn't enough; the loop only closes if you periodically **fold them back in and
prune**. Run a lightweight review on a regular cadence — at each milestone/release, or every
handful of sessions, whichever comes first:

1. **Read the `open` entries.** For each, either land its bounded edit (then flip Status to
   `applied`) or, if you've decided not to, mark it `wont-fix` with one line of why. No entry
   sits `open` forever.
2. **Verify the `applied` edits are still in place.** Each entry's *named surface* tells you
   exactly what to re-check — the rule line still reads that way, the hook still fires, the
   verify phase still exists. Refactors silently undo fixes; this is where you catch it.
3. **Watch the budget.** Accumulated edits bloat static context. Run
   `scripts/lint-leanness.sh` (or `setup.sh --doctor`) — over budget is the cue to move
   knowledge out of `core/` into a skill/doc, not to keep growing the rules.
4. **Look for clusters.** Three entries pointing at the same surface mean the surface itself is
   the problem — fix it once, structurally, instead of adding a fourth patch.

Keep a one-line note of when you last ran the review (a dated line at the bottom of this file, a
tracker ticket, or a memory note) so the cadence is visible and doesn't quietly lapse.

---

_Last harness review: (none yet — run the checkpoint above and date it here.)_
