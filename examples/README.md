# Worked examples — what a real project looks like

The `profiles/` are the templates; these are six **filled-in projects** built on top of them, so
you can see the end state instead of guessing what to write. Each one is a fictional-but-realistic
project that uses the layered setup (universal **core** installed once globally, the **profile**
assembled per project, then a hand-authored **project-specifics** layer on top).

| Example | Profile | What it is |
|---|---|---|
| [`python-service/`](python-service/) | `software-dev` | **Orchard** — a FastAPI inventory microservice (Postgres, pytest). Also shows a **project-bundled skill**. |
| [`docs-site/`](docs-site/) | `document-creation` | **Lumen Docs** — an Astro Starlight documentation website. |
| [`data-analysis/`](data-analysis/) | `data-crunching` | **Tideline** — a monthly customer-churn analysis (pandas/DuckDB → report). |
| [`devops-server/`](devops-server/) | `devops-setup` | **Harbor** — a self-hosted app server on a VPS (Docker Compose + Caddy). |
| [`marketing-newsletter/`](marketing-newsletter/) | `marketing-outreach` | **Dispatch** — a weekly product newsletter & light outreach. |
| [`ui-component-library/`](ui-component-library/) | `software-dev` | **Facet UI** — a React component library that adopts a catalog design system. Shows the **design-system feature** (`DESIGN.md`) + a **bundled skill**. |

## What's in each folder

- **`README.md`** — the scenario, the exact `setup.sh` commands that produce it, and what to notice.
- **`CLAUDE.md`** — the **project-specifics layer only** (what *you* author on top of the global
  core + the profile). It does not re-emit the core or the profile — those are layered in by
  `setup.sh`; this is the part that's unique to the project. Fully filled, no `{{placeholders}}`.
- **`.harness/verify.conf`** — the project's real definition of "shippable": concrete verify phases
  (the profile's preset, filled with actual commands). One phase per line, first failure stops.
- **`.claude/skills/…`** (python-service and ui-component-library) — a project-bundled skill,
  showing that an example can carry its own skills (or plugins) — not just rules.

## How to read them

1. Skim the example whose profile matches your work (see [`../docs/07-how-to-pick-a-profile.md`](../docs/07-how-to-pick-a-profile.md)).
2. Look at its `CLAUDE.md` — that "Project specifics" shape is what you write for your own project
   after running `setup.sh`. Notice how it *sharpens* the profile's generic "done" into concrete,
   project-specific gates rather than repeating it.
3. Look at its `.harness/verify.conf` — that's the single most valuable thing to get right early;
   it's what `scripts/verify.sh` runs to decide "is this shippable?"

> These are **reference artifacts**, not a runnable project — the commands in each `verify.conf`
> name tools/paths that would exist in that real project, not in this repo. Copy the shape, not the
> literal commands. And note what's **absent**: no secrets, API keys, real hostnames, or PII — the
> no-live-credentials rule (core) applies to examples too.
