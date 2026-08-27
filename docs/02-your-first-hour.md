# Your first hour

Setup ran and printed its managed destinations. This is the hour version: what actually changed on
disk, why it's shaped that way, and how your first task and first handoff should go. The gap
between "it installed" and "I know what it did" is where most people quit; this closes it.

## Minutes 0–10: what setup actually wrote

A project install (`./setup.sh --agent <id|group> --profile software-dev --target .`,
or the wizard) leaves these project-local surfaces. Unless you pass `--assemble-only`, it also
updates the selected runtime's user config in `~/.claude` and/or resolved `CODEX_HOME`:

```
AGENTS.md                        canonical assembled rulebook (tour below)
CLAUDE.md                        generated copy when Claude is selected
.harness/verify.conf             your project's definition of "shippable" (starts as a stub)
.harness/templates/              plan, handoff, research, progress-log, quality-gate templates
.claude/settings.local.json.example   Claude project safety example (when Claude is selected)
.codex/config.toml                 Codex project MCP (only with --with-mcp)
.agents/skills                  canonical pack (only with --with-skills)
.claude/skills                  required Claude adapter (when selected)
.planning/progress-log.md        a running log the agent appends to
docs/feedback/README.md          the post-incident convention (see below)
.agentsmith/                     Python runtime + POSIX/Windows command shims
```

The runtime and templates are *copied in*, so your project is self-contained — nothing at runtime
depends on the harness checkout you cloned. Each rule file is written inside marker comments
(`<!-- BEGIN AGENTSMITH … -->`): that block belongs to setup. To change the rules, edit `core/`
or `profiles/` in your harness checkout and re-run setup; anything you add *outside* the markers
(project specifics) is yours and survives every re-run.

## Minutes 10–25: read your native rule file — the tour

Here's the reframe that makes everything else make sense: **`AGENTS.md` is not a
runtime config file.** The agent *reads* it — the whole thing, effectively re-read on every turn of
every session — and behaves according to what it understood. It's a contract written for a very
fast, very literal colleague. Editing it is programming the agent, in prose. That's also why
every line is rationed (see [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)).

Yours is ~490 lines for one profile. In order:

| Section | What it does | What to look for on first read |
|---|---|---|
| **Identity** | Who the agent believes you are, and how the layers of the agreement relate. | Your name/role. Any `[TODO: …]` setup told you about is a blank only you can fill. |
| **Operating model** | How much the agent decides alone — and the *short* list of things it must stop and ask about (a missing credential, an external surprise, the first write to an outside system). | The autonomy might surprise you: no approval sought between plan → do → verify. That's deliberate. |
| **The ten principle rules** | The rigid core: understand before changing, evidence before assertion, atomic changes, no secrets ever, research never deleted… | Each exists because skipping it caused a real, repeated failure. None is decorative. |
| **The STOP table** | A list of *thoughts* — "I'll verify later," "too small to check" — paired with why each precedes a failure. | Models rationalize exactly the way tired engineers do. This table is the countermeasure, and it works better than you'd expect. |
| **Subagents & tools** | When work is delegated to parallel agents vs kept on the main thread. | Mostly the agent's business; skim it. |
| **Git & handoff** | Branch discipline, commit style, and the end-of-session protocol. | "Commit or push only when asked" — the agent won't ship behind your back. |
| **Evolving the harness** | The habit that compounds: when something goes wrong, fix the *system*, not just the symptom. | This is the section that makes the harness worth more every week you use it. |
| **Your profile(s)** | What "done" and "verified" mean for *your kind of work*, its quality gates and failure modes. | The part that changes between projects. Everything above it never does. |

## Minutes 25–30: wire one real check into `verify.conf`

`.harness/verify.conf` starts with a placeholder phase that just echoes. Replace it with one real
line in the `label :: command` format — your build, your test suite, whatever "shippable" means
here:

```
test :: npm test        # or: pytest -q · go test ./... · cargo test
```

This five-minute edit is disproportionately important: `agentsmith verify` runs every phase in order and
is the agent's gate for calling anything done. Until it runs *your* checks, "verified" means
nothing (the full story: [`03-verify-means-evidence.md`](03-verify-means-evidence.md)).

## Minutes 30–50: the first task

Start your selected coding agent in the project and ask: *"what does my harness do, and what are my rules?"* — the
agent explains its own contract back to you, which is both a sanity check and the fastest tour.

Then give it one small, real task — a typo-level fix, a tiny function, something you'd trust a
new hire with on day one. Watch the shape of what happens: it reads before it edits, it states
what it's about to do, it does the work, it runs the checks, and it reports the outcome *with the
evidence* — not "done!" but "here's the test that failed before and passes now."

What it won't do is ask permission between steps. It pauses only for the three things it can't
decide (credentials, external-service surprises, the first write to a system outside the repo).
If that autonomy is more than you signed up for, the **cautious** safety mode — the wizard
default — keeps higher-risk actions behind a prompt and Codex writes inside its workspace sandbox
while you build trust; see
README → "Permissions & dangerous mode."

## Minutes 50–60: the first handoff

Here's the counterintuitive one: sessions should end *early*. An agent's working memory (the
context window) degrades as it fills — quality drops well before the window is technically full,
so the discipline is to hand off around **25–30% used**, while the model is still in its best
range. Don't run it to the red.

Say **"handoff"**. The agent brings the work to a safe state, writes a memory note (branch, what
shipped, what's pending, the gotchas), and prints a paste-ready kickoff block. That block is the
*only* bridge to the next session — a fresh session remembers nothing. Next time, paste the
kickoff and it resumes exactly where this one stopped.

The optional keyword hook understands both runtimes' payloads. After a Codex hook install, run
`/hooks` once and review/trust it. The automatic context-percentage nudge is Claude-only because it
depends on Claude's status line. A normal install activates AgentSmith's Claude gauge only when no
explicit status-line choice exists; Codex already activates its built-in gauge when unset. Codex
gets no percentage nudge and this release adds no `PreCompact` hook. The written handoff protocol
is the dependable mechanism on both platforms.

That's the loop you'll live in: one unit of work, verified with evidence, handed off clean.

## Where next

[`03-verify-means-evidence.md`](03-verify-means-evidence.md) for the concept that carries everything ·
[`05-operating-modes.md`](05-operating-modes.md) when you wonder whether work could run unattended ·
[`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md) before you write your
first rule.
