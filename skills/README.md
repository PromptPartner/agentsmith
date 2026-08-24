# Skills — how they work, and how to add your own

A **skill** is a packaged workflow the agent loads *on demand* (dynamic context — it costs no
tokens until it's triggered). It's just a folder with a `SKILL.md`.

## Where skills live

| Location | Scope | Use for |
|---|---|---|
| `~/.claude/skills/<name>/` | every Claude project on this machine | personal Claude skills |
| `<project>/.claude/skills/<name>/` | one Claude project (git-committable) | team/project Claude skills |
| `~/.agents/skills/<name>/` | every Codex project on this machine | personal Codex skills |
| `<project>/.agents/skills/<name>/` | one Codex project (git-committable) | team/project Codex skills |
| bundled in a plugin | wherever the plugin is enabled | shared/distributed skills |

The agent auto-discovers them and may invoke one when its description matches the task. Invoke a
skill explicitly as `/<name>` in Claude Code or `$<name>` in Codex. With `--platform both`, setup
installs independent copies in both native trees rather than symlinks.

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

Seven small skills ship in this repo. Six are **self-contained + script-aware**: each prefers a
project-local `scripts/<x>.sh` when present (the fast path a harness-installed project already has),
and otherwise runs a complete inline procedure — so they work installed globally, inside a harness
project, or in a bare repo, with no dependency on a harness checkout. The seventh,
**writing-rules**, is pure reference: no script, nothing to run, consulted while you write.

| Skill | Fires on | What it does |
|---|---|---|
| **handoff** | "handoff" / "wrap up" | Safe-state → durable note → paste-ready kickoff block. |
| **verify** | "is this done / shippable?" | Runs the project's verify phases; never claims "passing" without output. |
| **harness-doctor** | "is my harness healthy?" | Self-contained health checks with a one-line fix each. |
| **harness-help** | "what is this / what do I type next?" | Non-coder orientation: profile, rules, safety mode, next step. |
| **new-research** | "start a research note" | Scaffolds a durable `docs/research/` source note (R9). |
| **new-feedback** | "log a harness lesson" | Scaffolds a numbered `docs/feedback/` post-incident (System-Evolution loop). |
| **writing-rules** | writing/reviewing a rule, gate, skill description, or agent prompt | The levers that decide whether a line changes behaviour or only costs tokens. |

They're work-type-neutral and follow `core/` rules (verify before done, no secrets). See
`RECOMMENDED.md` for the per-profile map.

## Install the skills bundled here

```bash
./setup.sh --with-skills                          # bundled pack + example (see targets below)
# or copy one by hand:
cp -r skills/handoff <project>/.claude/skills/
cp -r skills/handoff <project>/.agents/skills/
```

`--with-skills` installs **every** skill folder in `skills/`. The **target depends on mode**:

- **Project mode** → `<project>/.claude/skills/` for Claude, `<project>/.agents/skills/` for Codex,
  or both native directories with `--platform both` (committable, travels with the repo).
- **Global mode** → `~/.claude/skills/` for Claude, `~/.agents/skills/` for Codex, or both.

## Best practices (R10 — keep the surface small)

- **Many Claude skills arrive via plugins** — superpowers and claude-mem each bundle many. Codex
  can use skills installed in its native tree; a Codex-only setup does not invoke Claude plugin
  marketplaces. See `RECOMMENDED.md` and `../config/plugins.md`.
- **Review before installing** a third-party skill — it can run tools and shell commands.
- **One precise `description`** beats a vague one — it's how the agent decides to load it.
- **Capture, don't repeat.** When you keep doing the same multi-step thing by hand, that's the
  signal to make it a skill (the System-Evolution loop, `core/60-evolving-the-harness.md`).
- Keep skills **work-type-neutral** where you can, so they travel between projects.
