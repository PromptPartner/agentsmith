#!/bin/sh
# Thin POSIX launcher for the shared Python runtime. No installer behavior lives here.
set -eu

AGENTSMITH_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  AGENTSMITH_PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  AGENTSMITH_PYTHON=python
else
  printf '%s\n' 'Agentsmith requires Python 3.11+.' >&2
  printf '%s\n' 'Install Python, then rerun this exact command. Tried: python3, python.' >&2
  exit 127
fi

exec "$AGENTSMITH_PYTHON" "$AGENTSMITH_DIR/agentsmith.py" "$@"
