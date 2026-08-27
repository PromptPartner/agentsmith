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
# Behaviour: when context USED ≥ threshold, it nudges ONCE per session (a marker file prevents a
# block-loop), asking the agent to safe-state + write a recall prompt before stopping.
#
# THRESHOLD IS "USED", NOT "LEFT", AND IT IS DELIBERATELY LOW. The cue to hand off + /clear is
# when the window is ~25-30% USED — early, while the model is still sharp — NOT when it's nearly
# full. Reason: model quality degrades as the window fills; for Opus 4.8 the sweet spot is ~25-40%
# used, so you hand off near the BOTTOM of that band (leaving headroom to write the handoff and
# clear before quality drifts). Default 30 used. Tune with HANDOFF_PCT_THRESHOLD (e.g. 25 to fire
# earlier, up to ~40 to use more of the band). Signals older than 300 seconds fail open; tune that
# bounded freshness window with HANDOFF_SIGNAL_MAX_AGE_SECONDS (1–3600).
#
# Wire it (global ~/.claude/settings.json):
#   "hooks": { "Stop": [ { "hooks": [
#     { "type": "command", "command": "bash ~/.claude/hooks/context-budget-nudge.sh" } ] } ] }
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0

THRESHOLD="${HANDOFF_PCT_THRESHOLD:-30}"
MAX_SIGNAL_AGE="${HANDOFF_SIGNAL_MAX_AGE_SECONDS:-300}"
input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null) || exit 0

# Invalid configuration and unscoped events must stay silent. Falling back to a shared
# "default" file can leak a percentage between sessions and produce a false handoff cue.
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
  output=$(jq -n --arg p "$pint" '{decision:"block", reason:("Context is at " + $p + "% used — at the handoff cue (hand off EARLY, while the model is still sharp, not when the window is nearly full). Before you stop: bring the working tree to a safe state (commit/stash), write a handoff note, and output a ready-to-paste post-/clear recall prompt (issue/branch IDs, what is done, exact next step, gotchas). Then stop.")}') || exit 0
  : > "$marker"
  printf '%s\n' "$output"
fi
exit 0
