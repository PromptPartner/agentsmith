#!/usr/bin/env bash
# Git guardrail: refuse to commit on a protected branch — branch first, then PR.
# Protected branches default to "main master"; override with PROTECTED_BRANCHES.
# Bypass a single commit with: git commit --no-verify  (use sparingly).
set -euo pipefail
# Firing log: one line per block in <repo>/.agentsmith/hook-events.jsonl, so `agentsmith doctor`
# can name a guardrail that stopped firing. No commit text; a logging failure never blocks.
log_firing() {
  local dir log
  dir="$(git rev-parse --show-toplevel 2>/dev/null)/.agentsmith" || return 0
  [ -d "$dir" ] && [ ! -L "$dir/hook-events.jsonl" ] || return 0
  log="$dir/hook-events.jsonl"
  printf '{"ts":"%s","hook":"%s","event":"%s","outcome":"blocked"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >>"$log" 2>/dev/null || return 0
  if [ "$(wc -c <"$log" 2>/dev/null || echo 0)" -gt 65536 ]; then
    { tail -c 32768 "$log" | sed '1d' >"$log.tmp" && mv -f "$log.tmp" "$log"; } 2>/dev/null || rm -f "$log.tmp"
  fi
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
