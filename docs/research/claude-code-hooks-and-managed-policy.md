# Research: Claude Code hooks, context visibility & managed policy

> Source material and findings. NEVER delete this in a cleanup/rebase — if it's
> obsolete, move it to docs/research/_archive/ instead (R9). Verified 2026-06-25
> against the official Claude Code docs (code.claude.com/docs). Underpins roadmap
> items #3 (context/handoff trigger), #5 (guardrail hooks), #9 (org-policy variant).

## Question / scope

Can a hook/skill/plugin **see the live context-window usage** and auto-trigger a
handoff at a threshold? What hook events exist, and can a hook **inject a message
back** to the model? What are the exact **enterprise managed-policy paths** and the
keys to **harden permissions** (disable bypass mode) on a shared machine?

## Sources consulted
- https://code.claude.com/docs/en/hooks.md — hook events + I/O schema
- https://code.claude.com/docs/en/hooks-guide.md — structured JSON output / context injection
- https://code.claude.com/docs/en/how-claude-code-works.md — compaction behaviour
- https://code.claude.com/docs/en/admin-setup.md — org setup
- https://code.claude.com/docs/en/server-managed-settings.md — managed settings paths
- https://code.claude.com/docs/en/permissions.md — managed-only permission keys
- https://code.claude.com/docs/en/memory.md — org-wide CLAUDE.md
- Feature requests confirming the context-visibility gap:
  github.com/anthropics/claude-code/issues/46695, /25689, /34202

## Findings

### A. Context-window visibility to hooks — the key answer
**No hook receives context-window / token-usage in its stdin payload.** (HIGH confidence.)
The common hook input fields are `session_id`, `transcript_path`, `cwd`,
`permission_mode`, `hook_event_name`, `effort.level`, optional `agent_id`/`agent_type`.
There is **no** `context_window`, `token_usage`, `used_percentage`, or
`tokens_remaining` field on any event. Only the **statusline** command receives
`context_window.used_percentage` (we already use it in config/statusline-command.sh).
This is a known gap (open feature requests above).

Implication: a **fully-automatic %-threshold handoff trigger is not reliably
possible today**. Be honest about this in the harness — don't pretend a hook can
watch the gauge.

### B. Hook events (current list, abridged)
SessionStart, Setup, SessionEnd · UserPromptSubmit, UserPromptExpansion, Stop,
StopFailure · PreToolUse, PostToolUse, PostToolUseFailure, PostToolBatch,
PermissionRequest/Denied · PreCompact, PostCompact · SubagentStart/Stop ·
Notification, MessageDisplay · ConfigChange, CwdChanged, FileChanged,
InstructionsLoaded · TaskCreated/Completed, TeammateIdle · WorktreeCreate/Remove ·
Elicitation/Result.

### C. PreCompact as a "context nearly full" signal — too late, reactive
PreCompact fires *before* compaction, matcher `manual` or `auto`. Auto-compaction
triggers near ~95% capacity (internal buffer ~20–45k tokens). It's a post-hoc event:
by the time it fires, compaction is already imminent. **Not usable** for an *early*
proactive nudge at ~25–30% **used** (the Opus-4.8 sweet-spot cue). Threshold is not
configurable as of 2026-06. (MEDIUM confidence on exact %, from docs + GitHub issues.)

### D. Injecting a message back to the model — supported, varies by event (HIGH)
- **UserPromptSubmit**: input includes `prompt_text`. Output `{"additionalContext": "..."}`
  on exit 0 injects text the model reads. → the reliable "handoff" keyword path.
- **SessionStart / PreCompact**: stdout / `additionalContext` on exit 0 appends context
  (used to restore instructions after compaction).
- **Stop**: `{"hookSpecificOutput":{"hookEventName":"Stop","decision":"block","reason":"..."}}`
  — `decision:"block"` shows `reason` to the model and prevents the stop (model continues).
- Caveat: injected text is a *system reminder the model reads*, not a code path — the
  model still decides. Stop-hook output is visible to the model, not prominently to the user.

### E. Feasibility verdicts for the #3 handoff trigger
1. **"handoff"/"wrap up" keyword → handoff instructions** via a UserPromptSubmit hook:
   **solid, ship it.** (HIGH)
2. **%-threshold auto-nudge** via statusline writing `used_percentage` to a temp file +
   a Stop hook reading it and `decision:block`-injecting a reminder above threshold:
   **technically works, but fragile** — statusline/Stop timing drift, stale file if the
   statusline process dies, no documented example. Ship as **opt-in, best-effort**, clearly
   labelled; keep the human-watched `ctx:NN%` gauge as the primary trigger. (MEDIUM)
3. **Leanness lint** (keep static context small) is the complementary lever — fewer tokens
   in CLAUDE.md = the threshold arrives later.

### F. Enterprise managed-policy paths (HIGH)
| OS | Managed settings | Org-wide CLAUDE.md |
|----|------------------|--------------------|
| Linux/WSL | `/etc/claude-code/managed-settings.json` (+ `managed-settings.d/`) | `/etc/claude-code/CLAUDE.md` |
| macOS | `/Library/Application Support/ClaudeCode/managed-settings.json` (+ `.d/`) | `/Library/Application Support/ClaudeCode/CLAUDE.md` |
| Windows | `C:\Program Files\ClaudeCode\managed-settings.json` (+ `.d\`) | `C:\Program Files\ClaudeCode\CLAUDE.md` |

- Org CLAUDE.md loads **before** user + project CLAUDE.md, every session, and **cannot be
  excluded** by user/project settings. Alternative: `"claudeMd":"..."` inline in
  managed-settings.json.
- Legacy Windows `C:\ProgramData\ClaudeCode\managed-settings.json` is **no longer supported**
  (≥ v2.1.75).

### G. Permission hardening keys — managed-only (HIGH)
```json
{ "permissions": {
    "disableBypassPermissionsMode": "disable",   // blocks --dangerously-skip-permissions / bypass mode
    "disableAutoMode": "disable"                  // disables background 'auto' permission mode
} }
```
**These only take effect in a managed-settings file** (no effect in user/project settings).
Managed settings are highest precedence and cannot be overridden by CLI/user/project.
This is the inverse of our default `skipDangerousModePermissionPrompt: true` — the
hardened org profile drops that and adds the two `disable` keys.

## Open questions / what was NOT checked
- Exact auto-compaction % and whether it will become configurable (tracking GH #46695/#34202).
- Whether `statusline.interval` is honoured on all clients (render frequency affects the
  best-effort temp-file freshness).
- Did not test the Stop-hook `decision:block` injection end-to-end on this box — design is
  doc-grounded; the harness ships it opt-in so a user can validate in their own session.
