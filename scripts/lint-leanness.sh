#!/usr/bin/env bash
# lint-leanness.sh — guardrail for the System-Evolution rule: keep STATIC context lean.
# The assembled instruction file is loaded every turn and paid for every turn. When it grows past a
# budget, that's the cue to move new knowledge into DYNAMIC context (skills, docs/, templates,
# memory) instead of piling more prose into core/. This is a gauge, not a gate — until --strict.
#
# Usage:
#   ./scripts/lint-leanness.sh [file]        # default: managed CLAUDE.md, AGENTS.md, or both
#   ./scripts/lint-leanness.sh --strict [f]  # exit 1 if over budget (wire as a verify phase)
#   ./scripts/lint-leanness.sh --help
# Budgets (override via env):  LEANNESS_MAX_LINES (default 600)  LEANNESS_MAX_TOKENS (default 10000)
# Calibration: no expected sizes are written here — they drift and stale numbers mislead (0007).
# scripts/test-assemble.sh measures each core+profile assembly per run and is the source of truth;
# a core+TWO-profile assembly can exceed this budget. Token count is an estimate (chars/4).
set -euo pipefail

MAX_LINES="${LEANNESS_MAX_LINES:-600}"
MAX_TOKENS="${LEANNESS_MAX_TOKENS:-10000}"
STRICT=false; FILE=""
for a in "$@"; do
  case "$a" in
    --strict) STRICT=true ;;
    --help|-h) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $a" >&2; exit 2 ;;
    *) FILE="$a" ;;
  esac
done

has_managed_block() {
  [ -f "$1" ] && grep -Fq '<!-- BEGIN AGENTSMITH' "$1"
}

FILES=()
COMPARE_MANAGED=false
if [ -n "$FILE" ]; then
  [ -f "$FILE" ] || { echo "lint-leanness: no such file: $FILE" >&2; exit 2; }
  FILES+=("$FILE")
elif has_managed_block CLAUDE.md && has_managed_block AGENTS.md; then
  FILES+=(CLAUDE.md AGENTS.md)
  COMPARE_MANAGED=true
elif has_managed_block CLAUDE.md; then
  FILES+=(CLAUDE.md)
elif has_managed_block AGENTS.md; then
  FILES+=(AGENTS.md)
elif [ -f CLAUDE.md ]; then
  FILES+=(CLAUDE.md) # backwards-compatible fallback for an unmanaged instruction file
elif [ -f AGENTS.md ]; then
  FILES+=(AGENTS.md)
else
  echo "lint-leanness: no CLAUDE.md or AGENTS.md in the current directory" >&2
  exit 2
fi

if [ -t 1 ]; then GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else GREEN=''; YELLOW=''; BOLD=''; RESET=''; fi

over=false
for FILE in "${FILES[@]}"; do
  lines=$(wc -l < "$FILE" | tr -d ' ')
  chars=$(wc -c < "$FILE" | tr -d ' ')
  tokens=$(( chars / 4 ))
  pct_l=$(( lines * 100 / MAX_LINES ))
  pct_t=$(( tokens * 100 / MAX_TOKENS ))

  file_over=false
  [ "$lines"  -gt "$MAX_LINES"  ] && file_over=true
  [ "$tokens" -gt "$MAX_TOKENS" ] && file_over=true

  printf '%sleanness%s  %s\n' "$BOLD" "$RESET" "$FILE"
  printf '  lines : %4d / %-4d  (%d%%)\n' "$lines"  "$MAX_LINES"  "$pct_l"
  printf '  tokens: ~%4d / %-4d  (%d%%, est chars/4)\n' "$tokens" "$MAX_TOKENS" "$pct_t"

  if $file_over; then
    over=true
    printf '%s  WARN: static context is over budget.%s Trim core/, or move new rules into a skill,\n' "$YELLOW" "$RESET"
    printf '        a docs/ page, or a template (dynamic context) instead of the instruction file.\n'
  else
    printf '%s  OK%s — lean enough.\n' "$GREEN" "$RESET"
  fi
done

mismatch=false
if $COMPARE_MANAGED; then
  if diff -q \
    <(sed -n '/<!-- BEGIN AGENTSMITH/,/<!-- END AGENTSMITH/p' CLAUDE.md) \
    <(sed -n '/<!-- BEGIN AGENTSMITH/,/<!-- END AGENTSMITH/p' AGENTS.md) >/dev/null; then
    printf '%smanaged rules%s  CLAUDE.md = AGENTS.md\n' "$GREEN" "$RESET"
  else
    mismatch=true
    printf '%s  WARN: CLAUDE.md and AGENTS.md managed rules differ.%s Re-run setup for both platforms.\n' "$YELLOW" "$RESET"
  fi
fi

if $STRICT && { $over || $mismatch; }; then exit 1; fi
exit 0
