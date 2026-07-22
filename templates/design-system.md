<!--
  DESIGN.md — the design system for this project's UI.
  Scaffolded by the harness (software-dev profile). This is the single source of truth for how the
  UI looks; the agent reads it before writing or changing any UI and matches it. Keep it in the
  project root so tools (and coding agents) find it by convention.

  THREE WAYS TO FILL IT — pick one, then delete the [TODO]s:
    1. Bring your brand. You already have a brand guide / existing product. Transcribe the palette,
       type, spacing, and component rules into the sections below. Most durable — it's YOUR system.
    2. Pick a ready-made one. Copy a DESIGN.md from the awesome-design-md catalog and adapt it:
       https://github.com/VoltAgent/awesome-design-md  (files live at design-md/<brand>/DESIGN.md).
       Or scaffold it at setup:  ./setup.sh --profile software-dev --design-system catalog:<brand>
    3. Generate one. The ui-ux-pro-max skill produces and persists a full design system from a brief:
         /plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
         /plugin install ui-ux-pro-max@ui-ux-pro-max-skill
       Its MASTER.md can point at this DESIGN.md so the two stay in sync.

  Format follows the awesome-design-md convention (frontmatter + the H2 sections below) so external
  tools recognize it. While DESIGN.md still reads "[TODO: set DESIGN_SYSTEM]", nobody has chosen a
  design system yet — the agent will stop and ask, or (worse) invent one. Fill it before building UI.
-->
---
name: [TODO: set DESIGN_SYSTEM]        # e.g. "Acme Console — dark-first product UI"
description: [TODO: one or two sentences on the overall look and the feeling it should evoke]
colors:
  primary: "[TODO: #hex]"
  # add the rest of your roles (background, surface, text, accent, success, warning, danger)
---

## Visual Theme & Atmosphere

[TODO: the overall mood in a few sentences — light or dark first, dense or airy, playful or serious,
flat or layered. What should someone feel in the first second? Name the one idea every screen serves.]

## Color Palette & Roles

[TODO: list each color as a role, not just a swatch — background, surface/card, primary/action,
text-primary, text-muted, border, success/warning/danger. Give the hex and WHEN to use it. State the
contrast rule you hold to (e.g. body text ≥ 4.5:1). No off-palette hues, no "close enough".]

## Typography

[TODO: the type families (display / body / mono), the scale (sizes + line-heights), the weights you
use and don't, and letter-spacing rules. When is bold allowed? What's the smallest legible size?]

## Component Stylings

[TODO: the recurring components and their rules — buttons (variants, radius, padding, states),
inputs, cards, tables, modals, nav. Radius, border, shadow, and the hover/active/focus/disabled
states. This is what stops every screen from reinventing a button.]

## Layout Principles

[TODO: the spacing scale (e.g. 4/8px grid), container widths, gutters, and how density is decided.
Alignment and grid rules. What "breathing room" means here.]

## Depth & Elevation

[TODO: how layering is expressed — shadows, borders, overlays, blur. The elevation levels and what
sits at each. Flat, or soft-shadowed, or hard-edged?]

## Do's and Don'ts

[TODO: the short list that prevents the most common drift.
- Do: …
- Don't: …]

## Responsive Behavior

[TODO: breakpoints, what reflows vs. what hides, touch-target minimums, and how the layout adapts
from mobile to wide. What's the smallest screen you support?]

## Agent Prompt Guide

[TODO: the one paragraph you'd paste to a coding agent so it builds on-system UI without reading the
rest of this file — the palette, the type, the component library, and the single most important rule.
Update this whenever the system changes.]
