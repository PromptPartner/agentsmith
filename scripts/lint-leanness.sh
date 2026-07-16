#!/usr/bin/env bash
# lint-leanness.sh — guardrail for the System-Evolution rule: keep STATIC context lean.
# The assembled CLAUDE.md is loaded every turn and paid for every turn. When it grows past a
# budget, that's the cue to move new knowledge into DYNAMIC context (skills, docs/, templates,
# memory) instead of piling more prose into core/. This is a gauge, not a gate — until --strict.
#
# Usage:
#   ./scripts/lint-leanness.sh [file]        # default: ./CLAUDE.md
#   ./scripts/lint-leanness.sh --strict [f]  # exit 1 if over budget (wire as a verify phase)
#   ./scripts/lint-leanness.sh --help
# Budgets (override via env):  LEANNESS_MAX_LINES (default 600)  LEANNESS_MAX_TOKENS (default 10000)
# Calibration: core alone ~350 lines; core + one profile ~450; core + two ~535. The budget sits
# above a normal two-profile assembly so it flags genuine bloat (3+ profiles, or lots of custom
# rules), not a supported config. Token count is an estimate (chars/4) — a gauge, not a tokenizer.
set -euo pipefail

MAX_LINES="${LEANNESS_MAX_LINES:-600}"
MAX_TOKENS="${LEANNESS_MAX_TOKENS:-10000}"
STRICT=false; FILE=""
for a in "$@"; do
  case "$a" in
    --strict) STRICT=true ;;
    --help|-h) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $a" >&2; exit 2 ;;
    *) FILE="$a" ;;
  esac
done
FILE="${FILE:-CLAUDE.md}"
[ -f "$FILE" ] || { echo "lint-leanness: no such file: $FILE" >&2; exit 2; }

if [ -t 1 ]; then GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else GREEN=''; YELLOW=''; BOLD=''; RESET=''; fi

lines=$(wc -l < "$FILE" | tr -d ' ')
chars=$(wc -c < "$FILE" | tr -d ' ')
tokens=$(( chars / 4 ))
pct_l=$(( lines * 100 / MAX_LINES ))
pct_t=$(( tokens * 100 / MAX_TOKENS ))

over=false
[ "$lines"  -gt "$MAX_LINES"  ] && over=true
[ "$tokens" -gt "$MAX_TOKENS" ] && over=true

printf '%sleanness%s  %s\n' "$BOLD" "$RESET" "$FILE"
printf '  lines : %4d / %-4d  (%d%%)\n' "$lines"  "$MAX_LINES"  "$pct_l"
printf '  tokens: ~%4d / %-4d  (%d%%, est chars/4)\n' "$tokens" "$MAX_TOKENS" "$pct_t"

if $over; then
  printf '%s  WARN: static context is over budget.%s Trim core/, or move new rules into a skill,\n' "$YELLOW" "$RESET"
  printf '        a docs/ page, or a template (dynamic context) instead of CLAUDE.md.\n'
  $STRICT && exit 1 || exit 0
else
  printf '%s  OK%s — lean enough.\n' "$GREEN" "$RESET"
fi
