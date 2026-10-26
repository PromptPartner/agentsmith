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
  'resolve one decision per session with the operator' \
  'never answered by an agent: put it under "Needs operator"' \
  'It blocks only those; the rest of the map moves on.' \
  'When unsure, take the heavier route.' \
  'A list of bugs is a numbered checklist of `direct` items' \
  'The usual successor is `autonomous-run`' \
  'Accept: the operator only.'; do
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
# The schema line decides whether the fields are required, so it must not be dodged by YAML shape.
# Any schema key that is not exactly 2 refuses; only a spec with no schema key at all is legacy.
for case in \
  'research is missing|schema:\n  2' \
  "repeats the key 'schema'|schema: 2\nschema:" \
  "unsupported schema 'two'|schema: two" \
  "unsupported schema ''|schema:"; do
  expected="${case%%|*}"; schema_lines="${case#*|}"
  printf -- "---\n${schema_lines}\nstatus: accepted\ndecision_ticket: DEC-1\naccepted_by: Test Operator\naccepted_at: 2026-10-26\n---\n# Spec\n" > "$FIX/docs/specs/item.md"
  if [ "$(check)" = 1 ] && grep -qF "$expected" "$FIX/out"; then
    ok "guard: red for schema shape — $expected"
  else
    bad "guard: schema shape passed or wrong reason — $expected"; cat "$FIX/out"
  fi
done
write_spec accepted 's#^route:.*#route: >-#' '/^route:/a\
  direct — one bug with a reproduction'
[ "$(check)" = 0 ] && ok 'guard: a folded multi-line route is read' || { bad 'guard: folded route not read'; cat "$FIX/out"; }

write_spec draft '/^research:/d'
[ "$(check)" = 0 ] && ok 'guard: a draft is not checked in the repository scan' || bad 'guard: scan checked a draft'
[ "$(check docs/specs/item.md)" = 1 ] && ok 'guard: a named draft is checked, so a goal cannot finish early' || bad 'guard: named draft passed'
write_spec accepted '/^schema:/d' '/^research:/d' '/^route:/d' '/^reviewer_receipt:/d'
if [ "$(check)" = 0 ] && grep -q 'legacy spec' "$FIX/out"; then
  ok 'guard: a spec accepted before schema 2 passes and says it is legacy'
else bad 'guard: legacy spec failed or was not reported'; cat "$FIX/out"; fi

# The skill is what an installed project sees; the doc explains it. They must not drift apart.
PIPELINE_DOC="$ROOT_DIR/docs/28-development-pipeline.md"
for term in Goal Research Shape Route 'Spec review' Accept Implement Prove Land; do
  if grep -qF "**$term**" "$PIPELINE_DOC" && grep -qE "^[0-8]\. $term:" "$SKILL"; then
    ok "pipeline: stage $term is in the doc and the skill"
  else bad "pipeline: stage $term drifted between the doc and the skill"; fi
done
for route in direct grill wayfinder; do
  if grep -qF "| \`$route\` |" "$PIPELINE_DOC" && grep -qF -- "- \`$route\`:" "$SKILL"; then
    ok "pipeline: route $route is in the doc and the skill"
  else bad "pipeline: route $route drifted between the doc and the skill"; fi
done

# One goal text for Claude Code /goal and Codex goals: both cap a goal at 4,000 characters, so it
# points at the pipeline instead of restating it, and "done" is evidence printed in the chat.
GOAL="$ROOT_DIR/templates/goal.md"
goal_text="$(awk '/^```text$/{inside=1; next} /^```$/{inside=0} inside' "$GOAL" 2>/dev/null)"
goal_chars="$(printf '%s' "$goal_text" | python3 -c 'import sys; print(len(sys.stdin.read()))')"
if [ -n "$goal_text" ] && [ "$goal_chars" -lt 4000 ]; then
  ok "goal: one goal text of $goal_chars characters, under the 4,000 limit"
else bad "goal: goal text missing or $goal_chars characters"; fi
for phrase in \
  'the `wayfinder` skill' \
  'check-specs docs/specs/<slug>.md' \
  'printed both commands and their full output in this conversation' \
  'recorded under "Needs operator"' \
  'counts as done for this goal' \
  'Never set `status: accepted` yourself' \
  'Claude Code: stop after <turns> turns' \
  'Codex: this goal has a token budget of <tokens>'; do
  if printf '%s' "$goal_text" | grep -qF -- "$phrase"; then ok "goal: carries — $phrase"
  else bad "goal: missing — $phrase"; fi
done
if printf '%s' "$goal_text" | grep -qE 'Goal.*Research.*Shape.*Route.*Spec review.*Accept'; then
  ok 'goal: names the stage order without restating each stage'
else bad 'goal: stage order missing'; fi

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
