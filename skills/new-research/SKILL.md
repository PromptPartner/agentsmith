---
name: new-research
description: Start a durable research / source note that captures what you read and found — fires on "start a research note", "capture these sources", "log my research". Part of the Agentsmith harness; scaffolds docs/research/<slug>.md so findings live in the repo, never in disposable memory (R9), and are never silently deleted.
---

# New research note

Research belongs in the repo, traceable to sources, and is never silently deleted (R9). This
scaffolds one note per topic.

## When this fires
"start a research note" / "capture these sources" / beginning any multi-source investigation
whose findings should outlive the session.

## Fast path — if `./scripts/new-research.sh` exists
Run `./scripts/new-research.sh "topic name"` — it slugifies the title and writes
`docs/research/<slug>.md` from the template (it won't overwrite an existing file).

## Fallback — no script
1. slug = the topic lowercased, every run of non-alphanumeric characters → `-`, ends trimmed.
2. If `docs/research/<slug>.md` already exists, STOP — append to it, never overwrite.
3. Otherwise create it with a no-delete banner (obsolete → move to `docs/research/_archive/`, R9)
   and these sections:
   - **Question / scope**
   - **Sources consulted** — url or citation; what you actually opened, dated.
   - **Findings** — each traceable to a source above; mark single-sourced / uncertain items.
   - **Open questions / what was NOT checked.**

## Report
Name the file created and remind the operator to commit it (R9 — research lives in git, not
memory). Every finding you add later must cite a source already in the note.
