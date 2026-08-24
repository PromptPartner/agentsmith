#!/usr/bin/env bash
# Non-regression suite for the cross-runtime UserPromptSubmit handoff hook.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="${HOOK_BIN:-$SCRIPT_DIR/../hooks/handoff-on-keyword.sh}"
BASH_BIN="$(command -v bash)"

if ! command -v jq >/dev/null 2>&1; then
  echo "test-handoff-on-keyword: SKIP — jq not installed, hook schemas not exercised (CI covers it)."
  exit 0
fi

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
silent() { [ -z "${1//[[:space:]]/}" ]; }

emit() { printf '%s' "$1" | bash "$HOOK" 2>/dev/null; }

echo "test-handoff-on-keyword — emits each runtime's context shape"

claude='{"hook_event_name":"UserPromptSubmit","prompt":"Please HANDOFF now","session_id":"claude-1"}'
out="$(emit "$claude")"
if jq -e '.hookSpecificOutput.hookEventName == "UserPromptSubmit" and (.hookSpecificOutput.additionalContext | contains("HANDOFF REQUESTED"))' >/dev/null 2>&1 <<<"$out"; then
  ok "current Claude prompt → nested hookSpecificOutput"
else
  bad "current Claude prompt did not produce Claude's context shape"
fi

codex='{"hook_event_name":"UserPromptSubmit","prompt":"please wrap up","session_id":"codex-1","turn_id":"turn-1","model":"test"}'
out="$(emit "$codex")"
if jq -e '.hookSpecificOutput.hookEventName == "UserPromptSubmit" and (.hookSpecificOutput.additionalContext | contains("HANDOFF REQUESTED")) and (has("additionalContext") | not)' >/dev/null 2>&1 <<<"$out"; then
  ok "Codex prompt + turn_id → nested hookSpecificOutput"
else
  bad "Codex prompt did not produce Codex's context shape"
fi

legacy='{"hook_event_name":"UserPromptSubmit","prompt_text":"handoff","session_id":"claude-legacy"}'
out="$(emit "$legacy")"
if jq -e '.additionalContext | contains("HANDOFF REQUESTED")' >/dev/null 2>&1 <<<"$out"; then
  ok "legacy Claude prompt_text → preserved top-level additionalContext"
else
  bad "legacy Claude prompt_text compatibility regressed"
fi

# The hook has no state: the same input always yields the same context and never duplicates it.
out1="$(emit "$codex")"; out2="$(emit "$codex")"
if [ "$out1" = "$out2" ] && [ "$(jq '[.. | strings | select(contains("HANDOFF REQUESTED"))] | length' <<<"$out1")" -eq 1 ]; then
  ok "repeat invocation is deterministic and emits one context value"
else
  bad "repeat invocation changed or duplicated the context"
fi

echo "test-handoff-on-keyword — stays silent and fail-open"

out="$(emit '{"prompt":"continue the implementation","turn_id":"turn-2"}')"
if silent "$out"; then ok "unrelated prompt → silent"; else bad "unrelated prompt produced output"; fi

out="$(printf 'not json {{' | bash "$HOOK" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out"; then ok "malformed input → successful silent no-op"; else bad "malformed input did not fail open (rc=$rc)"; fi

out="$(printf '%s' "$codex" | PATH="" "$BASH_BIN" "$HOOK" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out"; then ok "jq absent → successful silent no-op"; else bad "jq absent did not fail open (rc=$rc)"; fi

echo
printf 'test-handoff-on-keyword: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
