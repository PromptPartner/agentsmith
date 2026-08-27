# First steps — {{TARGET_NAME}}

Agentsmith (your AI "house rules") is installed here for **{{PLATFORM}}**. This card is your first 30 minutes.
Everything below happens **inside this folder** in your terminal.

## Start

Start the runtime(s) you selected inside this folder:

- Claude: `claude`
- Codex: `codex`

Each opens with its rules loaded. Type in plain English with no special syntax. The assistant uses
plain international English and explains new technical terms. Ask directly if you want another
language. Your `--operator-bio` tells it where you want more or less detail.

## Three things to try first

> **Step 0 — building a UI?** Establish your design system *before* the first screen. If setup
> scaffolded a `DESIGN.md` in this folder, fill it in (bring your brand, pick one from the
> awesome-design-md catalog, or generate one with ui-ux-pro-max); if not, re-run
> `./setup.sh --profile software-dev --design-system stub --target .` to get the template. The
> assistant reads `DESIGN.md` before writing any UI and holds every screen to it. **No UI? Skip this.**

1. **Get your bearings.** Ask:
   *"what does my harness do, and what are my rules?"*
   The assistant reads `CLAUDE.md` (Claude) or `AGENTS.md` (Codex) and explains the setup in plain
   language.
2. **Do one small thing end-to-end.** Give it a single, concrete task ("fix this typo",
   "add a function that …"). It will plan → do → verify before calling it done.
3. **Wrap up cleanly.** When you're stopping, say **"handoff"**. The assistant saves its
   place and writes a recall note so the next session picks up where you left off.

## Good to know

- **Handoff.** Say **"handoff"** at any natural stopping point. Claude's optional status line can
  also show `ctx:NN%`; its best-effort percentage nudge is Claude-only. Codex gets the reliable
  keyword hook, not that nudge and not a `PreCompact` hook. If Codex hooks were installed, review
  and trust them once with `/hooks`.
- **Safety mode: {{SAFETY}}.** In *cautious* mode the assistant auto-applies file edits but
  keeps work inside the workspace and asks for higher-risk actions. In *trusted* mode it runs
  almost everything without asking. Re-run setup with `--safety cautious|trusted` to change it;
  see README → "Permissions and trusted mode" for the native JSON/TOML settings.
- **Profile(s): {{PROFILES}}.** These tailor the rules to your kind of work. Re-run setup to
  change them.
- **Undo the managed install:** `./setup.sh --platform {{PLATFORM}} --uninstall --target .`
  (it backs up before removing and reports retained scaffolding/config).

## Go deeper (optional)

- `CLAUDE.md` / `AGENTS.md` — the actual rules in force for the selected runtime(s).
- `docs/01-harness-philosophy.md` — why the harness works this way (a 5-minute read).
