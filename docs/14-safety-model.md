# The safety model

The reasonable first question about any tool that runs commands on your machine is *"what can it
actually do, and how do I bound it?"* This page answers that in one place. It doesn't restate the
rules — it maps the harness's security posture to where each control lives, so you can see the
whole surface before you trust it with anything real.

The one-line version: **the harness defaults to the cautious end, makes the dangerous capabilities
opt-in and reversible, and enforces the non-negotiable parts with deterministic guards rather than
prose the model might skip.**

## The biggest lever: safety mode

How much the agent does without asking is a single setting, and it's the control you'll actually
use. **Cautious** (the wizard default) auto-applies file edits but prompts before shell commands
and network calls. **Trusted** (`bypassPermissions`) runs most tool calls without asking. The full
table, the exact JSON keys, and how to change it later are in the README's **"Permissions &
dangerous mode"** section — read it before you flip anything.

The honest risk statement: trusted mode means a wrong or manipulated step can delete files,
exfiltrate data (a stray `curl`), or push to a remote **without a prompt**. It's acceptable only
on a machine you fully own — never a shared, client, or production box. New to this? Stay cautious
until the setup has earned your trust. (The `rm -rf /` and `rm -rf ~` circuit-breakers still
prompt even in trusted mode.)

## Secrets never touch a tracked file

Rule 8 is absolute: no live credential in anything committed — not code, docs, config, commit
messages, or comments. Scripts read secrets from the environment with no real-value default, so
they fail loudly rather than bake in a fallback. This one isn't left to the model's judgment: the
`scripts/secret-scan.sh` pre-commit hook (`setup.sh --with-hooks`) blocks a commit that carries
one, mechanically. "Private repo" is not a safety argument — it's a smaller blast radius.

## Availability is not authorization

A connected tool is not a writable tool. The harness treats *naming* a system (a tracker, a CRM, a
mailbox, a chat) and *being allowed to write to it* as two separate consents — the second explicit,
opt-in, and asked once at setup, never inferred from the first. The pause-list in `core/10` makes
the **first write to any system outside the repo** a stop-and-ask, so this holds for every
connected MCP server, not just the one the harness happens to know about. Reading is always free;
writing is always asked. (The tracker case, and why the default is *propose, don't post*, is in
[`13-project-tracker-guide.md`](13-project-tracker-guide.md).)

## Unattended work has a hard denylist

When work runs without a human in the path (a loop), the blast radius is bounded by category:
secrets, auth, payments, billing, infra/prod, and migrations are **never auto-edited** — they're
escalated to a human, always. Loops default to no auto-merge, connectors stay read-only until
trust is earned, and every action goes through a checker the maker can't fool. The full set of
loop guardrails is in `profiles/autonomous-loops.md`; how you operate within them is
[`06-your-first-loop.md`](06-your-first-loop.md).

## Untrusted input is treated as hostile

The web page the agent fetched, the issue body it read, the file a stranger sent — any of it can
contain instructions aimed at the agent (prompt injection). The posture is Simon Willison's: stay
accountable for what the software does, and don't let content the agent *reads* become commands it
*follows*. This is why the outward-facing and hard-to-reverse actions get a confirmation, and why
the pause-list and the loop denylist exist — they bound what a manipulated step can reach.

## Locking it down on a shared or managed machine

On a box you don't fully control, you want the safety floor enforced from above, where no project
can re-enable the dangerous mode. `sudo setup.sh --org-policy` installs a managed `CLAUDE.md` at
the OS policy path plus a stricter, no-bypass settings profile; the managed-settings keys that
disable bypass mode (`disableBypassPermissionsMode`) and their exact per-OS paths are documented in
[`research/claude-code-hooks-and-managed-policy.md`](research/claude-code-hooks-and-managed-policy.md).
Managed settings are highest-precedence and can't be overridden by a user or project.

## Everything is reversible

Setup backs up any file it touches before writing, and only ever rewrites its own managed block
(the region between the `AGENTSMITH` markers) — your edits outside it survive every re-run. To
undo an install entirely: `./setup.sh --uninstall --target .`. Nothing here is a one-way door.

## One thing you own, not the harness

Skills and plugins run tool calls and shell commands. Review a third-party one before installing it
— its `description` tells the agent when to load it, and its body can do whatever a script can. The
harness keeps its own surface small (Rule 10) precisely so there's less of this to audit; hold the
same line on anything you add.
