#!/usr/bin/env bash
# Git guardrail: commit subject must follow Conventional Commits — "type(scope): why".
# type ∈ feat fix docs style refactor perf test build ci chore revert (override via CC_TYPES).
# Merge / Revert / fixup! / squash! messages pass through. Bypass once: git commit --no-verify.
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
msg_file="${1:?usage: conventional-commit.sh <commit-msg-file>}"
[ -f "$msg_file" ] || exit 0

# First non-comment, non-blank line = the subject.
subject="$(grep -vE '^[[:space:]]*#' "$msg_file" | grep -vE '^[[:space:]]*$' | head -1 || true)"
[ -z "$subject" ] && exit 0   # empty message — let git's own abort handle it

case "$subject" in
  "Merge "*|"Revert "*|"fixup! "*|"squash! "*|"amend! "*) exit 0 ;;
esac

types="${CC_TYPES:-feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert}"
if printf '%s' "$subject" | grep -Eq "^(${types})(\([a-z0-9 ._/-]+\))?!?: .+"; then
  exit 0
fi

echo "✗ conventional-commit: subject must be 'type(scope): why'." >&2
echo "  type ∈ ${types//|/ }" >&2
echo "  got : $subject" >&2
echo "  e.g.: feat(setup): add --with-mcp picker     (bypass once: --no-verify)" >&2
log_firing conventional-commit commit-msg
exit 1
