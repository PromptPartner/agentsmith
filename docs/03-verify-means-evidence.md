# Verify means evidence

You already own the word "verify" — every developer does. Here it means something stricter than
you're used to, and the difference is the single most load-bearing idea in the harness. If you
read one concept doc, read this one.

## The distinction

"It works." "The fix is in." "Should be fine now." — these are **claims**. Evidence is an
**artifact the verification produced**: a test that failed before the change and passes after, an
HTTP response from the actual endpoint, a rendered page you looked at, a row count that
reconciles, a diff of before/after output. The harness's Rule 2 draws the line absolutely:
no claim without evidence you actually produced. Not "it should," not "it looks right" — the
artifact, then the claim. Never the reverse.

## Why this is *the* rule for agent work specifically

Working with a capable human, you can partly trust the report because confidence and correctness
correlate — a senior engineer who says "tested it, works" usually did and it usually does. With
an agent that correlation is broken in a specific, dangerous way: **it generates plausible
success narratives at exactly the same fluency as true ones.** A report of what it did is a
probable-sounding text about work, and "probable-sounding" is precisely what the model is best
at. You cannot tell a real "all tests pass" from a confabulated one by reading it. Only an
artifact distinguishes them — which is why the harness runs on artifacts.

This isn't agent cynicism; it's the same reason your CI doesn't take the PR author's word that
tests pass. The harness just applies that instinct everywhere, because with an agent, *every*
claim is a PR author's word.

## Two kinds of proof — and most work needs both

**Tests** cover the deterministic part: this input produces that output. Binary, cheap to rerun,
the bedrock. But most real work has a part no assertion can reach: is the *approach* right, is
the tone right for this audience, is the analysis answering the actual question? That part needs
**evaluation** — a rubric, a second independent reviewer (human or an adversarial AI pass told to
find reasons to reject), a real run observed end-to-end.

A document can pass every spellcheck and be wrong for its reader. A trading strategy can pass its
backtest *because* the backtest is the overfit artifact. Tests catch broken; evals catch
plausible-but-wrong — and plausible-but-wrong is the agent-era failure mode.

## What counts, per kind of work

Each profile sharpens "done and verified" for its territory — it's the first section to read in
yours. The flavor:

| Work | Evidence is… | A claim is… |
|---|---|---|
| **Software** | a test that failed before the fix and passes after; the *full* suite green | "the logic is correct now" |
| **DevOps** | the endpoint responding from *outside* the box, TLS valid, no restart loop | a command exiting 0; `docker ps` saying "running" |
| **Documents** | the *rendered* output read, links resolving | the source markdown "reading fine" |
| **Data** | totals reconciling against the source; row counts matching | "the transform looks right" |
| **Research** | every load-bearing claim traced to a source you actually opened | a confident synthesis |
| **Outreach** | the message rendered in every format/segment it fans out to | "the template works" (one of them did) |
| **Unattended loops** | a *separate* checker that reran the checks and quotes their output | the maker saying its own tests passed |

Two cross-cutting rules ride along. **Verify the whole chain:** correct at your layer isn't
correct at the layer the user sees — trace one concrete example end-to-end, and when a change
fans out to many consumers, check every one ("one of them works" is how the other five ship
broken). And **the maker is never the judge** for anything unattended: verification must measure
something the maker structurally cannot fake (the deep version is in
`profiles/autonomous-loops.md`).

## Verification has a shelf life

The subtlest failure, straight from this harness's incident log: files that had to survive an
untracking were verified present on disk — a real check, real evidence. Four git operations
later (a checkout, a merge, a `reset --hard`), they were gone. The `ls` had proved something true
*at step 1*, and the ground moved. It was caught only because the final report was about to claim
"nothing deleted," and that sentence got re-checked instead of asserted.

The rule that generalizes: **re-verify after the last destructive step, not after the step that
preserved it** — and check the *claim you're about to make*, at the moment you make it, not the
memory of the action that once made it true.

## The mechanical form

`scripts/verify.sh` reads `.harness/verify.conf` — one `label :: command` per line, run in
order, first failure stops — and is the gate for calling anything shippable. It starts as a
placeholder that only echoes, which means **a fresh install's "verified" is vacuously true until
you wire real phases**. Replacing that line with your build/test/checks is the highest-leverage
five minutes in the whole setup ([`02-your-first-hour.md`](02-your-first-hour.md) walks it). From then
on, "done" has a definition that's versioned with your repo — and the agent's claim and your
gate are the same command.
