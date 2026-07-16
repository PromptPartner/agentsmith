# Adapting it to your team

Every rule in this harness was paid for — a real incident, on a real project, that cost real time
or trust. That's its strength and its limitation in one: the rules are *earned*, but they were
earned from **someone else's incidents**. Running it as-is is a fine start. It becomes *yours* —
and genuinely better than anything you could download — only when rules start tracing to failures
your team actually had.

## Why earned beats copied

A rule you can't trace to a failure is a best practice: decorative, interchangeable, and the
first thing rationalized away under pressure ("surely that doesn't apply here"). A rule with a
story attached — *"never X; last time, Y broke and it cost us Z"* — carries its own justification
to exactly the situations where it matters. Reasons travel; rules don't.

There's a budget argument too, and it's not soft: static context is capped (~600 lines / 10k
tokens — see [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)), so
every copied rule you don't actually need crowds out an earned rule you do.

## What to keep, what to expect to change

**Keep the core.** Its ten rules guard failures that are universal because they're human, not
domain-specific: secrets end up in repos, unverified claims ship, research gets deleted in
cleanups, changes get bundled until nothing can be rolled back. If one seems not to apply to you,
that's usually the incident you haven't had yet.

**Expect to change everything downstream of "what does done mean here":** the profile's quality
gates, `.harness/verify.conf` (always — the placeholder is meant to be replaced), the tracker
conventions, the skills. That's the tailoring layer; it's *supposed* to diverge.

## The earning loop

When something goes wrong — you corrected the agent, it thrashed, a reviewer caught what the
harness should have — resist the twin temptations of fixing just the instance (it recurs) and
writing an angry rule on the spot (it bloats). Instead:

```bash
./scripts/new-feedback.sh "short symptom title"
```

That scaffolds a numbered post-incident record with five stages: **evidence** (what was observed,
verbatim — no diagnosis yet) → **failure mechanism** (why the *system* allowed it) → **bounded
edit** (the smallest change that prevents the class) → **named surface** (exactly where it lands)
→ **non-regression** (the check that fails if it comes back). The discipline of the ordering is
the point — it forces you past "patch the symptom" into "change the system."

A worked example from this harness's own log: an operator asked for handoffs "when context
reaches 25–30%." It was built as 25–30% *left* — one misread word, silently compiled into a
default of 70% used, then copied across six files. The instance-fix would be one number. The
*system* fix, which is what shipped: a single source of truth for the threshold, and the
direction ("used", not "left") plus the *reason* stated everywhere the number appears — so the
class of error (a magic number duplicated in prose and code, with no check tying it to intent)
got harder, not just this case.

## Where a new rule goes — the decision that keeps it lean

The write-up's "named surface" stage forces a choice, and the cost model makes it for you:

| Surface | Cost | Put here when… |
|---|---|---|
| **Hook / verify phase** | zero until triggered — and *deterministic* | it must hold 100% of the time. Always your first candidate: a check can't be rationalized around; prose can. |
| **Profile** | every turn, on projects of that type | it's about what "done" means for one kind of work. |
| **Skill** | zero until invoked | it's a procedure — how we do releases, how we structure a report. |
| **Doc / template** | zero until read | it's knowledge or reference, not behavior. |
| **Core** | every turn, everywhere, forever | last resort. Universal, earned, and the budget has room — and prefer *amending* an existing rule over adding one. (This harness has capped itself at ten for a reason.) |

If you can't name the surface and the regression check, you haven't found the system fix yet —
you've only described the bug.

## Pruning — rules must keep earning their place

Accumulation is the death spiral: each rule reasonable, the sum incoherent. On a regular cadence
(each release, or every handful of sessions), run the review in
[`feedback/README.md`](feedback/README.md): land or close the open records, re-check that applied
fixes are still in place (refactors silently undo them), watch the budget, and look for clusters —
three records pointing at the same surface mean the surface is the problem, and want one
structural fix instead of a fourth patch. Obsolete rules and records get *archived*, never
deleted: the history of why each rule existed is what keeps the survivors lean.

## Retrofitting onto an existing project

Adopting the harness on a large, established repo is lower-risk than it sounds, because the harness
introduces itself *read-first*. Do it in this order and nothing lands with force:

1. **Rules before machinery.** Assemble just the `CLAUDE.md` — `./setup.sh --profile <dominant> --target .`
   — and run a handful of real sessions before you add a single hook or gate. You're watching how
   the agent behaves under the rules on *your* code, with your team still fully in the loop, before
   you make anything deterministic.
2. **Wire `verify.conf` to the checks you already have.** Don't invent new ones. Point the phases
   at your existing build and test commands; "shippable" should mean what it already means on this
   repo, just made explicit ([`03-verify-means-evidence.md`](03-verify-means-evidence.md)).
3. **One profile, not all of them.** Pick the profile matching the bulk of the work; stack a second
   only if the repo genuinely spans two kinds (a service *and* its installers). Resist the urge to
   pre-load every rule you can imagine — the feedback log starts empty on purpose.
4. **Land it like any change.** The `CLAUDE.md` goes on a branch and through review — your team
   reads and agrees to the rules the same way they'd review a config change, because that's what
   it is. Rule 1 (understand before you change) protects your codebase here: the agent reads the
   surrounding code before touching it, which is exactly the behaviour you want on a codebase it
   has never seen.

The empty feedback log is a feature: your *first real incident on this repo* writes the first
entry. Rules earned from your own code beat rules imagined in advance — that's the whole point of
the section above.

## At team scale

The layered install maps onto a team cleanly: the **core installs once per machine**
(`--global`, or `--org-policy` for a managed box) and each repo carries only its **profile** plus
project specifics. That gives every engineer the same spine with per-project tailoring — and one
place to land a lesson so everyone inherits it.

The under-rated asset at team scale is the **feedback log itself**. It's your team's institutional
memory of *why* — the part that normally lives in senior engineers' heads and leaves when they
do. A new teammate who reads the incident log understands the harness better than one who reads
the rules, for the same reason post-mortems teach more than runbooks. And when someone asks "why
do we have this weird rule?" — the answer is a numbered file, not archaeology.
