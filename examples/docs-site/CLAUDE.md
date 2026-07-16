<!--
  PROJECT-SPECIFICS LAYER ONLY.

  This file is NOT the whole operating agreement. setup.sh stacks three layers:
    1. the universal core   (installed globally on Theo's machine — the rigid rules)
    2. the document-creation profile  (what "done"/"verified" mean for prose & docs)
    3. THIS file             (the Lumen-Docs-specific facts, conventions, and gotchas)

  Do not re-state the core or the profile here — they're already loaded. This layer only
  carries what a fresh session would otherwise have to re-derive about THIS docs site.
  When the core, the profile, and this file all speak, the stricter rule wins; Theo's
  explicit instruction wins over all three. See README.md for the exact setup commands.
-->

# Project: Lumen Docs

Product documentation website for Lumen, built with **Astro Starlight** and shipped as a
static site. Content is Markdown/MDX; the build output is plain HTML served from a CDN. The
audience is developers integrating Lumen — so a wrong code sample or a dead link costs them
real time, and "done" leans hard on accuracy and the rendered page, not on prose polish.

## Stack & layout

- **Framework:** Astro + `@astrojs/starlight`. Static build only — no server, no database.
- **Content dir:** `src/content/docs/` — one `.md`/`.mdx` file per page. Folders map to URL
  segments (`src/content/docs/guides/auth.md` → `/guides/auth/`).
- **Sidebar:** configured in `astro.config.mjs` under `starlight({ sidebar: [...] })`. A new
  page is invisible until it's added to a sidebar group there — Starlight does not auto-list it.
- **Components:** Starlight built-ins used in MDX — `<Tabs>`/`<TabItem>`, `<Card>`/`<CardGrid>`,
  `<Steps>`, `<Aside type="note|tip|caution|danger">`. Imported from
  `@astrojs/starlight/components`. Don't hand-roll HTML for these; the components carry the
  theme's dark-mode and accessibility styling.
- **Assets:** images in `src/assets/`, referenced with a relative import in MDX or `~/assets/…`.
  Files in `public/` are served verbatim at the site root (use only for things like `favicon`).
- **Build output:** `dist/`. Local preview: `npm run build && npm run preview`.

## What "done" means here

The profile's render-verify rule is the spine; these are the Lumen-specific edges of it.

- **Claims match the shipped product — verify, don't remember.** Every flag, endpoint, env var,
  config key, default value, and CLI command in a page must match the current Lumen release.
  Open the source of truth (the API reference, the actual CLI `--help`, the changelog) and
  confirm — do not write a version number or a default from memory. A confidently wrong default
  is worse than a TODO.
- **Code samples are real.** Copy a runnable snippet into a scratch file and run it (or paste it
  into the documented context) before shipping. A sample that doesn't run is a broken promise to
  a developer who trusts it.
- **Every link resolves.** Internal cross-links use the page path (`/guides/auth/`), not a
  source filename. No empty `[]()` Markdown links. External URLs must be live, not assumed.
- **VERIFY THE RENDERED PAGE, not just the Markdown source.** This is the load-bearing one.
  `npm run build`, then open the page in `dist/` (or `npm run preview`) and *look at it*.
  Formatting, MDX-component, image, and contrast bugs exist ONLY in the rendered HTML — they are
  invisible in the source. "The Markdown reads fine" is not verified.
- **Both themes.** Starlight ships light and dark. Read the page in BOTH — contrast and
  invisible-text bugs hide in exactly one mode.
- **One concern per change (core R4).** A structural reorg, a copyedit pass, and a fact update
  are three separate commits — they're impossible to review together and a fact fix buried in a
  reflow gets missed. Same for a content edit vs. a sidebar/config change.
- **Voice & style.** Second person ("you"), present tense, imperative for steps ("Run…", not
  "You should run…"). Sentence-case headings. Match a sibling page's register before imposing a
  new one (core R1). UK/US spelling: pick what the existing docs use and stay consistent.

## verify.conf phases

`.harness/verify.conf` mirrors the document-creation preset, made concrete for Starlight. Phases
run top-to-bottom; the FIRST failure stops the run. WHY each one earns its place:

- **`spell` — `cspell` over `src/content/**`.** Typos in docs read as carelessness and erode
  trust in the accuracy of everything else on the page. Catching them is cheap and deterministic;
  project-specific terms (product names, API nouns) live in `cspell.json` so they aren't flagged.
- **`links` — `lychee` over the Markdown.** Dead and empty links are the most common docs defect
  and the profile's top failure mode. This catches them in the source before build. It does NOT
  replace the human render-check — a link can resolve yet point at the wrong page.
- **`build` — `npm run build`.** A clean Starlight build proves the MDX compiles, every component
  import resolves, and every referenced asset exists. A green build is the *gate to* the
  render-verify step, not a substitute for it — after it passes, a human still opens `dist/` and
  eyeballs the page in both themes (see "What done means").

## Conventions

- **Front-matter (every page):** `title` (required — drives the `<h1>` and sidebar label) and
  `description` (required — the meta description, ~150 chars, written for search). Optional:
  `sidebar.order` to position within its group, `sidebar.badge` (e.g. `New`), `draft: true` to
  build-but-hide a work-in-progress page. No `title` = build error.
- **Headings:** start page bodies at `##` — the `title` front-matter already supplies the `h1`.
  Never skip a level (no `##` → `####`); Starlight builds the on-page TOC from the heading tree.
- **Assets:** screenshots and diagrams in `src/assets/`, referenced relatively. Give every image
  meaningful alt text — it's accessibility *and* it surfaces when the image fails to load.
- **Terminology (keep it consistent across the whole site):** the product is **"Lumen"**; its
  command-line tool is the **"Lumen CLI"** (never "the CLI tool"); access tokens are
  **"API keys"** (never "secrets" or "tokens" in prose). Pick one term per concept and hold it.
- **Code blocks:** fence with the language for syntax highlighting (```` ```bash ````,
  ```` ```ts ````). Starlight supports `title="…"` and line-highlight (`{2-4}`) annotations on the
  fence — use them for multi-step or "change this line" samples so readers see exactly what moved.
- **New page checklist:** create the file under `src/content/docs/`, add front-matter, then add it
  to the sidebar in `astro.config.mjs` — all in the same change, or the page ships orphaned.

## Gotchas & decisions

- **Empty-link rendering (the classic).** A Markdown `[see the guide]()` with no target compiles
  fine and renders as un-clickable text — no error, no warning. The `links` phase catches the
  empty target; this is exactly why links are verified, not eyeballed-in-source.
- **Dark-mode contrast on custom callouts.** A page once used a raw inline-styled `<div>` for a
  note with a hardcoded light background; the text turned near-invisible in dark mode while
  looking perfect in light. Decision: always use Starlight's `<Aside>` component, never a
  hand-styled box — the component themes correctly in both modes. This is why the render-check
  reads BOTH themes.
- **A new page silently 404s.** Adding `src/content/docs/guides/webhooks.md` without registering
  it in the `astro.config.mjs` sidebar builds clean but leaves the page unreachable from nav and
  invisible to readers. The new-page checklist exists to make the sidebar edit non-optional.
- **MDX is JSX — `{` and `<` bite.** A literal `{` or an unclosed `<tag>` in MDX prose is parsed
  as an expression/component and breaks the build with a cryptic error. Wrap literal braces in a
  code span (`` `{ }` ``) or escape them; this is a frequent cause of a red `build` phase.
