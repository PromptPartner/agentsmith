#!/usr/bin/env bash
# Compatibility launcher for the cross-platform Python scanner test suite.
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$ROOT_DIR/scripts/test-secret-scan.py" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$ROOT_DIR/scripts/test-secret-scan.py" "$@"
else
  echo "Agentsmith tests require Python 3.11+ (tried python3 and python)." >&2
  exit 127
fi
