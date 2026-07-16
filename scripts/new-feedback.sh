#!/usr/bin/env bash
# Scaffold a harness post-incident under docs/feedback/ — the durable feedback
# record core/60 (the System-Evolution mindset) is built around. The point is NOT
# to fix one bug; it's to change the SYSTEM so the whole CLASS gets less likely.
# Structure follows the self-improving-harness loop:
#   evidence/symptom → failure mechanism → bounded edit → named surface → non-regression.
# Mirrors new-research.sh. Like research, feedback is never silently deleted (R9-style):
# if an entry is obsolete, move it to docs/feedback/_archive/ instead.
# Usage: ./scripts/new-feedback.sh "short symptom title"
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TITLE="${*:-}"
[ -z "$TITLE" ] && { echo "Usage: $0 \"short symptom title\""; exit 2; }
SLUG="$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/-/g;s/^-//;s/-$//')"
DIR="$ROOT_DIR/docs/feedback"
mkdir -p "$DIR"
# Number entries so each is referenceable ("feedback 0007") and the recurring
# review can say "everything since 0012". Numbers are never reused (R9: no deletes).
LAST="$(ls "$DIR"/[0-9][0-9][0-9][0-9]-*.md 2>/dev/null | sed -E 's#.*/([0-9]{4})-.*#\1#' | sort -n | tail -1 || true)"
NEXT="$(printf '%04d' "$(( 10#${LAST:-0} + 1 ))")"
DATE="$(date +%Y-%m-%d 2>/dev/null || echo 'YYYY-MM-DD')"
FILE="$DIR/$NEXT-$SLUG.md"
[ -e "$FILE" ] && { echo "Already exists: $FILE"; exit 0; }
cat > "$FILE" <<EOF
# Feedback $NEXT: $TITLE

> A harness post-incident. The point is not to fix THIS bug — it's to change the
> SYSTEM so this CLASS of mistake is less likely next time (core/60). Keep it small,
> specific, and traceable to the incident. Never delete this; archive if obsolete (R9).

- **Date:** $DATE
- **Status:** open   <!-- open | applied | wont-fix -->
- **Cost:** <!-- what did it actually cost? rework / a human had to catch it / a near-miss / a re-derived decision -->

## 1. Evidence / symptom
<!-- What was OBSERVED, concretely — the correction you got, the iteration loop, the
     human stepping in, the decision a past session already made and you redid. Quote it.
     No diagnosis here yet; just what happened. -->

## 2. Failure mechanism
<!-- WHY the system allowed it. Almost never "the model was dumb" — it's a missing rule,
     a vague instruction, an absent guardrail, a tool that wasn't reached for, or a context
     window full of noise. This is the root cause you're actually fixing. -->

## 3. Bounded edit
<!-- The SMALLEST change that prevents this whole class — one rule line, one quality gate,
     one hook, one template tweak. If the fix feels big, the mechanism above is probably
     mis-scoped: go back and narrow it. -->

## 4. Named surface
<!-- WHERE the edit lands — be exact, so it's reviewable and the recurring review knows what
     to re-check. One of:
       core/<file>.md (a specific rule)   ·   profiles/<name>.md (a quality gate)
       skills/<name>   ·   hooks/<name>.sh   ·   templates/<name>.md   ·   a verify.conf phase
     Prefer a DETERMINISTIC surface (hook / verify phase) over prose the model can skip (core/60). -->

## 5. Non-regression validation
<!-- How you confirmed the fix works AND how it STAYS fixed: the failing case that now passes,
     the hook that now blocks it, the verify phase that's now red on regression. Evidence, not
     intention. Until this section has a real check, Status stays 'open'. -->
EOF
echo "Created $FILE"
echo "Next: fill the five sections, land the bounded edit on its named surface, then flip Status to 'applied'."
