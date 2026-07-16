#!/usr/bin/env bash
# install-git-hooks.sh — wire the harness guardrails into git hooks.
#
# Guardrails (mix and match):
#   secret-scan      (ALWAYS · pre-commit)  no live secrets in a commit (Rule 8)
#   --protect-main   (pre-commit)           refuse commits on main/master; branch first
#   --conventional   (commit-msg)           message must be 'type(scope): why'
#   --branch-naming  (pre-push)             branch must match BRANCH_PATTERN (auto-links PRs)
#   --tests-green    (pre-push)             run scripts/verify.sh before push   (alias: --verify)
#   --all            protect-main + conventional + branch-naming + tests-green
#   --minimal        secret-scan only
# No flags = recommended set: secret-scan + protect-main + conventional.
# Re-runnable. Backs up any foreign hook it would overwrite. Bypass once: git commit/push --no-verify.
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Not a git repo — run inside one."; exit 2; }
HOOKS_DIR="$ROOT_DIR/.git/hooks"; mkdir -p "$HOOKS_DIR"

PROTECT_MAIN=false; CONVENTIONAL=false; BRANCH_NAMING=false; TESTS_GREEN=false; ANY_FLAG=false; MINIMAL=false
for a in "$@"; do
  case "$a" in
    --protect-main)    PROTECT_MAIN=true;  ANY_FLAG=true ;;
    --conventional)    CONVENTIONAL=true;  ANY_FLAG=true ;;
    --branch-naming)   BRANCH_NAMING=true; ANY_FLAG=true ;;
    --tests-green|--verify) TESTS_GREEN=true; ANY_FLAG=true ;;
    --all) PROTECT_MAIN=true; CONVENTIONAL=true; BRANCH_NAMING=true; TESTS_GREEN=true; ANY_FLAG=true ;;
    --minimal) MINIMAL=true; ANY_FLAG=true ;;
    --help|-h) awk 'NR==1{next} /^[^#]/{exit} {sub(/^# ?/,"");print}' "$0"; exit 0 ;;
    *) echo "unknown option: $a (try --help)"; exit 2 ;;
  esac
done
$ANY_FLAG || { PROTECT_MAIN=true; CONVENTIONAL=true; }          # default recommended set
$MINIMAL  && { PROTECT_MAIN=false; CONVENTIONAL=false; BRANCH_NAMING=false; TESTS_GREEN=false; }

write_hook() {  # <hookname> <body> — managed write w/ foreign-backup; empty body removes a stale managed hook
  local name="$1" body="$2" f="$HOOKS_DIR/$1" marker="agentsmith $1"
  # legacy pre-rebrand marker: still recognized as "ours" so old hooks migrate in place, never written
  local legacy_marker="universal-claude-harness $1"
  if [ -z "$body" ]; then
    if [ -f "$f" ] && grep -q -e "$marker" -e "$legacy_marker" "$f"; then
      rm -f "$f"; echo "  removed managed $name (not selected)"
    fi
    return 0   # bare 'return' would propagate the failed test above and kill the set -e script
  fi
  [ -f "$f" ] && ! grep -q -e "$marker" -e "$legacy_marker" "$f" && { cp "$f" "$f.bak.$$"; echo "  backed up foreign $name → $name.bak.$$"; }
  {
    echo "#!/usr/bin/env bash"
    echo "# $marker — regenerate via scripts/install-git-hooks.sh. Bypass once: --no-verify"
    echo "set -e"
    echo 'ROOT="$(git rev-parse --show-toplevel)"'
    printf '%s\n' "$body"
  } > "$f"
  chmod +x "$f"; echo "  installed $name"
}

pc='if [ -x "$ROOT/scripts/secret-scan.sh" ]; then "$ROOT/scripts/secret-scan.sh" || exit 1; fi'
$PROTECT_MAIN && pc+=$'\n''if [ -x "$ROOT/hooks/git/protect-main.sh" ]; then "$ROOT/hooks/git/protect-main.sh" || exit 1; fi'
write_hook pre-commit "$pc"

cm=''
$CONVENTIONAL && cm='if [ -x "$ROOT/hooks/git/conventional-commit.sh" ]; then "$ROOT/hooks/git/conventional-commit.sh" "$1" || exit 1; fi'
write_hook commit-msg "$cm"

pp=''
$BRANCH_NAMING && pp+='if [ -x "$ROOT/hooks/git/branch-naming.sh" ]; then "$ROOT/hooks/git/branch-naming.sh" || exit 1; fi'$'\n'
$TESTS_GREEN   && pp+='if [ -x "$ROOT/scripts/verify.sh" ]; then "$ROOT/scripts/verify.sh" || exit 1; fi'$'\n'
write_hook pre-push "$pp"

echo "Git guardrails installed in $HOOKS_DIR:"
echo "  pre-commit : secret-scan$($PROTECT_MAIN && echo ' + protect-main')"
$CONVENTIONAL && echo "  commit-msg : conventional-commit"
{ $BRANCH_NAMING || $TESTS_GREEN; } && echo "  pre-push   :$($BRANCH_NAMING && echo ' branch-naming')$($TESTS_GREEN && echo ' tests-green(verify.sh)')"
echo "  bypass a single commit/push with --no-verify (use sparingly)."
