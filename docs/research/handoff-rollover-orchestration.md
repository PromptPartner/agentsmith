# Research: automatic handoff rollover orchestration

> Decision note, verified 2026-08-25 against the shipped hooks and the locally installed
> `codex-cli 0.149.0`. Keep this source material under `docs/research/` (R9); obsolete material
> moves to `_archive/`, never deletion.

## Question / scope

Should Agentsmith go beyond an early handoff cue and run a controller that verifies the current
session's handoff, then starts its successor automatically around 25–30% context used? This note
covers the minimum safe protocol and the build/no-build gate. It does not propose an implementation
against undocumented runtime internals.

## Sources consulted

| # | Source | Date | Type |
|---|---|---|---|
| 1 | [Claude Code hooks reference](https://code.claude.com/docs/en/hooks) and [guide](https://code.claude.com/docs/en/hooks-guide) | 2026-08-25 | primary/vendor |
| 2 | `hooks/context-budget-nudge.sh`, `hooks/handoff-on-keyword.sh`, `config/statusline-command.sh`, and `scripts/handoff.sh` in this repository | 2026-08-25 | primary/local |
| 3 | Local `codex-cli 0.149.0` help for `queue`, `fork`, and experimental `app-server` | 2026-08-25 | primary/runtime |

## Current trigger availability

- **Claude:** `UserPromptSubmit` supplies the prompt, so the keyword cue is dependable. The early
  percentage cue is only best-effort: the status line receives `used_percentage`, writes a
  per-session temp file, and the Stop hook reads that side channel. With a valid ≥30% signal, Stop
  blocks once and tells the agent to hand off. It does not perform or attest the handoff.
- **Codex:** Agentsmith can install the keyword hook. The inspected supported hook/config surface
  does not provide a first-party, per-session context-percentage signal, so no percentage cue is
  shipped. `queue` can address an existing thread and `fork` can fork one; neither command's help
  establishes a blank-context rollover contract. `app-server` is explicitly experimental.

These are different problems: **triggering a cue** asks the current agent to preserve state;
**automatic rollover** must prove that preservation happened and start exactly one clean successor.

## Minimum safe rollover protocol

1. **Stable trigger.** Receive a first-party event carrying runtime, session ID, current working
   directory, and used-context percentage. A missing or malformed signal fails open to the keyword
   path; an estimate derived from transcript scraping is not sufficient.
2. **Completion receipt.** The source session writes the normal handoff note plus a small
   machine-readable receipt keyed by session ID. It records note path, item, repository root,
   branch, HEAD, safe-state kind (`clean`, `commit`, or `stash`) and reference, kickoff text, and
   completion time. The controller treats the agent's prose as a claim until these fields agree
   with git and the note exists.
3. **Safe-state gate.** Never start the successor while tracked work is silently dirty. If a stash
   is the safe state, record its exact reference; if the repo cannot be made safe, retain the
   current session and surface the blocker.
4. **Fresh-thread bootstrap.** Use a supported runtime API that creates a genuinely new context at
   the same repository root and submits only the receipt's kickoff prompt. Continuing or queuing
   the source thread is not rollover; forking is acceptable only if the runtime documents and can
   prove blank-context semantics.
5. **Idempotency and recovery.** Persist controller state outside the conversation. Deduplicate by
   source session + threshold crossing, create at most one successor, and mark completion only
   after its ID is recorded. On timeout, invalid receipt, dirty tree, or launch failure, do not
   retry blindly: leave the current session usable and show the durable note/kickoff for manual
   recovery.

The receipt is the portable seam. Claude and Codex adapters may differ, but safe-state validation,
idempotency, audit state, and the kickoff payload must not.

## Go / no-go criteria

Build a small, opt-in prototype for a runtime only when all of these are true:

- a stable first-party event exposes per-session used-context percentage near 25–30%;
- a supported API creates a blank successor session with explicit working directory and prompt;
- the receipt and git checks can fail closed without losing or duplicating work;
- crash recovery and duplicate-trigger tests prove at-most-one successor creation;
- the adapter does not depend on experimental commands, private schemas, cached model metadata, or
  transcript/token estimates.

## Conclusion / recommendation

**No-go for an automatic rollover orchestrator today.** Keep the 30%-used Claude nudge as a
best-effort enforced cue and the keyword hook as the cross-runtime path. Do not build on Codex's
experimental `app-server` or infer context consumption from internal/runtime files. Revisit with a
bounded prototype when at least one runtime exposes both a stable context-usage event and a
documented blank-session creation API; until then, automation would add a service without being
able to prove the two facts that matter: *handoff completed* and *successor is fresh*.

## Open questions / NOT checked

- Whether future Claude or Codex releases add a stable early-context event.
- Whether a future Codex session-creation API documents blank-context rather than fork semantics.
- Cross-platform process supervision and UI presentation; these matter only after the two primary
  API gates above pass.
