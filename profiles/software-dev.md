<!-- PROFILE · software-dev -->
## Profile: Software Development

**Use this profile when** the unit of work is code that builds, runs, and is tested —
features, bug fixes, refactors, libraries, services, CLIs. Language-agnostic
(Go, Python, JS/TS, Rust, …); read commands from `.harness/verify.conf`.

### What "done" and "verified" mean here
Sharpens R2, R3 and R5. "Verified" has two distinct gates — pass both:

- **Within a layer (automated):** build, type-check, lint and the **full** test suite pass, and
  every behaviour change has a test you saw fail for the intended reason before the fix.
- **Across layers (exercised):** the changed path was actually run — a real invocation, a request
  through the running service, a click-through in the UI — and one concrete value was traced
  through every fan-out consumer it reaches (each route, caller, callback, config variant).
  Exercise it **as the real caller**: anonymous, another tenant, the user's permissions — not with
  your own credentials or hermetic stubs.

"It compiles and the unit test passes" is within-a-layer evidence only. If a human could click a
button and see it break, you haven't verified it.

**UI work:** if the project has a UI, `DESIGN.md` at the root is its design system. Read it before
changing UI and update it in the same unit when you add or restyle a component; if it is missing
or still `[TODO]`, establish one first (`docs/11-designing-uis.md`).

### Quality gates
Before calling code done, tick each — "deferred: reason" is allowed, silence is not:

- [ ] `agentsmith verify` passes (it chains the phases in `.harness/verify.conf`: build →
      typecheck → lint → tests; edit the conf, not the call sites)
- [ ] the changed path was **run for real** once, including every fan-out consumer (R3)
- [ ] UI changes match `DESIGN.md` (or `DESIGN.md` updated to match) — inert without a UI
- [ ] code touching auth, user input, or secrets got a **named** security pass —
      authorization enforced server-side at the handler (not the caller), input
      parameterized/escaped at the sink, no credential in the diff. Name what you
      checked; "looks fine" is not a pass
- [ ] new/changed dependencies carry no known high/critical CVE (`npm audit` /
      `pip-audit` / `govulncheck` / `cargo audit` — whichever your stack has)
- [ ] a defect is recorded for anything found-but-not-fixed (R7)

**Before merge, risky diffs get a second, independent pass** — a different model or reviewer that
*tests* (writes or runs tests, reproduces the bug), not only reads. A checker that measures beats
one that only reads (`docs/03-verify-means-evidence.md`). Skill suggestions: `skills/RECOMMENDED.md`.

### Addendum to the STOP table

| Thought | Reality |
|---------|---------|
| "It compiles / unit tests pass, so it works." | That's within-a-layer green. Run the real path across layers before "done" (R3). |
| "It's internal-only, nobody can reach it." | Internal today, exposed after the next routing change. Enforce authz at the handler, not at the caller. |
| "The scanner was clean, so it's secure." | Clean means no *known pattern* matched. Auth and ownership bugs are logic, not patterns — trace one request from an unauthorized caller. |
