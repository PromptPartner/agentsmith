#!/usr/bin/env bash
# UserPromptSubmit hook — RELIABLE handoff trigger.
# When the user says "handoff" or "wrap up", inject the handoff protocol so the agent
# safe-states and emits a recall prompt before context runs out. This path needs NO
# context-% visibility — it keys off the prompt text, which the hook always receives.
# See core/50-git-and-handoff and docs/research/claude-code-hooks-and-managed-policy.md.
#
# Wire it (global ~/.claude/settings.json):
#   "hooks": { "UserPromptSubmit": [ { "hooks": [
#     { "type": "command", "command": "bash ~/.claude/hooks/handoff-on-keyword.sh" } ] } ] }
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0   # no jq → silently no-op, never block the prompt

input=$(cat)
prompt=$(printf '%s' "$input" | jq -r '.prompt_text // .prompt // empty' 2>/dev/null)
shopt -s nocasematch 2>/dev/null || true

if [[ "$prompt" =~ handoff || "$prompt" =~ wrap[[:space:]]+up ]]; then
  jq -n '{additionalContext: "HANDOFF REQUESTED. Before anything else: (1) bring the working tree to a SAFE STATE — commit or stash so nothing half-edited is lost; (2) write a durable handoff note (memory and/or the project tracker); (3) output a ready-to-paste, post-/clear recall prompt that carries the issue/branch IDs, what is done (commit SHAs / PR links / merge state), the EXACT next step, and the gotchas/decisions a fresh session would otherwise re-derive. Keep it tight; do this before any new work."}'
fi
exit 0
