#!/usr/bin/env bash
. "$(dirname "$0")/_fixture_git.sh"  # first: keeps every Git fixture out of an inherited repository
# Compatibility launcher: consent behavior is implemented and tested in the Python runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/scripts/test-tracker-consent.py" "$@"
