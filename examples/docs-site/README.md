# Example: Lumen Docs — Astro Starlight docs site (document-creation profile)

**Scenario.** Lumen Docs is a product documentation website built with Astro Starlight —
Markdown/MDX content under `src/content/docs/`, a configured sidebar, and a static site that
builds to `dist/`. The operator is Theo Bauer, a developer advocate who tracks work in Linear.
This folder shows what the harness looks like *layered onto that one docs site*: the universal
core is installed globally on Theo's machine, and the project itself carries only the
document-creation profile plus the project-specifics below.

**Set it up like this:**

```bash
# 1) Install the universal core once, globally (Theo's machine, all projects):
./setup.sh --global --operator-name "Theo Bauer" --operator-role "developer advocate"

# 2) Layer the document-creation profile onto THIS repo (no core copied in — core is global):
./setup.sh --profile document-creation --profile-only --target . \
  --operator-name "Theo Bauer" --operator-role "developer advocate" \
  --tracker linear --with-hooks
```

**What to notice.**

- **`.harness/verify.conf` is the single source of truth for "shippable."** The profile says
  "spell-check → links resolve → rendered page looks right"; the conf makes that concrete for
  Starlight (`cspell` over the MDX content, `lychee` over the source links, `npm run build`).
  `verify.sh` and any human both read this one file, so the commands never drift.
- **`CLAUDE.md` here is *only* the project-specifics layer.** It doesn't repeat the core or the
  profile — `setup.sh` stacks all three. It sharpens what "done" means for *docs specifically*:
  claims match the shipped product, every link resolves, and the **rendered** page is eyeballed,
  not just the Markdown source.
- **Docs bugs live in the rendered output, not the source.** Empty `[]()` links, dark-mode
  contrast, an overflowing table — all read fine in Markdown and only appear once Starlight
  renders the page. The build phase produces `dist/`; the human still opens it and looks.
- **`--with-hooks` installs git guardrails** (secret-scan, protect-main, conventional-commit) so
  the no-secrets and atomic-commit rules are enforced deterministically, not just remembered.

**Files here:**

- `README.md` — this file.
- `CLAUDE.md` — the project-specifics layer (Lumen Docs' stack, "done," conventions, gotchas).
- `.harness/verify.conf` — the concrete verify phases for this Starlight docs site.
