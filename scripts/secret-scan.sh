#!/usr/bin/env bash
# secret-scan.sh — compatibility launcher for the canonical Python secret scanner.
#
# Usage:
#   ./scripts/secret-scan.sh                 # scan staged diff (use as a pre-commit hook)
#   ./scripts/secret-scan.sh --all           # scan the whole working tree (tracked files)
#   ./scripts/secret-scan.sh <file> [file..] # scan specific files
#   echo "...text..." | ./scripts/secret-scan.sh -   # scan stdin
# Exit 0 = clean, 1 = likely secret found, 2 = usage/runtime error. Tune with
# .harness/secret-scan.allow; one Python regular expression per line.
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$ROOT_DIR/agentsmith.py" secret-scan "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$ROOT_DIR/agentsmith.py" secret-scan "$@"
else
  echo "Agentsmith requires Python 3.11+ (tried python3 and python)." >&2
  exit 127
fi
