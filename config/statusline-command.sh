#!/bin/bash
# Legacy manual Bash renderer. Current installs use config/statusline.py so Windows and POSIX
# share a dependency-free implementation; this file remains for existing manual configurations.
# Claude Code status line — user@host:/cwd  [model]  ctx:NN%
# The ctx:NN% gauge shows context USED. It is visibility, not a universal quality boundary:
# reliable capacity varies by model, task, prompt position, and conversation history. Hand off at
# a natural phase boundary or at a threshold you calibrated on your own work. See core/50.
input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Persist context-usage % to a per-session temp file. No hook receives context% directly, so the
# opt-in handoff Stop hook (hooks/context-budget-nudge.sh) reads it from here. Harmless if unused.
sid=$(echo "$input" | jq -r '.session_id // empty')
if [[ "$sid" =~ ^[A-Za-z0-9._-]{1,128}$ ]] && [[ "$used" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  printf '%s' "$used" > "${TMPDIR:-/tmp}/claude-ctx-${sid}.pct" 2>/dev/null || true
fi

# PS1-style prefix: bold green user@host, reset, colon, bold blue cwd, reset
prefix=$(printf '\033[01;32m%s@%s\033[00m:\033[01;34m%s\033[00m' "$(whoami)" "$(hostname -s)" "${cwd:-$(pwd)}")

model_part=""
[ -n "$model" ] && model_part="  $model"

ctx_part=""
[ -n "$used" ] && ctx_part="  ctx:$(printf '%.0f' "$used")%"

printf '%s%s%s\n' "$prefix" "$model_part" "$ctx_part"
