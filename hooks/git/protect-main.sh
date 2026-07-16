#!/usr/bin/env bash
# Git guardrail: refuse to commit on a protected branch — branch first, then PR.
# Protected branches default to "main master"; override with PROTECTED_BRANCHES.
# Bypass a single commit with: git commit --no-verify  (use sparingly).
set -euo pipefail
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then exit 0; fi   # detached / unborn → nothing to protect
for b in ${PROTECTED_BRANCHES:-main master}; do
  if [ "$branch" = "$b" ]; then
    echo "✗ protect-main: you're on '$branch'. Branch first:  git switch -c <name>" >&2
    echo "  then commit there and open a PR. (bypass once: --no-verify · list: PROTECTED_BRANCHES)" >&2
    exit 1
  fi
done
exit 0
