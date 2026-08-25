#!/usr/bin/env bash
# Non-regression suite for the Claude-only Stop hook context-budget nudge.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="${HOOK_BIN:-$SCRIPT_DIR/../hooks/context-budget-nudge.sh}"
BASH_BIN="$(command -v bash)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if ! command -v jq >/dev/null 2>&1; then
  echo "test-context-budget-nudge: SKIP — jq not installed, hook response not exercised (CI covers it)."
  exit 0
fi

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
silent() { [ -z "${1//[[:space:]]/}" ]; }
signal_path() { printf '%s/claude-ctx-%s.pct' "$TMP" "$1"; }
marker_path() { printf '%s/claude-ctx-%s.nudged' "$TMP" "$1"; }
write_signal() { printf '%s' "$2" > "$(signal_path "$1")"; }
emit() {
  local sid="$1" threshold="${2:-}"
  if [ -n "$threshold" ]; then
    printf '{"hook_event_name":"Stop","session_id":"%s"}' "$sid" |
      TMPDIR="$TMP" HANDOFF_PCT_THRESHOLD="$threshold" bash "$HOOK" 2>/dev/null
  else
    printf '{"hook_event_name":"Stop","session_id":"%s"}' "$sid" |
      TMPDIR="$TMP" bash "$HOOK" 2>/dev/null
  fi
}

echo "test-context-budget-nudge — threshold and fail-open behavior"

out="$(emit missing)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out" && [ ! -e "$(marker_path missing)" ]; then
  ok "missing signal → successful silent no-op"
else
  bad "missing signal did not fail open"
fi

write_signal malformed '30 percent'
out="$(emit malformed)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out" && [ ! -e "$(marker_path malformed)" ]; then
  ok "malformed signal → successful silent no-op"
else
  bad "malformed signal was interpreted as a percentage"
fi

write_signal stale 31
touch -t 200001010000 "$(signal_path stale)"
out="$(emit stale)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out" && [ ! -e "$(marker_path stale)" ]; then
  ok "stale signal → successful silent no-op"
else
  bad "stale signal triggered a handoff"
fi

write_signal below 29
out="$(emit below)"
if silent "$out" && [ ! -e "$(marker_path below)" ]; then
  ok "29% used → silent below default threshold"
else
  bad "29% used unexpectedly nudged"
fi

write_signal boundary 30
out="$(emit boundary)"
if jq -e '.decision == "block" and (.reason | contains("30% used"))' >/dev/null 2>&1 <<<"$out" &&
   [ -f "$(marker_path boundary)" ]; then
  ok "30% used → block response and session marker"
else
  bad "30% boundary did not emit the Stop block response"
fi

write_signal override 25
out="$(emit override 25)"
if jq -e '.decision == "block" and (.reason | contains("25% used"))' >/dev/null 2>&1 <<<"$out"; then
  ok "HANDOFF_PCT_THRESHOLD override controls the boundary"
else
  bad "threshold override was ignored"
fi

write_signal repeat 31
first="$(emit repeat)"; second="$(emit repeat)"
if ! silent "$first" && silent "$second" && [ -f "$(marker_path repeat)" ]; then
  ok "repeat invocation nudges once per session"
else
  bad "repeat invocation did not stay silent after the first nudge"
fi

write_signal isolated-a 30
write_signal isolated-b 30
out_a="$(emit isolated-a)"; out_b="$(emit isolated-b)"
if ! silent "$out_a" && ! silent "$out_b" &&
   [ -f "$(marker_path isolated-a)" ] && [ -f "$(marker_path isolated-b)" ]; then
  ok "different session IDs maintain independent marker state"
else
  bad "one session suppressed another session's nudge"
fi

write_signal invalid-threshold 99
out="$(emit invalid-threshold not-a-number)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out" && [ ! -e "$(marker_path invalid-threshold)" ]; then
  ok "invalid threshold → successful silent no-op"
else
  bad "invalid threshold did not fail open"
fi

out="$(printf '%s' '{"session_id":"../../unsafe"}' | TMPDIR="$TMP" bash "$HOOK" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out"; then
  ok "unsafe session ID → successful silent no-op"
else
  bad "unsafe session ID was accepted for a temp path"
fi

# A missing jq executable must also remain a successful silent no-op.
out="$(printf '{"session_id":"no-jq"}' | TMPDIR="$TMP" PATH="" "$BASH_BIN" "$HOOK" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out"; then
  ok "jq absent → successful silent no-op"
else
  bad "jq absent did not fail open"
fi

echo
printf 'test-context-budget-nudge: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
