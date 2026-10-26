#!/usr/bin/env bash
# Git guardrail (opt-in): branch name must match a pattern so PRs auto-link to the issue.
# Default matches e.g. "you/ai-123-slug" or "feature/JIRA-12-thing": <prefix>/<letters><digits>.
# Override with BRANCH_PATTERN (an extended regex). Base/protected branches are exempt.
# Bypass once with: git push --no-verify.
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
if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then exit 0; fi
for b in ${PROTECTED_BRANCHES:-main master} develop staging; do
  [ "$branch" = "$b" ] && exit 0
done
pattern="${BRANCH_PATTERN:-^[a-z0-9._-]+/[a-zA-Z]+-?[0-9]+}"
if printf '%s' "$branch" | grep -Eq "$pattern"; then exit 0; fi
echo "✗ branch-naming: '$branch' doesn't match  $pattern" >&2
echo "  name branches like 'you/ai-123-slug' so the PR auto-links the issue." >&2
echo "  (bypass once: --no-verify · change the rule: BRANCH_PATTERN)" >&2
log_firing branch-naming pre-push
exit 1
