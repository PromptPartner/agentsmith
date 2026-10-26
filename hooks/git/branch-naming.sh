#!/usr/bin/env bash
# Git guardrail (opt-in): branch name must match a pattern so PRs auto-link to the issue.
# Default matches e.g. "you/ai-123-slug" or "feature/JIRA-12-thing": <prefix>/<letters><digits>.
# Override with BRANCH_PATTERN (an extended regex). Base/protected branches are exempt.
# Bypass once with: git push --no-verify.
set -euo pipefail
# Firing log: one line per block in <repo>/.agentsmith/logs/hook-events.jsonl, so `agentsmith
# doctor` can name a guardrail that stopped firing. No commit text; a logging failure never blocks.
log_firing() {
  local dir log
  dir="$(git rev-parse --show-toplevel 2>/dev/null)/.agentsmith" || return 0
  [ -d "$dir" ] && [ ! -L "$dir/logs" ] || return 0
  mkdir -p "$dir/logs" 2>/dev/null || return 0
  [ -e "$dir/logs/.gitignore" ] || printf '*\n' >"$dir/logs/.gitignore" 2>/dev/null || true
  log="$dir/logs/hook-events.jsonl"
  [ ! -L "$log" ] || return 0
  printf '{"ts":"%s","hook":"%s","event":"%s","outcome":"blocked"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >>"$log" 2>/dev/null || return 0
  if [ "$(wc -c <"$log" 2>/dev/null || echo 0)" -gt 65536 ]; then
    { tail -c 32768 "$log" | sed '1d' >"$log.tmp" && mv -f "$log.tmp" "$log"; } 2>/dev/null || rm -f "$log.tmp"
  fi
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
