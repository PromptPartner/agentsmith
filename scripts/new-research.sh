#!/usr/bin/env bash
# Scaffold a research/source note under docs/research/ (R9: research lives in the
# repo, never in disposable memory, and is never silently deleted).
# Usage: ./scripts/new-research.sh "topic name here"
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TITLE="${*:-}"
[ -z "$TITLE" ] && { echo "Usage: $0 \"topic name\""; exit 2; }
SLUG="$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/-/g;s/^-//;s/-$//')"
DIR="$ROOT_DIR/docs/research"
FILE="$DIR/$SLUG.md"
mkdir -p "$DIR"
if [ -e "$FILE" ]; then echo "Already exists: $FILE"; exit 0; fi
cat > "$FILE" <<EOF
# Research: $TITLE

> Source material and findings. NEVER delete this in a cleanup/rebase — if it's
> obsolete, move it to docs/research/_archive/ instead (R9).

## Question / scope

## Sources consulted
<!-- url or citation — what you actually read, dated -->

## Findings
<!-- claims, each traceable to a source above; mark single-sourced/uncertain items -->

## Open questions / what was NOT checked
EOF
echo "Created $FILE"
