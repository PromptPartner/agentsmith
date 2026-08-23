# Harness surfaces — where a line goes, and what it costs

The harness-specific branch of [`writing-rules`](SKILL.md). Read this when the document you're
writing is part of the harness itself. Everything about *how* to write it is in `SKILL.md`.

## The surfaces, ranked by what they cost

`core/` and the profile are **static context** — assembled into `CLAUDE.md` and paid on every turn
of every session. Everything below them is **dynamic**: paid only when it fires.

| Surface | Cost | Put a line here when |
|---|---|---|
| `core/NN-*.md` | Every turn, every project, every profile | It is universal, load-bearing, and traceable to a real incident. The highest bar in the repo. |
| `profiles/<name>.md` | Every turn, but only for that work type | It defines what "done" or "verified" means for one kind of work. |
| `skills/<name>/SKILL.md` | One `description` line, always; body on demand | It is a procedure or a reference the agent reaches for on a nameable trigger. |
| `docs/NN-*.md` | Nothing, until a human reads it | It teaches a human. The agent never auto-loads it. |
| `hooks/`, `scripts/` | Nothing — it executes | You want the behaviour enforced rather than requested. |

**The routing question is always the same:** does this need to be true on every turn, or only when
some condition fires? Only the first answer earns `core/`.

## Before adding a line to `core/`

1. **Check the budget** — `bash scripts/lint-leanness.sh <assembled-file>` (or `setup.sh --doctor`).
   Never quote a budget figure from memory or from a doc; the numbers drift and stale numbers have
   already misled once. Run the command.
2. **Apply the no-op test** (`SKILL.md`). A `core/` line that doesn't change behaviour is the most
   expensive kind of nothing in the repo.
3. **Try the ladder first.** `docs/08` and `docs/09` both route new rules toward a profile, a skill
   or a doc before `core/`. Static context is the last resort, not the default.
4. **Prefer the guard.** `core/60`: a harness edit isn't done until a check fails if the mistake
   recurs. If you find yourself writing a rule in capitals, what you want is a hook (`docs/04`).

Adding to `core/` usually means **finding a line to remove**, not finding room.

## The dual audience — why "explanation is waste" bends here

`SKILL.md` says you are writing for a reader who has already read everything, so explanation is
waste. For a pure agent-facing document that holds. `core/` files have a second reader: the human
deciding whether to trust the rule — and `core/00` requires the opposite of them, *explain the WHY
before the HOW*, because "we do X because last time Y broke" travels where "best practice says X"
does not.

Both hold, and the resolution isn't a compromise: **the WHY is the rule's completion criterion, not
decoration.** A rule naming the failure it came from is more tightly bounded than one naming a
value, so it earns its load on behaviour. What doesn't earn it is the *retelling* — the incident
belongs in a clause, not a paragraph.

So in a `core/` review, a war story is a no-op only when the rule stays just as sharp without it.
Test it the usual way: delete it and ask whether the rule's bound got vaguer. If it did, the story
was doing work.

## Why there are no numbers in this skill

`SKILL.md` gives no line count for sprawl and no break-even for disclosure, deliberately. A written
threshold is a **cache** of a lookup, and this repo has already been misled by one: `docs/04` quoted
a budget figure that drifted out of date and was believed (`docs/feedback/0007`). One number is
worth keeping, and it lives where a command can compute it — `scripts/lint-leanness.sh`. Everywhere
else the test is a question, not a figure: does every branch need this, and does deleting it change
behaviour?

## Diagnosing a rule that didn't fire

`docs/04-why-your-agent-ignored-the-rule.md` names four failure modes. Each maps to a lever here —
name the mode first, then reach for its fix:

| `docs/04` mode | What it is in `SKILL.md` terms | The fix |
|---|---|---|
| **Drowned** | **Sprawl** — the rule is live but attention thinned across the excess | Subtract. Disclose reference behind a pointer; the ladder, not tighter sentences. |
| **Vague** | A weak **completion criterion** — the agent can't tell done from not-done | Sharpen the bound. Name the concrete failure and the reason, post-mortem style. |
| **Contradicted** | **Duplication** with a second meaning attached, or correct operator precedence | Reconcile to a single source of truth — or accept it: the operator outranks the rule. |
| **Unguarded** | Prose doing a guardrail's job | A hook, a verify phase, a test. Guardrails hold what prose forgets. |

A fifth, specific to this repo: a rule that is **sediment** — still true, no longer load-bearing.
It survives because removing feels risky. The no-op test settles it.

## Writing a profile

The shape is fixed (`docs/08`): `## Profile: <Name>` → **Use this profile when** → what "done" and
"verified" mean → a load-bearing block → `### Quality gates` → failure modes → recommended tools →
STOP-table addendum. Two rules from `SKILL.md` bite hardest here:

- **Reference core rules by number (R2, R10), never restate them.** A profile that re-explains R2
  has duplicated it into static context twice over.
- **Gates are demand, not description.** "Rendered and read" is a gate; "check the output" is not.

## Writing a skill description

The `description` is a **context pointer** and the only part of a skill that is always loaded — so
it gets the harshest pruning in the repo. One trigger per branch, leading word first, and cut the
identity the body already carries. If the skill only ever fires because a human typed its name, it
does not need trigger branches at all.

## Writing a subagent prompt

`core/40` fixes what a subagent prompt carries. Read it as completion criteria: the report format
(*"under ~150 words: what changed, where, and any surprises"*) is a **clarity** bound, and naming
the spec excerpt and known deviations is **demand** — it forces the legwork of reconciling
plan against reality instead of trusting the plan.

A subagent dispatch is also the one place where hiding post-completion steps genuinely works: it is
a real context boundary, so the later steps are not merely out of sight, they are absent.
