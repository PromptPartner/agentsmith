# Your first verified loop

[`02-your-first-hour.md`](02-your-first-hour.md) introduces the files and commands. This guide runs
one value through the complete attended loop before discussing automation. That order matters: an
unattended loop should be a trusted attended shape plus scheduling and isolation, not an unfamiliar
task with the human removed.

## Part 1 — complete the attended proof loop

### 1. Create the disposable project

From the AgentSmith source checkout, choose a new or empty directory:

```bash
python3 agentsmith.py demo first-loop --target /tmp/agentsmith-first-loop
cd /tmp/agentsmith-first-loop
```

The initializer uses no network and installs no dependency. It refuses broad, non-empty, and
symbolic-link targets. Read `ACCEPTED_TASK.md`: the outcome is narrow, the non-goals are explicit,
and only `readiness.py` plus its test are in scope.

### 2. Understand the active setup before editing

```bash
agentsmith status --target .
```

Status should name the three configured verification phases—syntax, tests, and real path—and show
unit/integration coverage as configured. In a normal repository, this is also where you would run
`agentsmith profiles recommend --target .` and preview a profile switch if the active work type is
wrong. The demo already has its bounded verification configuration, so no switch is needed.

### 3. Produce the red evidence

```bash
agentsmith verify --target .
```

The partial-check test must fail. This is intentional: `checks.json` has one true and one false
check, while `readiness.py` incorrectly accepts `any(checks.values())`. A failure with a different
test or reason is not the expected baseline—diagnose it before editing.

### 4. Make only the accepted change

Change `return any(checks.values())` to `return all(checks.values())`. Do not change the fixture,
remove a check, or add a dependency. This is the smallest change that makes the accepted behavior
true: readiness requires every named check.

### 5. Retain deterministic and real-path proof

```bash
agentsmith verify --target . \
  --record .harness/evidence/first-loop \
  --tree-class disposable-fixture
python3 readiness.py checks.json
```

Verification must pass syntax, tests, and the exercise script. The visible command must print
`NOT READY` and exit 1 because `security_review` is still false; that non-zero exit is the correct
user-visible result, not a failed fix. Inspect `.harness/evidence/first-loop/receipt.json` to see
which tree, configuration, phases, exits, and output hashes produced the claim.

### 6. Save and validate the continuation point

```bash
agentsmith handoff first-verified-loop --target .
agentsmith resume --target . --json
```

Fill the generated handoff with the actual branch, commit, dirty state, receipt, remaining authority,
and next read-only status command. Resume must then report `ready` with no unexpected drift. It
validates and synthesizes safe output; it does not check out, commit, stash, reset, or edit the note.

### 7. Inspect the reference proof

The [public proof bundle](demos/first-verified-loop/README.md) retains this exact red→green→real-path
chain, plus clean and existing-config installation lifecycle fixtures, a flow diagram, claim map,
sanitization record, and limitations. Its generator reruns every command from a temporary clean Git
copy and the contract byte-compares the normalized result.

## Part 2 — only then consider an unattended loop

The rest of this guide covers the other mode: a harness that runs on a schedule with nobody watching
each step. [`05-operating-modes.md`](05-operating-modes.md) is the *why* and *when*. The rules live
in `profiles/autonomous-loops.md`; this guide points at them rather than repeating them and adds the
operation the profile does not carry.

The one-line version: **an unattended loop is an attended session you've run enough times to trust
the shape, plus a schedule, a durable state file, and a checker the maker cannot fool.** Build it in
that order.

## Before you automate anything: you've already done L1

Don't start here. Start by running the same work as attended sessions until it's boring — until
you're merging its output without reading closely because it's been right ten times. That
boredom is data: it's the report-only calibration phase (L1) the profile insists on, and you did
it by hand. If the work still surprises you, it isn't ready to run unwatched, and no amount of
setup fixes that. The loop automates a *known-good* routine; it doesn't discover one.

## Step 1 — write the one sentence, and the non-goals

A loop with a fuzzy goal spends money producing nothing. Before any wiring, write down: the
single sentence of what it does ("triage new issues and label them by area"), the explicit
non-goals ("never closes anything, never comments on the issue"), and the exact scope it may
touch (which repo, which branch, which labels). This sentence is what you'll measure it against
later when you ask the only question that matters — *is it actually earning its cost?*

## Step 2 — create the state file first

The loop's memory is not a conversation; every run starts blank. So its memory has to be a file,
committed, that the run reads at the start and writes at the end. Create it before the loop
exists, so there's never a run without one:

```
# .harness/loops/issue-triage.md   (committed — this IS the loop's memory)
## goal
Triage new issues, label by area. Non-goals: no close, no comment. Scope: repo X, label set {area/*}.

## budget
daily-cap: 200k tokens · degrade-to-report-only at: 80% · kill: rename this file to *.paused

## items
(none yet — the loop appends here: id, attempts N/3, status, last-outcome, timestamp)
```

The `attempts N/3` line is load-bearing: it's what makes the profile's attempt cap real across
runs that share no memory. A fresh run reads "2/3" and knows this is the last try before it
escalates to you — knowledge that would otherwise die with the previous run's context window.

## Step 3 — wire the checker as a separate agent

This is the step that separates a loop from a liability. The agent that does the work does not
judge the work — a second agent does, with different instructions, told to **find reasons to
reject** and to *run* the check itself rather than trust the maker's summary. In practice that's a
subagent dispatch inside the loop: maker proposes a diff in an isolated worktree; checker runs
the real tests (`/verify` or the project's own) and quotes the output; reject discards the
worktree. The profile's rule is absolute and worth internalizing here: the check must measure
something the maker **structurally cannot fake** — "the tests I wrote pass" is not that; "the
existing suite still passes on a clean checkout" is.

## Step 4 — schedule it, cheaply

Use the native scheduler, not a bolted-on framework (R10). `/schedule` registers a cloud cron
agent; `/loop` runs one on an interval in a live session. Prefer a **long interval with a real
wake condition** over tight polling — a loop that wakes every minute to find an empty watchlist
is just spending. The first thing a run should do is the cheapest possible triage ("is there
anything new?") and exit immediately if there's nothing, before it spins up the expensive
maker/checker machinery.

## Step 5 — set the budget and the kill switch, then test the kill switch

Before the first unattended run — not after the first scare — the state file already names a
daily token cap, a rule that degrades the loop to report-only near the cap, and a one-move stop.
Now do the step everyone skips: **actually stop it once, on purpose.** Rename the file to
`.paused`, run the loop, confirm it exits without acting. A kill switch you've never pulled is a
hypothesis, and the run that needs it is the one you didn't expect.

## Step 6 — run it report-only, and read every report

Even though your attended sessions were the real L1, run the *assembled loop* report-only for its
first stretch: it writes what it *would* do to the state file and takes no action. Read those
reports. You're checking that the automated version flags the same things your hand-run did, at a
noise rate you can live with (the profile's guide is under ~20% junk). Only when the reports are
boringly correct do you let it act — and then on the narrowest, most reversible actions first.

## What "handoff" means for a loop

There's no chat to hand off. The state file plus an append-only run log (found / did / escalated,
one line per run) *are* the handoff — readable without opening any transcript. The loop hands off
to *you* only by exception: attempt cap hit, a denylisted area touched (secrets, auth, payments,
infra — never auto-edited), budget near the cap. Everything else stays in the log, because a loop
that pings you every run trains you to miss the ping that matters.

## The failure that hides from all of this

A loop can pass every step above, run green for a month, and still have failed — if it produces
output nobody reads. Green is not the metric; the sentence from Step 1 is. Put a review date on
the loop when you create it, and on that date answer honestly whether it still earns its cost. If
it ever surprises you, it goes back to attended sessions the same day — autonomy is cheap to
revoke and expensive to over-extend. The full failure catalogue is in `profiles/autonomous-loops.md`;
the mindset is in [`05-operating-modes.md`](05-operating-modes.md).
