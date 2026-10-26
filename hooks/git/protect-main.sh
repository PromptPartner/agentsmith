#!/usr/bin/env bash
# Git guardrail: refuse to commit on a protected branch — branch first, then PR.
# Protected branches default to "main master"; override with PROTECTED_BRANCHES.
# Bypass a single commit with: git commit --no-verify  (use sparingly).
set -euo pipefail
# Firing log: append one line per block to <repo>/.agentsmith/logs/hook-events.jsonl, so
# `agentsmith doctor` can name a guardrail that stopped firing. A cloned repository controls these
# paths, so this only appends to a regular file it can see is not a link, never rotates (Python
# hooks do; here appends stop at 128 KiB) and never lets a logging failure change the exit code.
log_firing() {
  local root dir log size
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
  dir="$root/.agentsmith/logs"
  log="$dir/hook-events.jsonl"
  [ -d "$root/.agentsmith" ] && [ ! -L "$root/.agentsmith" ] || return 0
  if [ ! -e "$dir" ] && [ ! -L "$dir" ]; then
    mkdir "$dir" 2>/dev/null || return 0
    ( set -o noclobber; printf '*\n' >"$dir/.gitignore" ) 2>/dev/null || true
  fi
  [ -d "$dir" ] && [ ! -L "$dir" ] || return 0
  if [ -e "$log" ] || [ -L "$log" ]; then
    [ -f "$log" ] && [ ! -L "$log" ] || return 0
    size="$(wc -c <"$log" 2>/dev/null)" || return 0
    [ "${size:-0}" -lt 131072 ] || return 0
  fi
  # One short O_APPEND write per event keeps concurrent lines whole. The subshell ignores
  # SIGXFSZ, so a full disk only fails the write.
  ( trap '' XFSZ
    printf '{"ts":"%s","hook":"%s","event":"%s","outcome":"blocked"}\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >>"$log" ) 2>/dev/null || true
  return 0
}
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then exit 0; fi   # detached / unborn → nothing to protect
for b in ${PROTECTED_BRANCHES:-main master}; do
  if [ "$branch" = "$b" ]; then
    echo "✗ protect-main: you're on '$branch'. Branch first:  git switch -c <name>" >&2
    echo "  then commit there and open a PR. (bypass once: --no-verify · list: PROTECTED_BRANCHES)" >&2
    log_firing protect-main pre-commit
    exit 1
  fi
done
exit 0
