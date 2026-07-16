#!/usr/bin/env bash
# Git guardrail: commit subject must follow Conventional Commits — "type(scope): why".
# type ∈ feat fix docs style refactor perf test build ci chore revert (override via CC_TYPES).
# Merge / Revert / fixup! / squash! messages pass through. Bypass once: git commit --no-verify.
set -euo pipefail
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
exit 1
