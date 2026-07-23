# Designing UIs — the design-system workflow

Product UI is `software-dev` work. Not `creative-design` — that profile is for diagrams, decks, and
brand artifacts where the picture *is* the deliverable. A web or app frontend is code that builds,
runs, and is tested, so it lives under [`software-dev`](07-how-to-pick-a-profile.md). But UI has a
second correctness axis that backend code doesn't: it has to look *coherent*. Every screen has to
speak the same visual language — the same palette, type, spacing, and components — or the product
reads as if five different people built it.

The harness treats that axis the way it treats every other correctness axis: name the thing that
makes work "done," write it where the agent will actually see it, and guard it. For UI, that thing
is a **design system**, and its home is a `DESIGN.md`.

## Why this exists (a real incident)

Running the harness on a real project, the agent built a license-key portal without applying the
project's chosen design system until it was explicitly told to — and setup never pushed for one. The
[post-incident](feedback/README.md) traced it to a plain configuration gap: `software-dev` was 100%
code-correctness (tests, verify, atomic commits) with **zero** design-system content. "Design system"
appeared exactly once in the whole harness. So the agent did the only reasonable thing — it treated
the look as the operator's concern, never a rule. That's the [core lesson](04-why-your-agent-ignored-the-rule.md)
of the whole harness: *most agent failures are configuration failures.* The fix was to add the rule,
not to blame the model.

## The artifact: `DESIGN.md`

A `DESIGN.md` at the project root is the single source of truth for how the UI looks. It follows the
[awesome-design-md](https://github.com/VoltAgent/awesome-design-md) convention — a plain-Markdown
design spec (visual theme, color roles, typography, components, layout, elevation, do's & don'ts,
responsive behavior, an agent prompt guide) that coding agents read best. The agent reads it **before
writing or changing any UI**, and matches it.

Why a durable file rather than a one-off instruction:

- **It persists.** A fresh session has zero memory of the last one (that's the whole
  [handoff](02-your-first-hour.md) premise). A palette you explain in chat is gone next session; a
  palette written into `DESIGN.md` is read every time. This is the same "establish once, write it
  down" mechanism the `creative-design` profile uses for its brand block — generalized to product UI.
- **It's the interchange format.** External tools speak it: drop in a ready-made file from the
  catalog, or have a generator write one. No bespoke config.

## Establishing one — three ways

Pick per project (the [`software-dev` profile](../profiles/software-dev.md) tells the agent to stop
and do this if `DESIGN.md` is missing or still `[TODO]`):

1. **Bring your brand.** You already have a brand guide or an existing product — transcribe the
   palette, type, spacing, and component rules into `DESIGN.md`. Most durable: it's *your* system.
2. **Pick a ready-made one.** Copy a `DESIGN.md` from the
   [awesome-design-md catalog](https://github.com/VoltAgent/awesome-design-md) (50+ brand systems)
   and adapt it.
3. **Generate one.** The `ui-ux-pro-max` skill produces and persists a full design system into
   `DESIGN.md` from a brief (needs Python 3). See [`skills/RECOMMENDED.md`](../skills/RECOMMENDED.md).

Do it at install and setup scaffolds the file for you:

```bash
./setup.sh --profile software-dev --design-system stub            # empty template to fill in
./setup.sh --profile software-dev --design-system catalog:stripe  # a ready-made one from the catalog
./setup.sh --profile software-dev --design-system generate        # print the ui-ux-pro-max steps
```

The wizard (bare `./setup.sh`) asks "Does this project have a UI?" and offers the same three paths.
An unfilled `DESIGN.md` is surfaced at setup end as a `DESIGN_SYSTEM` TODO, so it doesn't ship blank.
Full flag reference: [`12-whats-built-in.md`](12-whats-built-in.md).

## How the harness holds UI to it

Four layers, each matched to what it can actually enforce:

- **The rule (sticky, every turn).** The `software-dev` profile carries a "Design system (UI work)"
  section that assembles into `CLAUDE.md`: read `DESIGN.md` before touching UI and match it; if it's
  missing or `[TODO]`, establish one first; update it in the same unit of work when you add, rename,
  or restyle a component ([R6](03-verify-means-evidence.md) — finish the whole change, including the
  spec). **No UI? The section is inert** — backend, CLI, library, and data work skip it entirely.
- **The quality gate + STOP row.** A checkbox ("UI changes match the design system declared in
  `DESIGN.md`") joins the [software-dev quality gates](10-best-practices.md), and a STOP-table row
  catches the rationalization "I'll match the design system later" — *later is the off-brand screen
  that ships.*
- **The nudge hook (deterministic).** `hooks/ui-design-reminder.sh` is a once-per-session, non-blocking
  PreToolUse reminder that fires when the agent edits a UI file (`.tsx/.jsx/.vue/.svelte/.css/…`, or a
  `components/`/`ui/` path) **and** a `DESIGN.md` exists at the root. It self-gates on that file, so
  backend projects never see it, and it never blocks the edit. Install it with `--with-ui-design-hook`;
  details in [`hooks/README.md`](../hooks/README.md).
- **What it deliberately does *not* do.** It does **not** try to machine-verify adherence.
  "Does this screen match the design system?" is a judgment call, not a grep — and a green check that
  lies is worse than no check ([verify means evidence](03-verify-means-evidence.md)). So the
  [`verify.sh`](12-whats-built-in.md) preset for `software-dev` is unchanged; adherence is held by the
  rule, the gate, the STOP row, and the nudge, with a human or an agent making the call.

## The workflow in practice

1. **Establish** the design system at setup (or drop a `DESIGN.md` in later).
2. **Fill it** — resolve the `[TODO]`s from your brand, a catalog file, or a generator.
3. **Build** — the agent reads `DESIGN.md` before each UI change and matches it; the hook nudges if it
   forgets.
4. **Keep it in sync** — when a component changes, `DESIGN.md` changes in the same commit (R6). The
   design system and the code drift apart the instant one moves without the other.

That's the whole loop. It rides the same rails as the rest of the harness — sticky content in
`CLAUDE.md`, a `[TODO]` surfaced at setup, a durable per-project artifact, and a deterministic guard
for the mechanical part — so there's nothing new to learn beyond "product UI expects a `DESIGN.md`."

**See it worked out.** [`examples/ui-component-library/`](../examples/ui-component-library/README.md)
is this whole loop as a finished project — *Facet UI*, a React component library that adopts the
Linear system from the catalog (`--design-system catalog:linear.app`) and holds every component to
it, with a bundled `design-review` skill for the judgment pass `verify.sh` can't do.
