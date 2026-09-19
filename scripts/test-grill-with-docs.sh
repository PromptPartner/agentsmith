#!/usr/bin/env bash
# Regression guard for the repository-grilling workflow: self-contained instructions, durable
# decisions, and an explicit single-session boundary with Wayfinder.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL="$ROOT_DIR/skills/grill-with-docs/SKILL.md"
CONTEXT_FORMAT="$ROOT_DIR/skills/grill-with-docs/CONTEXT-FORMAT.md"
ADR_FORMAT="$ROOT_DIR/skills/grill-with-docs/ADR-FORMAT.md"
CATALOG="$ROOT_DIR/skills/README.md"
RECOMMENDED="$ROOT_DIR/skills/RECOMMENDED.md"
BUILT_IN="$ROOT_DIR/docs/12-whats-built-in.md"
INFLUENCES="$ROOT_DIR/docs/18-influences.md"
WAYFINDER="$ROOT_DIR/skills/wayfinder/SKILL.md"

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
has() { grep -qF "$2" "$1" 2>/dev/null; }

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

for file in "$SKILL" "$CONTEXT_FORMAT" "$ADR_FORMAT"; do
  [ -s "$file" ] && ok "$(basename "$file"): exists" || bad "$(basename "$file"): missing or empty"
done

for phrase in \
  'compatibility:' \
  '[`CONTEXT-FORMAT.md`](CONTEXT-FORMAT.md)' \
  '[`ADR-FORMAT.md`](ADR-FORMAT.md)' \
  'Facts come from the repository; decisions come from the operator.' \
  'before the next question round' \
  'every settled decision' \
  'the frontier is empty' \
  'operator confirms' \
  '`wayfinder`'; do
  has "$SKILL" "$phrase" \
    && ok "skill: guarded — $phrase" \
    || bad "skill: missing guard — $phrase"
done

for phrase in \
  'hard to reverse' \
  'surprising without context' \
  'real trade-off'; do
  has "$ADR_FORMAT" "$phrase" \
    && ok "ADR gate: $phrase" \
    || bad "ADR gate missing: $phrase"
done

has "$CONTEXT_FORMAT" 'Define what it is' \
  && ok 'glossary: definitions stay conceptual' \
  || bad 'glossary: conceptual-definition guard missing'

for index in "$CATALOG" "$RECOMMENDED" "$BUILT_IN"; do
  has "$index" 'grill-with-docs' \
    && ok "$(basename "$index"): skill indexed" \
    || bad "$(basename "$index"): skill missing"
done

has "$RECOMMENDED" '<!-- MAP software-dev | packs: dev-workflow,stack-lsp,security | skills: grill-with-docs,' \
  && ok 'recommendations: software-dev workflow maps repository grilling' \
  || bad 'recommendations: software-dev map omits repository grilling'
has "$WAYFINDER" '`grill-with-docs`' \
  && ok 'Wayfinder: routes single-session ambiguity to repository grilling' \
  || bad 'Wayfinder: single-session route missing'
has "$INFLUENCES" 'grill-with-docs' \
  && has "$INFLUENCES" 'MIT' \
  && ok 'attribution: upstream adaptation recorded' \
  || bad 'attribution: upstream adaptation or license missing'

if python3 - "$ROOT_DIR" "$WORK_DIR" <<'PY' >/dev/null
from pathlib import Path
import sys

root = Path(sys.argv[1])
target = Path(sys.argv[2])
sys.path.insert(0, str(root))
import agentsmith

agentsmith.install_skills(target, ["claude"], force=False, dry_run=False)
PY
then
  install_ok=true
  for destination in .agents/skills .claude/skills; do
    for artifact in SKILL.md CONTEXT-FORMAT.md ADR-FORMAT.md; do
      [ -s "$WORK_DIR/$destination/grill-with-docs/$artifact" ] || install_ok=false
    done
  done
  $install_ok \
    && ok 'install: canonical and Claude adapter receive the skill and both references' \
    || bad 'install: a runtime skill surface is incomplete'
else
  bad 'install: skill installer failed'
fi

echo
printf 'grill-with-docs: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
