#!/usr/bin/env bash
# Universal verification runner — the single "is this work shippable?" entry point
# referenced by the core "Verify before you call it done" rule (R5).
#
# It runs a list of PHASES defined in .harness/verify.conf, in order, and exits
# non-zero on the first failure with a one-line pointer at what to look at. The
# phases are whatever THIS project needs — code build/test, a markdown link
# check, a data-validation script, a spell-check, a dry-run — the runner doesn't
# care, it just executes and reports. Same entry point for the agent and the human.
#
# Usage:
#   ./scripts/verify.sh                # run every phase in .harness/verify.conf
#   ./scripts/verify.sh --only <tag>   # run only phases whose label contains <tag>
#   ./scripts/verify.sh --list         # list configured phases, don't run
#   ./scripts/verify.sh --help
#
# .harness/verify.conf format — one phase per line, "Label :: shell command":
#   build      :: <your build command>
#   tests      :: <your test command>
#   lint       :: <your lint command>
#   links      :: <your link/spell/render check>
# Lines starting with # and blank lines are ignored. See verify.conf.example.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONF="$ROOT_DIR/.harness/verify.conf"

if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'
  CYAN=$'\033[0;36m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

ONLY=""
LIST_ONLY=false

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --only) shift; ONLY="${1:-}"; [ -z "$ONLY" ] && { echo "${RED}--only needs a tag${RESET}"; exit 2; } ;;
    --list) LIST_ONLY=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "${RED}Unknown option: $1${RESET}"; usage; exit 2 ;;
  esac
  shift
done

if [ ! -f "$CONF" ]; then
  echo "${RED}No phase config at .harness/verify.conf${RESET}"
  echo "${YELLOW}Create it (see .harness/verify.conf.example) — list the commands that prove this project is shippable.${RESET}"
  exit 2
fi

# Parse "Label :: command" lines (skip comments/blanks).
LABELS=(); CMDS=()
while IFS= read -r line; do
  [ -z "${line//[[:space:]]/}" ] && continue
  case "$line" in \#*) continue ;; esac
  label="${line%%::*}"; cmd="${line#*::}"
  label="$(echo "$label" | sed 's/[[:space:]]*$//;s/^[[:space:]]*//')"
  cmd="$(echo "$cmd" | sed 's/^[[:space:]]*//')"
  [ -z "$cmd" ] && continue
  if [ -n "$ONLY" ] && [[ "$label" != *"$ONLY"* ]]; then continue; fi
  LABELS+=("$label"); CMDS+=("$cmd")
done < "$CONF"

TOTAL=${#LABELS[@]}
if [ "$TOTAL" -eq 0 ]; then
  echo "${YELLOW}No matching phases.${RESET}"; exit 0
fi

if $LIST_ONLY; then
  echo "${BOLD}Configured phases:${RESET}"
  for i in "${!LABELS[@]}"; do printf '  %d. %s :: %s\n' "$((i+1))" "${LABELS[$i]}" "${CMDS[$i]}"; done
  exit 0
fi

cd "$ROOT_DIR"
START=$SECONDS
for i in "${!LABELS[@]}"; do
  echo; echo "${BOLD}${CYAN}[$((i+1))/$TOTAL] ${LABELS[$i]}${RESET}"
  echo "  ${CMDS[$i]}"
  if ! bash -c "${CMDS[$i]}"; then
    echo; echo "${BOLD}${RED}verify.sh: phase '${LABELS[$i]}' failed.${RESET}"
    echo "${YELLOW}Run that command directly to iterate, then re-run verify.sh.${RESET}"
    exit 1
  fi
done

echo; echo "${BOLD}${GREEN}verify.sh: all $TOTAL phase(s) passed in $((SECONDS-START))s.${RESET}"
