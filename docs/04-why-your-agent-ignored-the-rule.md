# Why your agent ignored the rule

It will happen, probably in your first week: you write a rule into `CLAUDE.md`, plainly, in
bold — and the agent does the opposite. The instinct is "the model is dumb" or "I need a bigger
model." Both are almost always wrong, and both point away from the fix. A rule that didn't land
failed for one of four specific, fixable reasons. This doc is those four reasons — but first, the
mechanics, because they're nothing like what a developer expects.

## Rules don't execute — they compete

`CLAUDE.md` is not parsed, compiled, or enforced by anything. The agent *reads* it, every turn,
alongside everything else in its context window — the conversation, the files it opened, the tool
output. Each rule is a **bid for attention** in that crowd, weighted probabilistically against
every other token present. A rule is not an `if` statement. It's a standing instruction to a very
capable colleague who is rereading the entire employee handbook every few seconds while also
doing the work — and who, like any colleague, attends to what's salient.

This one fact predicts every failure mode below.

## The economics: why you can't just add more rules

Rules live in **static context** — loaded and paid for on *every single turn*. Dynamic context
(skills, docs, memory) loads only when a task needs it and is free until then. That asymmetry has
a hard number in this harness: the assembled `CLAUDE.md` is budgeted at **600 lines / ~10,000
tokens** (`scripts/lint-leanness.sh` warns past it). The core plus two profiles measures at 551
lines and ~9,860 tokens — **98% spent**. This is by design, not accident: the budget is full
because every line earned its place, and the discipline is what keeps it working.

The cost of exceeding it isn't an error message. It's dilution: every line you add slightly
weakens the agent's attention to every line already there. Ten sharp rules outperform forty
reasonable ones. "Just add a rule for it" is how harnesses die — slowly, and while appearing to
grow more thorough.

So when a rule fails, adding words is the one move that's almost never right. Diagnose instead:

## The four ways a rule fails

**1. Drowned.** The rule is fine; it's buried in too much static context, competing with noise.
The tell: the agent follows it when reminded, forgets it otherwise. The fix is subtraction —
move reference knowledge into a skill or a `docs/` page loaded on demand, and run
`lint-leanness.sh` to see what the budget says. Every removal makes the surviving rules louder.

**2. Vague.** "Be careful with the database" names no act, no failure, no boundary — there is
nothing for the agent to *match* against the moment that matters. Compare: "never run a
destructive migration without a dump taken first — a `down -v` on the wrong box is
unrecoverable." Rules that name a concrete failure and its reason dramatically outperform stated
virtues, because the agent can recognize the situation when it arrives. Write rules like
post-mortems, not values statements.

**3. Contradicted.** Sometimes by another rule — two instructions that collide resolve
unpredictably. But more often *by you*: operator instructions outrank the rulebook (as they
should), so "just quickly push this, skip the checks" wins over every verification rule you ever
wrote. The agent obeying you over the harness is correct precedence, not a bug. The harness can
hold a line against the agent's shortcuts; it cannot hold one against yours.

**4. Unguarded.** The deepest one. Prose is probabilistic — a rule read every turn will still,
occasionally, lose the attention contest. For anything that must hold *100% of the time*, prose
is the wrong tool entirely; you need a **guard**: a hook or check that fails deterministically,
outside the model.

This harness learned that one the expensive way. A setup re-run had a known trap that blanked a
config file's identity fields. The previous session hit it and left an explicit, written warning
in its handoff note. The next session **read that warning at startup — and walked into the same
trap anyway**, because the failure came during a low-suspicion moment (a measurement, not a
change). What finally held wasn't a third, louder warning: it was recovery logic in the script
plus a 19-check test suite that goes red if the bug ever returns. The lesson, now a core line:
**guardrails hold what prose forgets.** If you find yourself writing a rule in ALL CAPS, what you
actually want is a hook.

## Symptom → the guard that already exists

| Symptom | Deterministic guard |
|---|---|
| A secret nearly landed in a commit | `scripts/secret-scan.sh` as a pre-commit hook (`--with-hooks`) |
| Work committed straight to main | `hooks/git/protect-main.sh` |
| `CLAUDE.md` creeping past the budget | `scripts/lint-leanness.sh` / `setup.sh --doctor` |
| "Done" claimed, checks not run | `scripts/verify.sh` — the gate is a script, not a promise |
| Anything project-specific that must never recur | a phase you add to `.harness/verify.conf` |

The pattern generalizes: this repo itself replaced a by-hand "keep the published tree generic"
review with a small gate script — which promptly caught, in its first run, a leak in a place
nobody was looking (the `--help` text of both setup scripts), and then flagged its own first
draft. Gates beat eyeballs even when the eyeballs wrote the gate.

## When a rule fails: debug the system

A rule that didn't land is data, and there's a loop for it — don't just re-scold the agent in
chat (that fixes one session and evaporates). Run `./scripts/new-feedback.sh "what happened"`
and walk the incident through five stages: evidence → failure mechanism → smallest bounded edit →
the exact surface it lands on → a check that fails if it regresses. Which cause above it was
tells you the fix: drowned → subtract; vague → sharpen; contradicted → reconcile; unguarded →
hook. The full discipline lives in `core/60-evolving-the-harness.md` and
[`feedback/README.md`](feedback/README.md) — this doc ends where they begin.

Most agent failures are configuration failures. That's not a consolation — it's the good news.
Configuration is the part you can fix.
