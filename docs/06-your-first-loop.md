# Your first loop

[`02-your-first-hour.md`](02-your-first-hour.md) walked a session end to end. This is its
counterpart for the other mode: standing up a loop — a harness that runs on a schedule, with
nobody watching each step — without it being the reckless thing that phrase makes it sound.
[`05-operating-modes.md`](05-operating-modes.md) is the *why* and *when*; this is the *how*, in
order. The rules a loop must obey live in `profiles/autonomous-loops.md` (they're loaded when you
assemble that profile) — this doc points at them rather than repeating them, and adds the
operation the profile doesn't carry.

The one-line version: **a loop is a session you've run so many times you trust the shape, plus a
schedule, a durable state file, and a checker the maker can't fool.** Build it in that order.

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
