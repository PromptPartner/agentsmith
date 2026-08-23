# core/40 — findings from the first `/writing-rules` review pass

> Working notes. Do not delete; if superseded, move to `docs/research/_archive/` (R9).

## Question / scope

Does the `writing-rules` skill actually work when run? Test: hand a subagent **only**
`skills/writing-rules/SKILL.md` and `core/40-subagents-and-tools.md`, tell it to follow the review
pass literally, forbid any other methodology, and see what comes back. Read-only.

Two outputs: findings about `core/40` (below), and findings about the skill itself — those were
acted on immediately in commit `1632e4e`.

**Status: NOT ACCEPTED. Candidates awaiting an editorial pass.** Per the skill's own offline
evidence bar, a review with no run behind it yields candidates, not verdicts. `core/40` is static
context — 57 lines paid on every turn of every session — so a 43% cut is a real editorial decision,
not a cleanup. Recorded here so it isn't re-derived.

## Findings (subagent's, verbatim in substance)

Claimed **~25 of 58 lines deletable (~43%)**.

| # | Snippet | Mode named | Proposed fix |
|---|---|---|---|
| 1 | "Keep it on the main thread when the task touches multiple areas…" | duplication | Inverse of the dispatch conditions on the same axes; make main-thread the else-branch |
| 2 | "don't deliberate out loud each time" | negation + duplicates its own heading | Keep only "State the routing decision in one line." |
| 3 | "A subagent's final message is data for you… relay what matters." | cache | The Agent tool description already says it — free lookup |
| 4 | `### When to reach for a multi-agent workflow` (8 lines) | ladder violation | A branch only rare work reaches, paid every turn → disclose behind a pointer |
| 5 | "don't spin up a fleet for a small job (Rule 10…)" | duplication + negation | Restates Routing and R10 |
| 6 | Four explanatory clauses ("tens of thousands of tokens", "clearer for the human watching", "training data may be stale", "cheaper than shipping a wrong API call") | no-op | Delete the sentences, keep the instructions |
| 7 | "Never call a raw 'show me everything' endpoint to browse." | negation | Positive already present ("filter tightly", "minimum you need") |
| 8 | "A denied tool call is a signal… don't retry the same thing verbatim." | duplication + negation | Duplicates Failure recovery |
| 9 | "Blind retries burn the context window… four fix-on-fix commits" | no-op | War story |
| 10 | "Cap the flailing: when you've spent more turns thrashing than the task is worth" | duplication + vague criterion | Replaces a countable bound (two strikes) with an uncountable one |
| 11 | "Where a runtime can enforce this… prefer the deterministic limit over willpower." | no-op for the running agent | Addressed to the harness author; duplicates `core/60` |
| 12 | Failure-recovery heading + first two sentences | duplication | Three statements of one idea; collapses to *circuit-breaker* |

## Assessment — where I disagree with the reviewer

Findings are not equal, and taking them at face value would be the mistake `core/10` warns about.

- **Strong (act on these).** #1, #2, #5, #7, #8, #12 — structural duplication and negation, checkable
  against a surviving source of truth without running anything. #10 is the sharpest of the set: a
  countable bound ("about twice the same way") really is silently weakened by an uncountable one
  sitting beside it.
- **Contested — #6 and #9, the "war story" cuts.** These collide head-on with `core/00`: *"Explain
  the WHY before the HOW. 'We do X because last time Y broke' beats 'best practice says X.' Reasons
  travel; rules don't."* The reviewer flagged this conflict itself, calling the dual audience an
  unaddressed gap, and decided the clauses were waste on its own authority. That gap is now closed
  in `HARNESS-SURFACES.md` ("the WHY is the rule's completion criterion, not decoration"), and under
  that rule these need re-testing one at a time: delete the clause, ask whether the bound got
  vaguer. Some will survive. A blanket cut here would strip the harness of the reasons that make its
  rules portable — the single trait `core/00` says matters most.
- **Needs judgement — #3 and #4.** #3 is right that the runtime describes subagent returns, but a
  harness that only works when a specific runtime says so is not tool-neutral, and tool-neutrality is
  a stated design goal. #4 (disclosing the multi-agent section) is a genuine ladder call and probably
  correct, but it's the one change that alters what a whole class of session sees.

## Open questions / what was NOT checked

- No other `core/` file was reviewed. If `core/40` really is ~40% padding, the other six are
  unmeasured, and a full pass is the natural follow-on — with the caveat above about war stories.
- Nothing here was verified by running an assembled `CLAUDE.md` with the cuts applied. That is the
  evidence the skill demands and this note does not have.
- The reviewer could not consult `HARNESS-SURFACES.md` (the test forbade it) — the file that exists
  precisely for reviewing a harness surface. A re-run with it in scope would likely produce a
  different, better-calibrated set. **That re-run is the obvious next step, and it should happen
  before any of these cuts land.**
