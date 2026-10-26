<!-- CORE · version control + session handoff · universal -->
## Version Control & Finalizing Work

These apply whenever the work lives in git (code, docs, config, data pipelines). For non-git
work, treat "commit" as "save a clean, named version" and the spirit carries over.

- **The main branch is protected.** Do work on a feature branch and integrate via PR / review,
  not direct commits to main — unless the operator says otherwise for this project.
- **Commit messages explain WHY,** in the form `type(scope): why`. The diff already shows what
  changed; the message captures the reason a future reader needs.
- **Commit under the identity that owns the repo you're in** — read it off the remote
  (`git remote -v`), never off habit or the last project's config. Whoever's name lands on a
  commit is permanent and public once pushed, and across several orgs/clients the wrong one is a
  disclosure. If the local `user.name`/`user.email` aren't that owner's, stop and ask.
- **Commit or push only when asked,** unless this project's profile says otherwise. Don't
  accumulate a giant pile of uncommitted work — bring things to a safe, saved state regularly.
- **Look before you overwrite or delete.** If what you find contradicts how a file was
  described, or you didn't create it, surface that instead of blowing it away (see Rule 9). To
  move a branch back, use `git reset --keep`, which refuses to overwrite uncommitted changes;
  `--hard` silently destroys them.
- **Outward-facing or hard-to-reverse actions get a confirmation** unless you're durably
  authorized: publishing, sending to real recipients, deleting shared data, force-pushing a
  shared branch, touching production. Approval in one context doesn't extend to the next.

## Finalizing a unit of work

When a unit is done: state the outcome **faithfully**. If checks failed, say so with the output.
If a step was skipped or deferred, say "deferred: reason" — never silence. When something is
done and verified, say so plainly without hedging. Then make the work visible where the team
looks (the tracker comment, the PR description, the summary).

## Session handoff

A fresh session has **zero** memory of this one; the handoff is the only bridge. When you wind
down — the operator says "wrap up," context is filling, or a phase closed — run the handoff
**without being asked**: safe state first (commit or stash), then the durable note, then a
paste-ready kickoff block. The protocol lives in the **`handoff` skill**: run `/handoff`, or
`agentsmith handoff [name]` to scaffold the note with the Git facts filled in.
