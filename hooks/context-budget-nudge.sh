#!/usr/bin/env bash
# Stop hook — BEST-EFFORT context-budget nudge (opt-in, experimental).
#
# HONEST CAVEAT: no Claude Code hook receives the live context-% (only the statusline does), so
# this reads the % that config/statusline.py persisted to a temp file. That makes it
# inherently fragile — the file can be stale (statusline hasn't rendered since the last turn) or
# missing (statusline not installed / crashed). The RELIABLE handoff path is the "handoff"
# keyword (hooks/handoff-on-keyword.sh) and the human-watched ctx:NN% gauge. Treat this as a
# backstop, not a guarantee. See docs/research/claude-code-hooks-and-managed-policy.md.
#
# Behaviour: when an operator-configured context USED threshold is reached, it nudges ONCE per
# session (a marker file prevents a block-loop), asking the agent to safe-state + write a recall
# prompt before stopping.
#
# No percentage is a reliable universal quality boundary: behavior varies by model, task, prompt
# position, and conversation history. The hook is therefore disabled until HANDOFF_PCT_THRESHOLD
# is set to an integer from 1–100. Treat that value as a personal workflow cue, calibrated on your
# own tasks. Signals older than 300 seconds fail open; tune that bounded freshness window with
# HANDOFF_SIGNAL_MAX_AGE_SECONDS (1–3600).
#
# Wire it (global ~/.claude/settings.json):
#   "hooks": { "Stop": [ { "hooks": [
#     { "type": "command", "command": "bash ~/.claude/hooks/context-budget-nudge.sh" } ] } ] }
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0

THRESHOLD="${HANDOFF_PCT_THRESHOLD:-}"
MAX_SIGNAL_AGE="${HANDOFF_SIGNAL_MAX_AGE_SECONDS:-300}"
input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null) || exit 0

# Invalid configuration and unscoped events must stay silent. Falling back to a shared
# "default" file can leak a percentage between sessions and produce a false handoff cue.
[ -n "$THRESHOLD" ] || exit 0
[[ "$THRESHOLD" =~ ^[0-9]+$ ]] || exit 0
[ "$THRESHOLD" -ge 1 ] 2>/dev/null && [ "$THRESHOLD" -le 100 ] 2>/dev/null || exit 0
[[ "$MAX_SIGNAL_AGE" =~ ^[0-9]+$ ]] || exit 0
[ "$MAX_SIGNAL_AGE" -ge 1 ] 2>/dev/null && [ "$MAX_SIGNAL_AGE" -le 3600 ] 2>/dev/null || exit 0
[[ "$sid" =~ ^[A-Za-z0-9._-]{1,128}$ ]] || exit 0

pf="${TMPDIR:-/tmp}/claude-ctx-${sid}.pct"
marker="${TMPDIR:-/tmp}/claude-ctx-${sid}.nudged"

[ -f "$pf" ] || exit 0                       # no signal yet → do nothing
[ -f "$marker" ] && exit 0                    # already nudged this session → don't loop

# A statusline may stop rendering or a runtime may reuse a session identifier after recovery.
# Never act on a side-channel value older than five minutes (configurable, capped at one hour).
if mtime=$(stat -c %Y "$pf" 2>/dev/null); then       # GNU/Linux
  :
elif mtime=$(stat -f %m "$pf" 2>/dev/null); then    # BSD/macOS
  :
else
  exit 0
fi
now=$(date +%s 2>/dev/null) || exit 0
[[ "$mtime" =~ ^[0-9]+$ ]] && [[ "$now" =~ ^[0-9]+$ ]] || exit 0
age=$((now - mtime))
[ "$age" -ge 0 ] 2>/dev/null && [ "$age" -le "$MAX_SIGNAL_AGE" ] 2>/dev/null || exit 0

pct=$(tr -d '[:space:]' < "$pf" 2>/dev/null) || exit 0
[[ "$pct" =~ ^[0-9]+([.][0-9]+)?$ ]] || exit 0
pint=${pct%%.*}
[ "$pint" -le 100 ] 2>/dev/null || exit 0

if [ "$pint" -ge "$THRESHOLD" ]; then
  output=$(jq -n --arg p "$pint" '{decision:"block", reason:("Context is at " + $p + "% used — at your configured handoff cue. Context reliability varies by model, task, and conversation history; this percentage is a personal workflow heuristic, not a quality boundary. Before you stop: bring the working tree to a safe state, write a handoff note, and output a ready-to-paste recall prompt with the item, branch, completed work, exact next step, and gotchas. Then stop.")}') || exit 0
  : > "$marker"
  printf '%s\n' "$output"
fi
exit 0
