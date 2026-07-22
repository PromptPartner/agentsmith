# First steps — {{TARGET_NAME}}

Agentsmith (your AI "house rules") is installed here. This card is your first 30 minutes.
Everything below happens **inside this folder** in your terminal.

## Start

```
claude
```

That opens Claude Code with these rules loaded. Type in plain English — no special syntax.

## Three things to try first

> **Step 0 — building a UI?** Establish your design system *before* the first screen. If setup
> scaffolded a `DESIGN.md` in this folder, fill it in (bring your brand, pick one from the
> awesome-design-md catalog, or generate one with ui-ux-pro-max); if not, re-run
> `./setup.sh --profile software-dev --design-system stub --target .` to get the template. The
> assistant reads `DESIGN.md` before writing any UI and holds every screen to it. **No UI? Skip this.**

1. **Get your bearings.** Ask:
   *"what does my harness do, and what are my rules?"*
   The assistant reads `CLAUDE.md` and explains the setup in plain language.
2. **Do one small thing end-to-end.** Give it a single, concrete task ("fix this typo",
   "add a function that …"). It will plan → do → verify before calling it done.
3. **Wrap up cleanly.** When you're stopping, say **"handoff"**. The assistant saves its
   place and writes a recall note so the next session picks up where you left off.

## Good to know

- **Context gauge.** The status line shows `ctx:NN%` — how full the assistant's working
  memory is. Around 25–30%, or any time, just say **"handoff"**.
- **Safety mode: {{SAFETY}}.** In *cautious* mode the assistant auto-applies file edits but
  asks before running shell commands or touching the network. In *trusted* mode it runs
  almost everything without asking. Change it any time by editing
  `.claude/settings.local.json` (see README → "Permissions & dangerous mode").
- **Profile(s): {{PROFILES}}.** These tailor the rules to your kind of work. Re-run setup to
  change them.
- **Undo everything:** `./setup.sh --uninstall --target .` (it backs up before removing).

## Go deeper (optional)

- `CLAUDE.md` — the actual rules in force here.
- `docs/01-harness-philosophy.md` — why the harness works this way (a 5-minute read).
