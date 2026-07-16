# Skills — how they work, and how to add your own

A **skill** is a packaged workflow the agent loads *on demand* (dynamic context — it costs no
tokens until it's triggered). It's just a folder with a `SKILL.md`.

## Where skills live

| Location | Scope | Use for |
|---|---|---|
| `~/.claude/skills/<name>/` | every project on this machine | your personal, cross-project skills |
| `<project>/.claude/skills/<name>/` | one project (git-committable) | team/project-specific skills |
| bundled in a plugin | wherever the plugin is enabled | shared/distributed skills |

The agent auto-discovers them. Type `/` to list; the agent invokes a skill when its description
matches the task, or you call it explicitly with `/<name>`.

## Minimal structure

```
my-skill/
└── SKILL.md
```

```markdown
---
name: my-skill
description: One precise line — WHEN to use this. The agent matches on this; be specific.
---

# My Skill

Step-by-step instructions the agent should follow when this skill fires.
Reference other files in the folder with relative paths; they load only when needed
(progressive disclosure).
```

Add supporting files (scripts, references, templates) alongside `SKILL.md`; they're pulled in
only when the skill needs them.

## The bundled skill pack

Six small, **self-contained + script-aware** skills ship in this repo. Each one prefers a
project-local `scripts/<x>.sh` when present (the fast path a harness-installed project already has),
and otherwise runs a complete inline procedure — so they work installed globally, inside a harness
project, or in a bare repo, with no dependency on a harness checkout:

| Skill | Fires on | What it does |
|---|---|---|
| **handoff** | "handoff" / "wrap up" | Safe-state → durable note → paste-ready kickoff block. |
| **verify** | "is this done / shippable?" | Runs the project's verify phases; never claims "passing" without output. |
| **harness-doctor** | "is my harness healthy?" | Self-contained health checks with a one-line fix each. |
| **harness-help** | "what is this / what do I type next?" | Non-coder orientation: profile, rules, safety mode, next step. |
| **new-research** | "start a research note" | Scaffolds a durable `docs/research/` source note (R9). |
| **new-feedback** | "log a harness lesson" | Scaffolds a numbered `docs/feedback/` post-incident (System-Evolution loop). |

They're work-type-neutral and follow `core/` rules (verify before done, no secrets). See
`RECOMMENDED.md` for the per-profile map.

## Install the skills bundled here

```bash
./setup.sh --with-skills                          # bundled pack + example (see targets below)
# or copy one by hand:
cp -r skills/handoff <project>/.claude/skills/
```

`--with-skills` installs **every** skill folder in `skills/`. The **target depends on mode**:

- **Project mode** (`--profile … --target <project> --with-skills`) → `<project>/.claude/skills/`
  (committable, travels with the repo). The wizard offers this on the per-project path.
- **Global mode** (`--global --with-skills`) → `~/.claude/skills/` (every project on the machine).

## Best practices (R10 — keep the surface small)

- **Most skills arrive via plugins** — superpowers and claude-mem each bundle many. Install the
  plugin, get the skills. See `RECOMMENDED.md` and `../config/plugins.md`.
- **Review before installing** a third-party skill — it can run tools and shell commands.
- **One precise `description`** beats a vague one — it's how the agent decides to load it.
- **Capture, don't repeat.** When you keep doing the same multi-step thing by hand, that's the
  signal to make it a skill (the System-Evolution loop, `core/60-evolving-the-harness.md`).
- Keep skills **work-type-neutral** where you can, so they travel between projects.
