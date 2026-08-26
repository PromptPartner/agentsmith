---
name: handoff
description: Wrap up a work session for a clean restart — fires on "handoff", "wrap up", "let's stop here", when context is filling, or when a phase closed. Part of the Agentsmith harness; writes a durable handoff note plus a paste-ready kickoff block so a fresh session loses nothing.
compatibility: Requires filesystem access and git; the fast path requires the cross-platform Agentsmith CLI.
---

# Handoff — memory first, then the kickoff

A fresh session has **zero** memory of this one; the handoff note is the only bridge. Run this
whenever work winds down — even if no one asked (core/50).

## When this fires
"handoff" / "wrap up" / "let's stop here" / "I'm running low on context" / a phase or task just closed.

## Runtime neutrality
This workflow is identical in every client. Never infer the active agent from this skill's install
path: `.agents/skills` is the shared Agent Skills location. Use “fresh chat” rather than a
runtime-specific reset command so the note remains portable.

## Fast path — if the Agentsmith CLI is available
1. Run `agentsmith handoff [item-id]` — use `.agentsmith/agentsmith` on macOS/Linux or
   `.agentsmith\\agentsmith.cmd` on Windows when the command is not on PATH. It pre-fills
   branch/HEAD/dirty count and scaffolds
   `.harness/handoffs/handoff-<stamp>.md` with the standard sections.
2. Fill the scaffolded sections (below), then emit the kickoff block as your final message.

## Fallback — no CLI
1. **Safe state FIRST** (core/50 step 1): commit or stash so nothing half-edited is lost. Never
   hand off a dirty tree silently.
2. Write `.harness/handoffs/handoff-<stamp>.md` with these sections:
   - **What shipped this session** — with commit SHAs / PR links.
   - **What is still pending.**
   - **Deviations / decisions made** (so they're not re-litigated).
   - **Exact next step** — the single first action for the next session.
   - **Gotchas** a fresh session would otherwise re-derive.
3. Emit a fenced **"Kickoff prompt for a fresh chat"** block: 3–6 sentences of self-contained
   prose (not bullets — they paste it straight in) covering the item id, branch + HEAD, what's
   done, the single next step, decisions already made, and the handoff note path.

## Report
Name the handoff file, then end your message with the fenced kickoff block. If you notice mid-wrap
that you haven't written the note yet, stop and write it before continuing.
