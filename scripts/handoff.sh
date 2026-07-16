#!/usr/bin/env bash
# Scaffold a session handoff note from templates/handoff-memory.md and pre-fill
# the git facts, so the memory-first handoff protocol (core/50) is one command.
# Usage: ./scripts/handoff.sh [item-id]
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ITEM="${1:-UNTRACKED}"
DIR="$ROOT_DIR/.harness/handoffs"
mkdir -p "$DIR"
STAMP="$(date +%Y%m%d-%H%M 2>/dev/null || echo session)"
FILE="$DIR/handoff-$STAMP.md"
BRANCH="$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'n/a')"
HEAD="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo 'n/a')"
DIRTY="$(git -C "$ROOT_DIR" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"

cat > "$FILE" <<EOF
# Handoff — $ITEM — $STAMP

**Branch:** $BRANCH   **HEAD:** $HEAD   **Uncommitted files:** $DIRTY
$( [ "$DIRTY" != "0" ] && echo '> ⚠ Tree is dirty — commit or stash BEFORE handing off (core/50 step 1).' )

## What shipped this session

## What is still pending

## Deviations from the plan / decisions made (don't re-litigate)

## Exact next step

## Gotchas a fresh session would otherwise re-derive

---
## Kickoff prompt for after reset
\`\`\`
Resume $ITEM on branch $BRANCH (HEAD $HEAD). <one-paragraph: what's done, the single next step,
key decisions already made, and the handoff note path: .harness/handoffs/handoff-$STAMP.md>
\`\`\`
EOF
echo "Created $FILE"
echo "Fill it in, then paste the kickoff block as your last message before /clear."
