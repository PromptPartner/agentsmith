#!/usr/bin/env bash
# Stop hook — BEST-EFFORT context-budget nudge (opt-in, experimental).
#
# HONEST CAVEAT: no Claude Code hook receives the live context-% (only the statusline does), so
# this reads the % that config/statusline-command.sh persisted to a temp file. That makes it
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
# earlier, up to ~40 to use more of the band).
#
# Wire it (global ~/.claude/settings.json):
#   "hooks": { "Stop": [ { "hooks": [
#     { "type": "command", "command": "bash ~/.claude/hooks/context-budget-nudge.sh" } ] } ] }
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0

THRESHOLD="${HANDOFF_PCT_THRESHOLD:-30}"
input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)
pf="${TMPDIR:-/tmp}/claude-ctx-${sid:-default}.pct"
marker="${TMPDIR:-/tmp}/claude-ctx-${sid:-default}.nudged"

[ -f "$pf" ] || exit 0                       # no signal yet → do nothing
[ -f "$marker" ] && exit 0                    # already nudged this session → don't loop

pct=$(tr -dc '0-9.' < "$pf" 2>/dev/null); pint=${pct%.*}
[ -z "${pint:-}" ] && exit 0

if [ "$pint" -ge "$THRESHOLD" ]; then
  : > "$marker"
  jq -n --arg p "$pint" '{decision:"block", reason:("Context is at " + $p + "% used — at the handoff cue (hand off EARLY, while the model is still sharp, not when the window is nearly full). Before you stop: bring the working tree to a safe state (commit/stash), write a handoff note, and output a ready-to-paste post-/clear recall prompt (issue/branch IDs, what is done, exact next step, gotchas). Then stop.")}'
fi
exit 0
