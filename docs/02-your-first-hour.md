# Your first hour

Setup printed the files and settings it manages. This guide explains what changed, why each part
exists, and how to complete your first task and handoff. You do not need to learn AgentSmith's
special terms before you start.

## Minutes 0–10: what setup actually wrote

A project install (`./setup.sh --agent <id|group> --profile software-dev --target .`,
or the guided setup) creates these files in the project. Unless you pass `--assemble-only`, it also
updates the selected coding agent's user settings in `~/.claude` or `CODEX_HOME`:

```
AGENTS.md                        main generated instruction file (tour below)
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
.agentsmith/state.json           local installation choices and ownership fingerprints
```

The Python program and templates are copied into the project, so installed commands do not depend
on the AgentSmith folder you cloned. Each rule file is written inside marker comments
(`<!-- BEGIN AGENTSMITH … -->`): that block belongs to setup. To change the rules, edit `core/`
or `profiles/` in your harness checkout and re-run setup; anything you add *outside* the markers
(project specifics) is yours and survives every re-run.

Confirm which installation layers and profile actually apply before changing anything:

```bash
agentsmith status --target .
```

This is a read-only summary, not a second diagnostic dump. It shows the global-to-project
instruction chain, active profile, verification gaps, and one safest useful next command. Use
`agentsmith doctor` when the summary reports drift or you need capability-level detail.

When a stable release is available, use `agentsmith update plan --target . --save FILE` before
installing it. Planning does not change the installation. The first plan creates a local key under
`~/.agentsmith` to authenticate plans and receipts. Read the saved plan, then run `agentsmith update
apply --plan FILE` only when you approve those managed changes. Apply prints a rollback receipt
outside the project; keep that path until the update is accepted. Weekly availability checks are
off unless you explicitly enable them with `agentsmith update configure --auto-check weekly`, and
they never install anything automatically.

## Minutes 10–25: read your instruction file — the tour

**`AGENTS.md` is a set of written instructions, not an application settings file.** The agent reads
it and follows the agreement during the session. Changing it changes how the agent works. Every
line must earn its place because the full file uses part of the agent's limited working memory
(see [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)).

The software-development version is about 540 lines. In order:

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

If the active profile does not fit the work, ask for a deterministic recommendation and preview the
managed diff before switching:

```bash
agentsmith profiles recommend --target .
agentsmith profiles switch --target . --profile software-dev --dry-run
agentsmith profiles switch --target . --profile software-dev
```

The real switch backs up changed instruction files and updates the existing installation manifest.
It does not rewrite your verification configuration; instead it reports which profile gates remain
unrepresented so you can review them explicitly.

`.harness/verify.conf` starts with a deliberately failing `unwired` phase. Discover the checks the
repository supports without running its code, inspect the exact proposed diff, and then apply the
reviewed plan:

```bash
agentsmith verify discover --target . --save .harness/verification-plan.json
agentsmith verify apply --target . --plan .harness/verification-plan.json --dry-run
agentsmith verify apply --target . --plan .harness/verification-plan.json
```

Discovery reports what it still cannot prove and refuses to compose ambiguous stacks silently. If
no allow-listed detector fits, edit the config yourself with one real `label :: command` line —
your build, test suite, or other definition of "shippable":

```
test :: npm test        # or: pytest -q · go test ./... · cargo test
```

This five-minute setup is disproportionately important: `agentsmith verify` runs every phase in order
and is the agent's gate for calling anything done. Until it runs *your* checks, "verified" means
nothing (the full story: [`03-verify-means-evidence.md`](03-verify-means-evidence.md)).

## Minutes 30–50: the first task

If you want to learn the loop before touching the current project, create the bundled disposable
scenario in a new or empty directory:

```bash
agentsmith demo first-loop --target ../agentsmith-first-loop-demo
```

The initializer performs no network access, installs no dependency, and refuses a non-empty or
symbolic-link target before writing. Its launch-readiness checker deliberately uses `any` where the
accepted task requires `all`. Follow the three printed steps to observe the named red test, make
the one-line bounded fix, and prove both the tests and the visible command path.

If you want a reference run before editing, inspect the
[First Verified Loop public proof](demos/first-verified-loop/README.md). Its runbook was executed
from a temporary clean Git copy and retains the red output, green receipt, real command result,
handoff, read-only resume, lifecycle fixtures, and claim boundaries.

Start your selected coding agent in the project and ask: *"what does my harness do, and what are my rules?"* — the
agent explains its own contract back to you, which is both a sanity check and the fastest tour.

The agent uses plain international English by default. It explains technical terms in common words
and tells you what a command will change before showing it. If you want another language, ask for
it directly, for example: *"Answer in German."* Use `--operator-bio` during setup to tell the agent
which topics you know well and which topics need more explanation. Copy-ready examples are in
[INSTALL.md](../INSTALL.md#3-set-responsibility-background-and-external-write-consent).

Then give it one small, real task — a typo-level fix, a tiny function, something you'd trust a
new hire with on day one. Watch the shape of what happens: it reads before it edits, it states
what it's about to do, it does the work, it runs the checks, and it reports the outcome *with the
evidence* — not "done!" but "here's the test that failed before and passes now."

What it won't do is ask permission between steps. It pauses only for the three things it can't
decide (credentials, external-service surprises, the first write to a system outside the repo).
If that autonomy is more than you want, the **cautious** safety mode — the guided setup
default — keeps higher-risk actions behind a prompt and Codex writes inside its workspace sandbox
while you build trust; see
README → "Permissions and trusted mode."

## Minutes 50–60: the first handoff

Here's the counterintuitive one: sessions should end at a good seam, not only when the context
window is almost full. A context window is like a workbench: more space does not guarantee that
every tool and note on it remains equally easy to find. Reliable capacity varies by model and task,
so the `ctx:NN%` gauge shows load rather than a universal quality score. Hand off at a completed
phase, before a risky new step, or when the agent starts repeating itself or missing details.

Say **"handoff"**. The agent brings the work to a safe state, writes a memory note (branch, what
shipped, what's pending, the gotchas), and prints a paste-ready kickoff block. That block is the
*only* bridge to the next session — a fresh session remembers nothing. Next time, paste the
kickoff and it resumes exactly where this one stopped.

After the note is filled, verify the continuation point before opening a fresh session:

```bash
agentsmith resume --target .
```

This read-only command selects the newest handoff, reports incomplete sections or placeholders,
compares recorded and current Git facts, and prints a validated recovery command plus a synthesized
kickoff prompt. The command is limited to `agentsmith status`; handoff-supplied kickoff prose is
validated for presence but never echoed as paste-ready text. A drift warning informs you; resume
disables optional Git locks and never changes branches, commits, files, or stashes.

The optional keyword hook understands both runtimes' payloads. After a Codex hook install, run
`/hooks` once and review/trust it. Claude's experimental percentage nudge depends on its status line
and stays disabled until you set a threshold calibrated on your own work. A normal install
activates AgentSmith's Claude gauge only when no explicit status-line choice exists; Codex already
activates its built-in gauge when unset. Codex gets no percentage nudge and this release adds no
`PreCompact` hook. The written handoff protocol is the dependable mechanism on both platforms.

That's the loop you'll live in: one unit of work, verified with evidence, handed off clean.

## Where next

[`03-verify-means-evidence.md`](03-verify-means-evidence.md) for the concept that carries everything ·
[`05-operating-modes.md`](05-operating-modes.md) when you wonder whether work could run unattended ·
[`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md) before you write your
first rule.
