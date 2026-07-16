#!/bin/bash
# Claude Code status line — user@host:/cwd  [model]  ctx:NN%
# The ctx:NN% gauge shows context USED. Hand off + /clear EARLY — when used REACHES ~25-30%,
# not when it's nearly full: model quality degrades as the window fills (Opus 4.8 sweet spot is
# ~25-40% used, so hand off near the bottom of that band). See core/50-git-and-handoff.
input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Persist context-usage % to a per-session temp file. No hook receives context% directly, so the
# opt-in handoff Stop hook (hooks/context-budget-nudge.sh) reads it from here. Harmless if unused.
sid=$(echo "$input" | jq -r '.session_id // empty')
[ -n "$used" ] && printf '%s' "$used" > "${TMPDIR:-/tmp}/claude-ctx-${sid:-default}.pct" 2>/dev/null || true

# PS1-style prefix: bold green user@host, reset, colon, bold blue cwd, reset
prefix=$(printf '\033[01;32m%s@%s\033[00m:\033[01;34m%s\033[00m' "$(whoami)" "$(hostname -s)" "${cwd:-$(pwd)}")

model_part=""
[ -n "$model" ] && model_part="  $model"

ctx_part=""
[ -n "$used" ] && ctx_part="  ctx:$(printf '%.0f' "$used")%"

printf '%s%s%s\n' "$prefix" "$model_part" "$ctx_part"
