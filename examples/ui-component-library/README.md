# Example: Facet UI — React component library (software-dev profile)

**Scenario.** Facet UI is a small in-house **React component library** — TypeScript, built with
tsup, documented in Storybook, tested with Vitest. It's the shared button/input/card/nav kit every
internal app builds screens from. The operator is Devon Rhodes, a frontend engineer who tracks work
as GitHub issues/PRs. This folder shows what the harness looks like *layered onto a UI project*:
the universal core is installed globally on Devon's machine, and the project carries the software-dev
profile, a **design system adopted from a catalog**, and the UI-edit nudge hook.

This is the harness's **design-system feature** worked out end to end. Product UI is `software-dev`
work (not `creative-design`) — see [`docs/11-designing-uis.md`](../../docs/11-designing-uis.md) — and
UI has a correctness axis backend code doesn't: every screen must speak one visual language. The
harness names that axis in a root [`DESIGN.md`](DESIGN.md) and holds the UI to it.

**Set it up like this:**

```bash
# 1) Install the universal core once, globally (Devon's machine, all projects):
./setup.sh --global --operator-name "Devon Rhodes" --operator-role "frontend engineer"

# 2) Layer software-dev onto THIS repo, ADOPT a ready-made design system from the catalog, and
#    install the UI-edit nudge hook (no core copied in — core is global):
./setup.sh --profile software-dev --profile-only --target . \
  --operator-name "Devon Rhodes" --operator-role "frontend engineer" \
  --tracker github --with-hooks \
  --design-system catalog:linear.app --with-ui-design-hook
```

**What to notice.**

- **`DESIGN.md` is the single source of truth for how the UI looks — and here it came from the
  catalog.** `--design-system catalog:linear.app` fetches the Linear system from
  [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) and drops it in as `DESIGN.md`
  (that's [path #2 of three](../../docs/11-designing-uis.md#establishing-one--three-ways) — *bring
  your brand*, *pick a ready-made one*, *generate one*). The file here is that fetched system, with
  only an attribution header added — it's exactly what the flag produces. The agent reads it **before
  writing or changing any component** and matches it.
- **The design system is *adopted*, then it's the law.** Facet didn't invent a palette; it took a
  coherent one and made it the contract. `CLAUDE.md` sharpens "done" around it: tokens are the single
  source (no raw hex in components), every component ships all its states + a story + a test, the
  public prop API is semver, and `DESIGN.md` is updated in the *same* commit when a component pattern
  changes (R6).
- **The UI-edit nudge hook is deterministic, not nagging.** `--with-ui-design-hook` installs a
  once-per-session, non-blocking `PreToolUse` reminder that fires only when you edit a UI file
  (`.tsx/.css/components/…`) **and** a `DESIGN.md` exists at the root. It self-gates on that file, so
  backend projects never see it, and it never blocks the edit — see [`hooks/README.md`](../../hooks/README.md).
- **Adherence is a judgment call, not a grep.** `.harness/verify.conf` checks the *mechanical* floor
  — `format → lint → types → test → build → a11y`. It deliberately does **not** try to machine-verify
  "does this match the design system?", because a green check that lies is worse than no check. That
  axis is held by the profile rule, the quality gate, the STOP-table row, and the bundled
  **`design-review`** skill below — a human or an agent makes the call.
- **The bundled `design-review` skill** walks a new or changed component against `DESIGN.md` (tokens,
  states, contrast, responsive, and whether `DESIGN.md` itself moved with the code). Like
  python-service's `release-check`, it loads only when you need it, keeping everyday context lean.

**Files here:**

- `README.md` — this file.
- `CLAUDE.md` — the project-specifics layer (Facet's stack, "done" for a component library, gotchas).
- `DESIGN.md` — the adopted design system (the Linear system from the catalog; attribution in its header).
- `.harness/verify.conf` — the concrete verify phases for this component library.
- `.claude/skills/design-review/SKILL.md` — a small bundled skill for reviewing a component against `DESIGN.md`.
