# Project tracker guide (Linear / GitHub Issues / Jira / none)

Rule 7 says *never let a defect evaporate* — the tracker is the single source of truth and the
historical record. This guide makes that concrete without assuming a specific tool.

> **Naming your tracker does not grant write access to it.** Telling the harness *where* your team
> tracks work is a pointer, not permission. Whether the agent may create issues and post comments
> **by itself** is a separate, explicit choice — `--tracker-writes` (below). This split exists
> because the harness once inferred one from the other and filed issues in a live workspace that
> nobody had authorized it to touch. `scripts/test-tracker-consent.sh` is the guard that keeps
> that fixed.

## Principles (tool-agnostic)

- **Consent is separate from capture.** The defect always gets recorded before you move on. Consent
  governs *where it lands* — your live tracker vs. drafted for you to post — never *whether* it's
  recorded. "I wasn't allowed to post it" is never a reason a bug went missing.
- **One source of truth.** Don't scatter work across a tracker, a docs file, sticky notes, and
  memory. Pick one place; everything goes there.
- **The item is the contract.** The item's description is what "done" is measured against. If
  it's ambiguous, sharpen it before working (or research and note the decision).
- **The human stays accountable.** Even when the agent does the work, the item's owner/assignee
  is the human. Where agent writes are authorized, agent work is made *visible on the item* (a
  comment at start and at finish), not hidden in a chat log.
- **Make agent work visible** *(writes authorized only)*. Post a short note when work starts
  (what/why) and when it lands (the commit/PR/deliverable + "done"). The human reviews from one
  place. Where writes are **not** authorized, hand the same note to the human instead.
- **Branch from the item** when the tool supports it, so the branch ↔ item ↔ PR links itself and
  status transitions automatically.

## Mapping to common tools

| Concept | Linear | GitHub | Jira | No tracker |
|---|---|---|---|---|
| Work item | Issue (`ABC-123`) | Issue # | Issue (`PROJ-123`) | a line in `KNOWN-ISSUES.md` |
| Grouping | Project / Cycle | Milestone / Project | Epic / Sprint | a heading |
| Status flow | Backlog→In Progress→In Review→Done | Open→(PR)→Closed | To Do→In Progress→Done | checkbox |
| Branch link | "Copy git branch name" | `gh issue develop` | Smart Commits | branch name = slug |
| Agent visibility | comment on issue | comment on issue/PR | comment on issue | note in the file |

## If there's no tracker

Keep a `KNOWN-ISSUES.md` (or a `TODO.md`) at the repo root: one line per item, `[ ]`/`[x]`,
with a date and a one-line description. It's primitive, but it satisfies Rule 7 — the work is
recorded somewhere durable and greppable, not just in a vanished session.

## Set the placeholder

`setup.sh` writes your choice into `CLAUDE.md` as `{{TRACKER}}`. If you skip it, the assembled
file says "track work in your project's tracker (or KNOWN-ISSUES.md)".

## Grant (or withhold) write access

Separate flag, deliberate choice:

```bash
./setup.sh --tracker linear                            # ask-first (default)
./setup.sh --tracker linear --tracker-writes allowed   # the agent may file/comment itself
```

| | `ask` (default) | `allowed` |
|---|---|---|
| Finds a defect | drafts the item, hands it to you | files it in the tracker itself |
| Work start/finish | tells you in the session | comments on the item |
| Good for | shared/client workspaces; trying the harness out; anything with an audience | your own workspace, where you want the paper trail written for you |

The wizard asks this right after it asks *where* you track work. Both installers default to `ask`
— including on upgrade: a `CLAUDE.md` written before this split had its writes *inferred*, never
granted, so re-running setup **fails closed** to `ask` and tells you how to opt back in.

**A tracker file inside the repo** (`KNOWN-ISSUES.md`) isn't an outside system — it's a file, and
normal repo rules apply. `allowed` is the sensible answer there.
