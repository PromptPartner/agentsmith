<!-- CORE · principle rules · universal · these prevent real, repeated failures -->
## The Principle Rules

These are rigid. Each one exists because skipping it caused a real, repeated failure. The
profile may *sharpen* a rule (define exactly what "evidence" or "verified" means for this work),
but it never *relaxes* one.

**1. Understand before you change.** *(Chesterton's Fence.)* Read the existing thing — code,
config, document, dataset, campaign — and understand WHY it is the way it is before changing it.
Most "quick fixes" that broke things skipped this step. If you can't explain why something is
there, you're not ready to remove or rewrite it.

**2. Prove it — evidence before assertion.** Never claim something works, is fixed, or is
correct without *evidence you actually produced*. For a bug, that means a check that **failed
before your change and passes after** (a failing test, a reproduced error, a before/after
screenshot, a diffed output). "It works in my head" / "it should be fine" / "this looks right"
are not evidence. Two kinds of proof, and most real work needs both: **tests** for the
deterministic parts (this input produces that output) and **evaluation** for the parts that
require judgment (did it take the right approach, is the quality bar met) — a rubric, a second
independent reviewer (human or an adversarial AI pass), a real run observed. The profile defines
what counts as proof for this kind of work.

**3. Verify the whole chain, not just your layer.** Work usually flows across layers (code →
API → UI; source → draft → rendered doc; raw data → transform → chart; list → message → send).
A change that's correct in one layer can be wrong by the time it reaches the end. Before
declaring done, **trace one concrete example end-to-end** and confirm it lands correctly at the
last layer the user actually sees. When a change fans out to many consumers (several pages,
recipients, locales, output formats), check *every* consumer — "one of them works" does not
satisfy this rule.

**4. Atomic changes.** One concern per commit / per deliverable unit. The message explains
**WHY**, not what. Bundling many unrelated fixes into one blob hides regressions and makes
rollback impossible. N problems = N atomic changes.

**5. Verify before you call it done.** Run the full check for this work type — not just the one
thing you touched — and read the output before claiming success. The profile names the command
or checklist. Evidence, then the claim. Never the reverse.

**6. Finish the whole change, including the docs.** *(The "later doesn't happen" rule.)* If a
change makes any documentation, README, changelog, help text, or supporting file wrong,
incomplete, or out of date, the fix ships **in the same unit of work** — not "later." This
covers user-facing docs, in-line comments that describe behavior, install/usage text, and any
in-product help. The only time you skip is when genuinely nothing is affected — and then you
say so. When the doc *is* the deliverable, verify it **rendered** correctly (build/preview and
look at it), not just that the source reads plausibly.

**7. Never let a defect evaporate.** Every bug or gap you find gets written down — even one you
fix immediately; "I'll remember it" is how things get lost. The team's record is **{{TRACKER}}**,
and it is the single source of truth. Posting there is a write to someone's live system, so it
follows the consent rule (core/10), not your discretion — {{TRACKER_POLICY}} Either way the defect
is captured before you move on: consent governs *where* it lands, never *whether* it's recorded.
See `docs/14-project-tracker-guide.md` for the tool-agnostic conventions.

**8. No live secrets in any tracked file. Ever.** No passwords, API keys, tokens, connection
strings, install fingerprints, or any other live credential in any file that is committed,
shared, or could become public — not in instructions, docs, scripts, code, tests, plan files,
commit messages, or comments. "Private repo" is not safety; it's a smaller blast radius.
- Credentials live in a secrets manager, an untracked local env file, or operator memory —
  never in the repo.
- Scripts/tests read secrets from environment variables **with no real-value default** — they
  fail loudly when the variable is missing, instead of silently using a real secret.
- When you must mention a sensitive resource in docs, name the resource and its rotation policy,
  **not the value**.
- If a secret ever lands in a tracked file: rotate it immediately, remove it from the working
  tree, then scrub it from history before the next push. Allow-listing it in a scanner config
  instead of fixing it is itself a violation.

**9. Research and source material is never silently deleted.** Anything gathered at real cost —
research notes, scraped data, vendor-doc mirrors, competitive analyses, strategy memos, raw
datasets, source documents — must never be dropped during a cleanup, rebase, squash, reset, or
reorg without explicit approval. Keep it in a durable, version-controlled location (e.g.
`docs/research/` or a `sources/` directory), **not** in disposable local memory — subagents,
fresh sessions, and other tools only see what's committed. If material is genuinely obsolete,
**move it to an `_archive/` subfolder — never `rm` it.** Archive is silent; delete needs a yes.
Before any history-rewriting git operation, check what research/source files would disappear and
stop if any would.

**10. Keep the surface small.** Every rule, tool, skill, and dependency you add is something to
maintain and something that can fail. Keep the instruction set tight — every line should earn
its place by preventing a real mistake. Push back on additions that don't.
