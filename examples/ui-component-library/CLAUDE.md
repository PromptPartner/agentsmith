# Project: Facet UI

Facet UI is a small in-house **React component library** — the shared buttons, inputs, cards,
tabs, badges, and nav that every internal app builds screens from. It is a UI project, so its
"user-facing surface" is the rendered components and the design system they implement. That design
system is **adopted, not invented**: it's the **Linear** system pulled from the
[awesome-design-md](https://github.com/VoltAgent/awesome-design-md) catalog and it lives in
[`DESIGN.md`](DESIGN.md) at the project root (see that file's header). Operator: **Devon Rhodes**
(frontend engineer). Work is tracked as **GitHub** issues and PRs.

## Stack & layout

- **React 18 + TypeScript** (strict), built as a library (ESM + CJS + `.d.ts`) with **tsup**.
- **Storybook** for component dev/docs; **Vitest** + **Testing Library** for unit/interaction
  tests; **@storybook/test-runner** (`test-storybook`) for accessibility + play-function checks.
- **ESLint** + **Prettier**; **Changesets** for versioning the public package.
- **Design tokens** in `src/tokens/` are the code mirror of `DESIGN.md` — one source, two forms.
- Key directories/files:
  - `DESIGN.md` — the design system (the adopted Linear system). The spec every component matches.
  - `src/tokens/` — colors, type, spacing, radius as TS tokens, derived from `DESIGN.md`.
  - `src/components/<Name>/` — one folder per component: `<Name>.tsx`, `<Name>.stories.tsx`,
    `<Name>.test.tsx`, `index.ts`.
  - `src/index.ts` — the public barrel; what consumers import. This file *is* the API surface.
  - `.harness/verify.conf` — the verify phases; `scripts/verify.sh` runs them in order.

## What "done" means here

The profile's loop (read → failing test → implement → verify → commit) and its two-gate "verified"
(within-a-layer **and** across-layers) apply as-is — and because this is UI, the profile's
**"read `DESIGN.md` before any UI change and match it"** rule is live. Facet sharpens all of that:

- **Tokens are the single source — no raw hex in components.** Every color, space, radius, and type
  value comes from `src/tokens/` (which mirror `DESIGN.md`). A literal `#5e6ad2` typed into a
  component is a bug even if it looks right, because the next token change won't reach it. If a value
  you need isn't a token, it isn't in the design system yet — add it to `DESIGN.md` first.
- **Every interactive component ships all its states.** Default, hover, active, `:focus-visible`,
  and disabled — matching `DESIGN.md` (e.g. `button-primary` → hover `#828fff`, a 2px
  `primary-focus` focus ring). A component missing `:focus-visible` is not done, it's half-drawn.
- **Accessible by default.** Keyboard-operable, correct ARIA role/name, a **visible focus ring**
  (never `outline: none` without an equal replacement), and contrast **≥ 4.5:1** for body text
  (≥ 3:1 for large). The `a11y` verify phase (Storybook a11y addon via `test-storybook`) is the
  deterministic floor; it does not replace reading `DESIGN.md`.
- **A component = its story + its test.** The `.stories.tsx` is the living doc *and* the surface the
  a11y/interaction runner exercises; the `.test.tsx` asserts behavior and the states above. No
  component lands without both.
- **The public API is the contract.** Exported prop types are semver-relevant. Renaming/removing a
  prop, or adding a *required* one, is a **breaking change** → a Changeset + a `CHANGELOG` entry in
  the **same** PR (R6). Consumers pin to this; a silent prop rename is the front-end version of the
  API-contract drift the profile's R3 trace catches.
- **`DESIGN.md` moves with the code (R6).** Add, rename, or restyle a component pattern and you
  update `DESIGN.md`'s `components:` section in the *same* commit. The spec and the code drift apart
  the instant one moves without the other — and here the spec is what the next agent reads first.

A concrete across-layers trace (the R3 five-liner, in the PR body before commit) for the accent
color: `DESIGN.md` declares `primary: "#5e6ad2"` → `src/tokens/color.ts` exports it as
`color.primary` → `<Button variant="primary">` sets its background to `color.primary` → the Button
story renders that exact lavender → a consuming app imports `Button` and sees the same lavender on
its CTA. If the token is right in `DESIGN.md` but a component hardcodes a different hex, only the
trace — not a green unit test — catches that the CTA is off-system.

## verify.conf phases

`scripts/verify.sh` reads `.harness/verify.conf` and runs these top-to-bottom; the **first failure
stops the run** so you fix the earliest break instead of chasing a cascade:

1. **`format` — `prettier --check .`** — mechanical and cheapest; a diff means "run `prettier`,"
   not "think." Runs first so nothing downstream argues about whitespace.
2. **`lint` — `eslint .`** — unused imports, bad hooks deps, a11y lint rules (`eslint-plugin-jsx-a11y`)
   before the slower type/test phases spend time on code we already know is wrong.
3. **`types` — `tsc --noEmit`** — the prop types *are* the public contract; `tsc` catches a changed
   or missing prop type statically, cheaper than a test run, and guards the semver promise above.
4. **`test` — `vitest run`** — the full unit/interaction suite. Run the *whole* suite, not just your
   new test (R5) — a shared token change can break a component you didn't touch.
5. **`build` — `tsup src/index.ts --dts --format esm,cjs`** — actually bundle the library. This is
   the cheapest catch for a broken **public export** (a component removed from `src/index.ts`, a
   type that doesn't emit) — a thing unit tests pass right over.
6. **`a11y` — `test-storybook`** — last, because it needs the built stories running: the Storybook
   test-runner executes each story's play function and the a11y addon (axe) against the real DOM.
   This is the deterministic part of "accessible by default"; the judgment part is the design-review
   skill below.

## Conventions

- **Commit scope = the area touched:** `feat(button): …`, `fix(tokens): …`, `feat(card): …`,
  `docs(design): …` (a `DESIGN.md` change), `chore(release): …`. The message says WHY (profile R4).
- **One component per PR.** A button change and a card change are two PRs — atomic, reviewable,
  revertible.
- **Story + test are colocated** with the component and are part of the change, never a follow-up.
- **No off-token values.** Colors/space/radius/type come from `src/tokens/`; a raw hex or a magic
  `13px` in a component fails review even if `verify.sh` is green (that's what design-review is for).
- **Every public change ships a Changeset.** `npx changeset` in the same PR; the changelog is
  generated from these, so callers see breaking vs. additive at a glance.

## Gotchas & decisions

- **The design system is adopted from the catalog, not authored here.** `DESIGN.md` is the Linear
  system fetched by `--design-system catalog:linear.app` (see its header). If you fork Facet for a
  different brand, **adapt `DESIGN.md` first** (palette, type, name) — then the tokens, then the
  components. Don't diverge the components from `DESIGN.md` and backfill the spec later.
- **We don't ship the proprietary fonts.** `DESIGN.md`'s Typography note calls Linear's typefaces
  proprietary and names substitutes; Facet uses **Inter** (500/600/700) and **JetBrains Mono**. The
  token file records the substitute so no component reaches for an unavailable family.
- **Never delete a focus outline for looks.** An early card grid set `outline: none` for a "cleaner"
  look and shipped a keyboard-untraversable form. `:focus-visible` styling is mandatory and the
  `a11y` phase now fails on a missing focus indicator — this is why that rule rarely needs a human.
- **`test-storybook` needs Storybook running.** CI builds Storybook and serves it before the `a11y`
  phase; locally, run `storybook dev` in another terminal first, or the phase errors on connection,
  not on a real a11y failure.
- **Dark-only, on purpose.** `DESIGN.md` documents no light theme ("Don't ship a light-mode…") and
  lists it as a known gap. Don't invent light tokens ad-hoc; if light mode is needed, **establish it
  in `DESIGN.md` first** (the profile's "missing/incomplete design system ⇒ stop and establish" rule),
  then implement.
