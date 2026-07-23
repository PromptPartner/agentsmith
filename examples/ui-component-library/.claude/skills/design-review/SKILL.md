---
name: design-review
description: Use when adding or restyling a Facet UI component, or before merging a UI PR — walks the component against DESIGN.md (tokens, states, a11y, contrast, responsive) so the design system is matched, not just remembered. The judgment check verify.sh can't grep.
---

# Design Review — Facet UI

`verify.sh` proves a component *builds, types, tests, and passes axe*. It cannot prove the component
**matches the design system** — "is this on-system?" is a judgment call, not a grep (see
[`docs/11`](../../../../../docs/11-designing-uis.md)). This skill is that judgment pass, as a checklist,
so a component doesn't ship looking almost-right. It loads only when you're reviewing UI — everyday
work doesn't pay for it.

## When this fires

You type `/design-review`, or you've added/restyled a component and are about to open or merge the PR.

## Before you start

Open [`DESIGN.md`](../../../DESIGN.md) and keep it beside the diff. Every check below is "does the
component agree with `DESIGN.md`?" — if you're guessing, you haven't read it recently enough.

## Checklist

Walk these in order. Stop at the first miss, fix it, restart — an off-system component is not "done."

1. **Tokens, not literals.** No raw hex, `px` font sizes, or magic radii in the component — every
   value resolves to a token in `src/tokens/` that mirrors `DESIGN.md` (`color.primary`,
   `radius.md`, `type.body`, `space.lg`). A literal `#5e6ad2` or `13px` is a miss even if it looks
   identical, because the next token change won't reach it.
2. **All states present and on-system.** Default, hover, active, `:focus-visible`, and disabled —
   each matching `DESIGN.md` (e.g. a primary button: hover → `primary-hover` `#828fff`, focus → a
   2px `primary-focus` ring). A missing state is the most common miss; check every interactive part.
3. **Accessible.** Keyboard-operable, correct ARIA role/name, a **visible** focus ring (never
   `outline: none` without an equal replacement), and contrast **≥ 4.5:1** for body text (≥ 3:1 for
   large / UI). `test-storybook`'s axe pass is necessary but not sufficient — eyeball the focus ring.
4. **Type and spacing scale.** Sizes, weights, line-heights, and letter-spacing come from the type
   scale; padding/gaps come from the spacing scale. No one-off `600` weight where `DESIGN.md` says
   `500`, no `10px` gap outside the 4px grid.
5. **Right surface and elevation.** Backgrounds use the surface ladder (`canvas → surface-1 → …`) and
   depth is carried by surface + hairline border per `DESIGN.md` — not an invented drop shadow or a
   skipped surface level.
6. **Responsive.** The component reflows per the breakpoints and holds touch-target minimums
   (CTAs ≥ 40px, ≥ 44px on touch). Check the smallest supported width, not just desktop.
7. **`DESIGN.md` moved with the code (R6).** If you added a new component pattern or variant, its
   entry exists in `DESIGN.md`'s `components:` section **in this same PR**. If the pattern you needed
   wasn't in `DESIGN.md`, it should have been added there first — fix the order, don't paper over it.
8. **Story + test cover the above.** The `.stories.tsx` shows every state (so the a11y/interaction
   runner and a reviewer both see them); the `.test.tsx` asserts them. A state with no story is a
   state no one reviews.

## Notes

- If a value you need genuinely isn't in `DESIGN.md`, **stop and establish it there first**, then
  build — don't invent an off-system value and reconcile later (that's the drift this whole example
  exists to prevent).
- Dark-only is intentional: `DESIGN.md` ships no light theme. Don't add light-mode styling here; if
  it's needed, it's a `DESIGN.md` change first, not a per-component one.
- This is a review of *adherence*, not correctness — run `scripts/verify.sh` for the mechanical gate.
  Both have to pass before merge.
