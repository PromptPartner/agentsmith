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
#   ./scripts/verify.sh --only <tag>   # run only phases whose label contains <tag>; none = failure
#   ./scripts/verify.sh --list         # list configured phases, don't run
#   ./scripts/verify.sh --wait         # wait for another gate in this worktree instead of failing
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
WAIT=false

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --only) shift; ONLY="${1:-}"; [ -z "$ONLY" ] && { echo "${RED}--only needs a tag${RESET}"; exit 2; } ;;
    --list) LIST_ONLY=true ;;
    --wait) WAIT=true ;;
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
  if [ -n "$ONLY" ]; then empty="No phase label contains --only '$ONLY'."; else empty="verify.conf defines no phases."; fi
  # A listing asserts nothing; a run that executes no phase proves nothing, so it cannot pass.
  if $LIST_ONLY; then echo "${YELLOW}${empty}${RESET}"; exit 0; fi
  echo "${RED}verify.sh: ${empty} Nothing ran, so this is not a pass.${RESET}"; exit 1
fi

if $LIST_ONLY; then
  echo "${BOLD}Configured phases:${RESET}"
  for i in "${!LABELS[@]}"; do printf '  %d. %s :: %s\n' "$((i+1))" "${LABELS[$i]}" "${CMDS[$i]}"; done
  exit 0
fi

# One gate per worktree: two at once (two agents, a hook and a manual run) interleave fixtures and
# receipts. The lock lives in the worktree's own Git directory and is shared with `agentsmith
# verify`; a gate started by the holder itself (a phase that runs a gate) shares the holder's lock.
LOCK="$(git -C "$ROOT_DIR" rev-parse --absolute-git-dir 2>/dev/null)/agentsmith-verify.lock"
[ "$LOCK" = "/agentsmith-verify.lock" ] && LOCK="$ROOT_DIR/.harness/verify.lock"
if [ "${AGENTSMITH_VERIFY_LOCK:-}" != "$LOCK" ]; then
  while ! ( set -o noclobber
            printf '{"pid": %s, "started_at": "%s", "runner": "verify.sh", "target": "%s"}\n' \
              "$$" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$ROOT_DIR" > "$LOCK" ) 2>/dev/null; do
    holder="$(cat "$LOCK" 2>/dev/null || true)"
    pid="$(printf '%s' "$holder" | sed -n 's/.*"pid": *\([0-9][0-9]*\).*/\1/p')"
    started="$(printf '%s' "$holder" | sed -n 's/.*"started_at": *"\([^"]*\)".*/\1/p')"
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$LOCK"; continue   # the holder is gone; reclaim its lock
    fi
    if [ -z "$holder" ] && [ -f "$LOCK" ]; then
      # Being written right now; still empty after 10 s, its writer died between create and write.
      empty_waits=$(( ${empty_waits:-0} + 1 ))
      if [ "$empty_waits" -gt 10 ]; then rm -f "$LOCK"; fi
      sleep 1; continue
    fi
    if ! $WAIT; then
      echo "${RED}verify.sh: another verification gate is running in this worktree: pid ${pid:-unknown}, started ${started:-at an unknown time} ($LOCK); wait for it to finish, or pass --wait${RESET}"
      exit 2
    fi
    sleep 1
  done
  trap 'rm -f "$LOCK"' EXIT
  export AGENTSMITH_VERIFY_LOCK="$LOCK"
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
