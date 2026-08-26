# Skills — how they work, and how to add your own

A **skill** is a packaged workflow the agent loads *on demand* (dynamic context — it costs no
tokens until it's triggered). It's just a folder with a `SKILL.md`.

## Where skills live

| Location | Scope | Use for |
|---|---|---|
| `~/.agents/skills/<name>/` | shared global Agent Skills destination | portable personal skills |
| `<project>/.agents/skills/<name>/` | shared project Agent Skills destination | portable team/project skills |
| `~/.claude/skills/<name>/` | generated Claude adapter | clients that require a runtime copy |
| `<project>/.claude/skills/<name>/` | generated Claude project adapter | clients that require a runtime copy |
| bundled in a plugin | wherever the plugin is enabled | shared/distributed skills |

The agent auto-discovers them and may invoke one when its description matches the task. Invoke a
skill explicitly with the syntax supported by that client. Skill identity comes from frontmatter,
never from whether it happened to be installed below `.claude/` or `.agents/`.

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

Nine small skills ship in this repo. The starter `example-skill` is not part of that bundled count.
Procedural skills use the cross-platform `agentsmith` CLI.
**writing-rules** is pure reference;
**wayfinder** is the repository-native decision-to-spec workflow.

| Skill | Fires on | What it does |
|---|---|---|
| **handoff** | "handoff" / "wrap up" | Safe-state → durable note → paste-ready kickoff block. |
| **verify** | "is this done / shippable?" | Runs the project's verify phases; never claims "passing" without output. |
| **harness-doctor** | "is my harness healthy?" | Self-contained health checks with a one-line fix each. |
| **harness-help** | "what is this / what do I type next?" | Non-coder orientation: profile, rules, safety mode, next step. |
| **new-research** | "start a research note" | Scaffolds a durable `docs/research/` source note (R9). |
| **new-feedback** | "log a harness lesson" | Scaffolds a numbered `docs/feedback/` post-incident (System-Evolution loop). |
| **writing-rules** | writing/reviewing a rule, gate, skill description, or agent prompt | The levers that decide whether a line changes behaviour or only costs tokens. |
| **wayfinder** | a foggy effort whose destination is known but route is not | Builds a decision map and an operator-accepted spec before separate implementation tickets. |
| **autonomous-run** | start/status/resume/stop a bounded local run from an accepted spec | Drives the finite maker/checker controller without granting external writes. |

They're work-type-neutral and follow `core/` rules (verify before done, no secrets). See
`RECOMMENDED.md` for the per-profile map.

## Install the skills bundled here

```bash
./setup.sh --agent all --profile general-admin --with-skills --target .
# or copy one by hand:
cp -r skills/handoff <project>/.claude/skills/
cp -r skills/handoff <project>/.agents/skills/
```

`--with-skills` installs **every** skill folder in `skills/`. The **target depends on mode**:

- **Project mode** → canonical `<project>/.agents/skills/`; Claude additionally receives
  `<project>/.claude/skills/` as a required adapter.
- **Global mode** → canonical `~/.agents/skills/`; Claude additionally receives its global adapter.

## Best practices (R10 — keep the surface small)

- **Many Claude skills arrive via plugins** — superpowers and claude-mem each bundle many. Codex
  can use skills installed in its native tree; a Codex-only setup does not invoke Claude plugin
  marketplaces. See `RECOMMENDED.md` and `../config/plugins.md`.
- **Review before installing** a third-party skill — it can run tools and shell commands.
- **One precise `description`** beats a vague one — it's how the agent decides to load it.
- **Capture, don't repeat.** When you keep doing the same multi-step thing by hand, that's the
  signal to make it a skill (the System-Evolution loop, `core/60-evolving-the-harness.md`).
- Keep skills **work-type-neutral** where you can, so they travel between projects.
