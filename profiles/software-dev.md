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

### Design system (UI work)

**If this project has a UI, its design system is the spec for how that UI looks — and it lives in
`DESIGN.md` at the project root.** This is the product-UI analogue of the brand block in the
creative-design profile: establish the look once, write it down, and hold every screen to it.

- **Read `DESIGN.md` before you write or change any UI, and match it** — colors, type, spacing,
  components, layout, states. A screen that ignores it is off-brand the moment it ships, and that
  only shows up after the fact.
- **If `DESIGN.md` is missing or still reads `[TODO]`, STOP and establish one first.** Three ways,
  pick per project: *bring the brand* (brand guide + existing assets → write them in), *pick a
  ready-made one* (a `DESIGN.md` from the awesome-design-md catalog), or *generate one* (the
  ui-ux-pro-max skill produces and persists a design system). Then write the choice into `DESIGN.md`
  so the next session doesn't re-ask — exactly how the brand block persists a palette.
- **When you add, rename, or restyle a component, update `DESIGN.md` in the same unit of work (R6).**
  The design system and the code drift apart the instant one changes without the other.
- **No UI? This section is inert.** Backend, CLI, library, and data work have no design system to
  honor — skip it.

Adherence is a judgment rule, not something a script can grep for. It's held by the quality-gate
checkbox below, the STOP-table row, and the UI-edit nudge hook — deliberately **not** by
`verify.sh` (design correctness isn't automatable, so the verify preset stays out of it).

### Quality gates
Before calling code done, tick each — "deferred: reason" is allowed, silence is not:

- [ ] `<your build cmd>` succeeds (no warnings you introduced)
- [ ] `<your typecheck cmd>` clean
- [ ] `<your lint cmd>` clean
- [ ] new/changed behavior has a test that failed before the fix (R2)
- [ ] the **full** test suite passes, not just the new test (R5)
- [ ] the changed path was **run for real** once (CLI invocation / live request /
      browser click-through), including every fan-out consumer (R3)
- [ ] UI changes match the design system declared in `DESIGN.md` (or `DESIGN.md` updated to
      match) — inert if this project has no UI
- [ ] code touching auth, user input, or secrets got a **named** security pass —
      authorization enforced server-side at the handler (not the caller), input
      parameterized/escaped at the sink, no credential in the diff. Name what you
      checked; "looks fine" is not a pass
- [ ] new/changed dependencies carry no known high/critical CVE (`npm audit` /
      `pip-audit` / `govulncheck` / `cargo audit` — whichever your stack has)
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
- **UI built ad-hoc, ignoring the project's design system.** Components drift, every
  screen reinvents spacing/color/controls, and the product looks assembled by five
  different people. Read `DESIGN.md` first; if none exists, establish one before building UI.

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
| "I'll match the design system later." | Later is the off-brand screen that ships. Read DESIGN.md first; if none exists, establish it before building UI. |
| "It's internal-only, nobody can reach it." | Internal today, exposed after the next routing change. Enforce authz at the handler, not at the caller. |
| "The scanner was clean, so it's secure." | Clean means no *known pattern* matched. Auth and ownership bugs are logic, not patterns — trace one request from an unauthorized caller. |
