#!/usr/bin/env bash
# PreToolUse nudge — remind the agent to consult DESIGN.md when it edits UI (opt-in, fail-safe).
#
# Fires at most ONCE per session, and only when BOTH hold:
#   • the edit targets a UI file — *.tsx *.jsx *.vue *.svelte *.css *.scss *.less *.astro, or a
#     path under a components/ or ui/ directory; AND
#   • a DESIGN.md exists at the project root (so backend/CLI/library projects never see it).
# It NEVER blocks the edit and NEVER auto-approves it: it only injects a one-line reminder via the
# PreToolUse `additionalContext` field, then lets the normal permission flow proceed. Every surprise
# — no jq, malformed input, non-UI path, no DESIGN.md, already nudged — is a silent no-op.
#
# Model: hooks/context-budget-nudge.sh (once-per-session marker, jq-guarded, fail-open).
#
# Wire it (global ~/.claude/settings.json):
#   "hooks": { "PreToolUse": [ { "matcher": "Edit|Write|MultiEdit", "hooks": [
#     { "type": "command", "command": "bash ~/.claude/hooks/ui-design-reminder.sh" } ] } ] }
#
# Hook stdin/output schemas can drift between Claude Code versions; this stays fail-open (a bad read
# or an unknown field → no-op, never a blocked edit). Verified against the PreToolUse contract
# (tool_input.file_path input; hookSpecificOutput.additionalContext, exit 0 = normal flow) at time
# of writing — see docs at code.claude.com/docs/en/hooks.
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)
tool=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null) || exit 0
case "$tool" in Edit|Write|MultiEdit) ;; *) exit 0 ;; esac

fp=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$fp" ] || exit 0
fp=${fp//\\//}                                 # normalise Windows backslashes so dir globs match
case "$fp" in
  *.tsx|*.jsx|*.vue|*.svelte|*.css|*.scss|*.less|*.astro|*/components/*|*/ui/*) ;;
  *) exit 0 ;;                                  # not a UI file → silent
esac

# The self-gate: a DESIGN.md at the project root. No design system declared → stay silent, so backend
# projects never see this. Check the session cwd first, then the git root (covers a subdir cwd).
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null) || exit 0
[ -n "$cwd" ] || cwd=.
root="$cwd"
if [ ! -f "$root/DESIGN.md" ]; then
  gr=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || gr=""
  [ -n "$gr" ] && root="$gr"
fi
[ -f "$root/DESIGN.md" ] || exit 0

# Once per session (marker keyed by session_id): a screen's worth of edits nudges once, not N times.
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
marker="${TMPDIR:-/tmp}/claude-uidesign-${sid:-default}.nudged"
[ -f "$marker" ] && exit 0
: > "$marker" 2>/dev/null || true

jq -n --arg f "$fp" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ("Editing UI (" + $f + "). This project declares a design system in DESIGN.md — read it and match it (colors, type, spacing, components, states) before changing UI. If DESIGN.md still reads \"[TODO]\", establish the design system first. Update DESIGN.md in the same change when you add or restyle a component.")
  }
}'
exit 0
