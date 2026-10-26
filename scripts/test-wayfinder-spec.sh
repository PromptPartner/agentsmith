#!/usr/bin/env bash
# Regression guard for the Wayfinder spec boundary: stable structure, explicit acceptance, and
# tracker consent. This is intentionally structural; prose alone cannot prevent decision and
# implementation tickets from collapsing back into one item.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL="$ROOT_DIR/skills/wayfinder/SKILL.md"
TEMPLATE="$ROOT_DIR/templates/wayfinder-spec.md"
CATALOG="$ROOT_DIR/skills/README.md"
RECOMMENDED="$ROOT_DIR/skills/RECOMMENDED.md"

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
has() { grep -qF "$2" "$1" 2>/dev/null; }

for f in "$SKILL" "$TEMPLATE"; do
  [ -s "$f" ] && ok "$(basename "$f"): exists" || bad "$(basename "$f"): missing or empty"
done

required_sections=(
  '## Destination'
  '## Non-goals'
  '## Decision map'
  '### Frontier'
  '### Blocked'
  '### Fog'
  '## Decision index'
  '## Explicit deferrals'
  '## Needs operator'
  '## Acceptance and evidence'
  '## Review resolution'
  '## Decision-ticket drafts'
  '## Implementation-ticket drafts'
)
for heading in "${required_sections[@]}"; do
  has "$TEMPLATE" "$heading" \
    && ok "template: carries $heading" \
    || bad "template: missing $heading"
done
previous=0; ordered=true
for heading in "${required_sections[@]}"; do
  line="$(grep -nF "$heading" "$TEMPLATE" 2>/dev/null | head -1 | cut -d: -f1)"
  if [ -z "$line" ] || [ "$line" -le "$previous" ]; then ordered=false; break; fi
  previous="$line"
done
$ordered \
  && ok 'template: sections preserve the decision-to-implementation sequence' \
  || bad 'template: required sections are out of order'

has "$TEMPLATE" 'status: draft' \
  && ok 'template: initial status is draft' \
  || bad 'template: draft status missing'
if [ "$(head -1 "$TEMPLATE")" = '---' ] && [ "$(grep -c '^---$' "$TEMPLATE")" -ge 2 ]; then
  ok 'template: controller-readable frontmatter is present'
else
  bad 'template: YAML-style frontmatter missing'
fi
for field in 'schema: 2' 'decision_ticket:' 'research:' 'route:' 'reviewer_receipt:' 'accepted_by:' 'accepted_at:'; do
  has "$TEMPLATE" "$field" \
    && ok "template: frontmatter carries $field" \
    || bad "template: frontmatter missing $field"
done
if grep -qE '^status:[[:space:]]*accepted[[:space:]]*$' "$TEMPLATE"; then
  bad 'template: pre-accepts an agent-produced spec'
else
  ok 'template: cannot start accepted'
fi

for phrase in \
  'Only an explicit operator' \
  'acceptance may change `status` to `accepted`' \
  'separately tracked implementation ticket' \
  'when writes are unauthorized' \
  'A connected or named tracker grants no write permission' \
  'Resolve one decision per session'; do
  has "$SKILL" "$phrase" \
    && ok "skill: guarded — $phrase" \
    || bad "skill: missing guard — $phrase"
done

# The pipeline guard: an accepted schema-2 spec must point at its research and reviewer receipt
# and record its route. Each fixture removes or breaks one field and must turn the check red.
GUARD="$ROOT_DIR/scripts/autonomous-run.py"
FIX="$(mktemp -d)"; trap 'rm -rf "$FIX"' EXIT
git -C "$FIX" init -q
mkdir -p "$FIX/docs/specs" "$FIX/docs/research/reviews"
printf '# Research\n' > "$FIX/docs/research/item.md"
printf 'ACCEPT\n' > "$FIX/docs/research/reviews/item-spec-review.md"
write_spec() { # $1 = status, then lines to drop or replace via sed expressions
  local status="$1"; shift
  printf '%s\n' '---' 'schema: 2' "status: $status" 'decision_ticket: DEC-1' \
    'research: docs/research/item.md' 'route: direct — one bug with a reproduction' \
    'reviewer_receipt: docs/research/reviews/item-spec-review.md' \
    'accepted_by: Test Operator' 'accepted_at: 2026-10-26' '---' '# Spec' > "$FIX/docs/specs/item.md"
  for expression in "$@"; do sed -i.bak "$expression" "$FIX/docs/specs/item.md"; rm -f "$FIX/docs/specs/item.md.bak"; done
}
check() { (cd "$FIX" && python3 "$GUARD" check-specs "$@" >"$FIX/out" 2>&1); echo $?; }
write_spec accepted
[ "$(check)" = 0 ] && ok 'guard: a complete accepted spec passes' || { bad 'guard: complete spec failed'; cat "$FIX/out"; }
for case in \
  'research is missing|/^research:/d' \
  'reviewer_receipt is missing|/^reviewer_receipt:/d' \
  'route must start with direct, grill or wayfinder|/^route:/d' \
  'research points at docs/research/gone.md, which does not exist|s#^research:.*#research: docs/research/gone.md#' \
  'reviewer_receipt points at docs/research/reviews/none.md, which does not exist|s#^reviewer_receipt:.*#reviewer_receipt: docs/research/reviews/none.md#' \
  'route needs a one-line reason|s#^route:.*#route: wayfinder#' \
  'route must start with direct, grill or wayfinder|s#^route:.*#route: <direct | grill | wayfinder> — <reason>#' \
  'research must be a repository-relative path|s#^research:.*#research: ../outside.md#' \
  "unsupported schema '3'|s#^schema: 2#schema: 3#"; do
  expected="${case%%|*}"; expression="${case#*|}"
  write_spec accepted "$expression"
  if [ "$(check)" = 1 ] && grep -qF "$expected" "$FIX/out"; then
    ok "guard: red when $expected"
  else
    bad "guard: stayed green or wrong reason for: $expected"; cat "$FIX/out"
  fi
done
write_spec draft '/^research:/d'
[ "$(check)" = 0 ] && ok 'guard: a draft is not checked in the repository scan' || bad 'guard: scan checked a draft'
[ "$(check docs/specs/item.md)" = 1 ] && ok 'guard: a named draft is checked, so a goal cannot finish early' || bad 'guard: named draft passed'
write_spec accepted '/^schema:/d' '/^research:/d' '/^route:/d' '/^reviewer_receipt:/d'
if [ "$(check)" = 0 ] && grep -q 'legacy spec' "$FIX/out"; then
  ok 'guard: a spec accepted before schema 2 passes and says it is legacy'
else bad 'guard: legacy spec failed or was not reported'; cat "$FIX/out"; fi

if has "$TEMPLATE" '## Decision-ticket drafts' && has "$TEMPLATE" '## Implementation-ticket drafts'; then
  ok 'template: decision and implementation tickets are separate artifacts'
else
  bad 'template: ticket phases collapsed together'
fi

# The pack count excludes example-skill, which is explicitly a starter scaffold.
bundled_count="$(find "$ROOT_DIR/skills" -mindepth 2 -maxdepth 2 -name SKILL.md ! -path '*/example-skill/*' | wc -l | tr -d ' ')"
if [ "$bundled_count" = 10 ]; then
  ok 'catalog: ten bundled non-example skills exist'
else
  bad "catalog: expected 10 bundled non-example skills, found $bundled_count"
fi
has "$CATALOG" 'Ten small skills ship in this repo.' \
  && ok 'catalog: documented count is ten' \
  || bad 'catalog: bundled count drifted'
has "$RECOMMENDED" '**wayfinder**' \
  && ok 'recommendations: Wayfinder is indexed' \
  || bad 'recommendations: Wayfinder missing from bundled index'
for skill_file in "$ROOT_DIR"/skills/*/SKILL.md; do
  skill_name="$(basename "$(dirname "$skill_file")")"
  [ "$skill_name" = example-skill ] && continue
  if has "$CATALOG" "**$skill_name**" && has "$RECOMMENDED" "**$skill_name**"; then
    ok "catalog: $skill_name appears in both indexes"
  else
    bad "catalog: $skill_name is missing from an index"
  fi
done
has "$RECOMMENDED" '<!-- MAP autonomous-loops | packs: - | skills: using-git-worktrees,verify,wayfinder,autonomous-run -->' \
  && ok 'recommendations: autonomous-loops map includes Wayfinder' \
  || bad 'recommendations: autonomous-loops machine-readable map drifted'

echo
printf 'wayfinder-spec: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
