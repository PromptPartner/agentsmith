#!/usr/bin/env bash
# Compatibility launcher: consent behavior is implemented and tested in the Python runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/scripts/test-tracker-consent.py" "$@"
