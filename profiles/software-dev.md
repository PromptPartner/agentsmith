<!-- PROFILE · software-dev -->
## Profile: Software Development

**Use this profile when** the unit of work is code that builds, runs, and is tested —
features, bug fixes, refactors, libraries, services, CLIs. Language-agnostic
(Go, Python, JS/TS, Rust, …); read commands from `.harness/verify.conf`.

### What "done" and "verified" mean here
The sequence for every code change (sharpens R2/R5):

1. **Read** the code you're about to touch and the code that calls it (R1).
2. **Failing check first** — write a test that fails for the right reason and
   prove it fails. No red test = no proof = no fix (R2).
3. **Implement** the smallest change that turns it green.
4. **Verify** — run the project's full verify command and read the output, not
   just the test you wrote (R5).
5. **Commit** atomically, message says WHY (R4).

"Verified" has two distinct gates — pass both:

- **Within a layer (automated):** build, type-check, lint, unit/integration
  tests pass. These prove the code is internally correct.
- **Across layers (exercised):** the changed path was actually run — a real
  invocation, a request through the running service, a click-through in the UI.
  Automated green does NOT prove the feature works end to end. Trace one
  concrete value through every layer and every fan-out consumer it reaches
  (each route, caller, callback, config variant) before claiming done (R3).

"It compiles and the unit test passes" is within-a-layer evidence only. If a
human could click a button and see it break, you haven't verified it.

### Quality gates
Before calling code done, tick each — "deferred: reason" is allowed, silence is not:

- [ ] `<your build cmd>` succeeds (no warnings you introduced)
- [ ] `<your typecheck cmd>` clean
- [ ] `<your lint cmd>` clean
- [ ] new/changed behavior has a test that failed before the fix (R2)
- [ ] the **full** test suite passes, not just the new test (R5)
- [ ] the changed path was **run for real** once (CLI invocation / live request /
      browser click-through), including every fan-out consumer (R3)
- [ ] docs, changelog, help text, and inline comments that the change made wrong
      are fixed in this same unit (R6)
- [ ] a defect ticket exists for anything found-but-not-fixed (R7)

Single entry point: run `scripts/verify.sh` (it should chain build → typecheck →
lint → tests). The actual commands live in `.harness/verify.conf` so the script
and the human stay in sync — edit the conf, not the call sites. If `verify.sh`
doesn't exist yet, create it to wrap the conf; never scatter raw commands across
sessions.

### Failure modes to guard against
- **Fix-on-fix spiral.** Skipping R1, you patch a symptom, it breaks elsewhere,
  you patch that. Stop after the first surprise and re-read until you understand
  WHY the code was the way it was.
- **"Passes CI but broken across layers."** Every automated check is green and
  the feature is still dead because the bug lives in the seam between layers.
  This is exactly what the across-layers gate above catches — run the path.
- **Contract/data-flow mismatch.** Backend field, API key, and UI prop drift
  apart (wrong casing, renamed field, wrong endpoint). The 5-line value trace
  (R3) exposes these before commit; "one consumer works" does not.
- **Batch squash.** N unrelated fixes in one commit hides which change caused the
  new bug and defeats bisect. One concern per commit (R4); split or stack.
- **Shipping without tests.** "Too small to test" / "tests later" is how a sprint
  ships a pile of regressions. Red test first, every time (R2).
- **Stale-workspace noise.** Compiler/LSP errors pointing at a sibling worktree or
  a path your branch doesn't use are stale. Trust the build/typecheck command's
  output, not editor popups.

### Recommended skills & tools
Map to the loop — pull these in, don't reinvent them:

- **Before building:** `superpowers:brainstorming` (intent + design), then
  `superpowers:writing-plans` / claude-mem `make-plan` for multi-step work.
- **While building:** `superpowers:test-driven-development` for the red-green
  loop; **Context7** to fetch current library/API docs instead of guessing
  signatures; language LSP plugins + language dev plugins for navigation/fixes.
- **When it breaks:** `superpowers:systematic-debugging` before proposing any fix
  (find the cause, don't pattern-match a patch).
- **Verifying:** `superpowers:verification-before-completion`; **Playwright MCP**
  for browser/UI click-through; the `verify`/`run` skills to drive the real app.
- **Before merge:** the `code-review` skill, `superpowers:requesting-code-review`
  /`receiving-code-review`, and the **codex two-AI adversarial gate** for a second
  independent pass on risky diffs — use it not just as a second *reader* but as a second
  *tester*: point Codex at the diff to independently write/run tests or reproduce the bug.
  A checker that *measures* beats one that only reads ([`03-verify-means-evidence.md`](../docs/03-verify-means-evidence.md)).
- **Isolation:** `superpowers:using-git-worktrees` for parallel/long-running work.
- **Memory:** claude-mem `mem-search` ("did we solve this before?") and
  `learn-codebase` when entering unfamiliar code.

Keep the set tight (R10) — reach for the skill when the situation calls for it,
not by default.

**If installed, use them; if not, the rule still stands.** No `test-driven-development` skill? Write
the failing test first anyway (R2). No `using-git-worktrees`? Still isolate risky/parallel work on a
branch. No `code-review`/codex gate? Do the second-pass read — and an independent test run — yourself before merge.

### Addendum to the STOP table

| Thought | Reality |
|---------|---------|
| "Tests can come later." | Later never comes. Red test FIRST or it isn't proven (R2). |
| "It compiles / unit tests pass, so it works." | That's within-a-layer green. Run the real path across layers before "done" (R3). |
| "I'll fix all these in one commit." | One bad change hides in N and breaks bisect. Atomic only (R4). |
| "That type/lint error is in another workspace — ignore it." | Confirm with the build/typecheck command. If it's truly a sibling worktree, it's noise; if it's yours, it's a blocker — don't guess. |
| "The docs aren't really part of this change." | If the change made a doc/help/comment wrong, fixing it IS the change (R6). |
