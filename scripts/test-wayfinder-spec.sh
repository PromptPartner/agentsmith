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
  '## Acceptance and evidence'
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
for field in 'decision_ticket:' 'accepted_by:' 'accepted_at:'; do
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

if has "$TEMPLATE" '## Decision-ticket drafts' && has "$TEMPLATE" '## Implementation-ticket drafts'; then
  ok 'template: decision and implementation tickets are separate artifacts'
else
  bad 'template: ticket phases collapsed together'
fi

# The pack count excludes example-skill, which is explicitly a starter scaffold.
bundled_count="$(find "$ROOT_DIR/skills" -mindepth 2 -maxdepth 2 -name SKILL.md ! -path '*/example-skill/*' | wc -l | tr -d ' ')"
if [ "$bundled_count" = 9 ]; then
  ok 'catalog: nine bundled non-example skills exist'
else
  bad "catalog: expected 9 bundled non-example skills, found $bundled_count"
fi
has "$CATALOG" 'Nine small skills ship in this repo.' \
  && ok 'catalog: documented count is nine' \
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
