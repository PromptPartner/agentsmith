#!/usr/bin/env bash
# test-git-hooks.sh — non-regression suite for scripts/install-git-hooks.sh.
#
# The guard scripts the generated hooks call (scripts/secret-scan.sh, hooks/git/*.sh,
# scripts/verify.sh) are tracked at mode 100644, and a ZIP download or core.fileMode=false
# checkout loses the bit anyway. A hook that only runs a guard when it is executable therefore
# lets every commit through with no message. This suite installs the hooks into a throwaway repo
# whose guards are present but NOT executable, and proves each hook still runs its guard.
#
# The guards here are stubs that record they ran and refuse, so the suite tests the hook wiring,
# not the scanner (scripts/test-secret-scan.py covers the scanner).
#
# Usage: bash scripts/test-git-hooks.sh     # exit 0 = all pass, 1 = a test failed
set -uo pipefail   # deliberately NOT -e: run every test, then report

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="$SCRIPT_DIR/install-git-hooks.sh"
# A test run from inside a Git hook inherits that hook's repository; never let it leak in here.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# new_repo <dir> — a repo with one commit on a feature branch and every guard as a
# non-executable stub that writes <name> to ran.log and exits 1.
new_repo() {
  local repo="$1" guard
  git init -q "$repo"
  git -C "$repo" config user.name "Hook Test"
  git -C "$repo" config user.email "user@example.com"
  git -C "$repo" config commit.gpgsign false
  git -C "$repo" commit -q --allow-empty -m "chore: baseline"
  git -C "$repo" checkout -q -b test/hooks
  mkdir -p "$repo/scripts" "$repo/hooks/git"
  for guard in scripts/secret-scan.sh hooks/git/protect-main.sh hooks/git/conventional-commit.sh \
               hooks/git/branch-naming.sh scripts/verify.sh; do
    printf '#!/usr/bin/env bash\necho %s >> "%s/ran.log"\nexit 1\n' "$guard" "$repo" > "$repo/$guard"
    chmod 644 "$repo/$guard"
  done
}

ran() { grep -qxF "$2" "$1/ran.log" 2>/dev/null; }
# run_hook <repo> <hook> [args] — Git runs hooks from the work tree root, and the hook finds its
# guards through `git rev-parse --show-toplevel`, so run it from there too.
run_hook() { local repo="$1" hook="$2"; shift 2; (cd "$repo" && bash ".git/hooks/$hook" "$@") >/dev/null 2>&1 </dev/null; }

echo "install-git-hooks: guards that are present but not executable still run"

R="$TMP/all"; new_repo "$R"
(cd "$R" && bash "$INSTALLER" --all >/dev/null)

run_hook "$R" pre-commit
rc=$?
if [ "$rc" -ne 0 ] && ran "$R" scripts/secret-scan.sh; then ok "pre-commit runs a non-executable secret-scan.sh and fails with it"
else bad "pre-commit skipped non-executable secret-scan.sh (exit $rc)"; fi

printf 'feat: x\n' > "$TMP/msg"
run_hook "$R" commit-msg "$TMP/msg"
rc=$?
if [ "$rc" -ne 0 ] && ran "$R" hooks/git/conventional-commit.sh; then ok "commit-msg runs a non-executable conventional-commit.sh"
else bad "commit-msg skipped non-executable conventional-commit.sh (exit $rc)"; fi

run_hook "$R" pre-push
rc=$?
if [ "$rc" -ne 0 ] && ran "$R" hooks/git/branch-naming.sh; then ok "pre-push runs a non-executable branch-naming.sh"
else bad "pre-push skipped non-executable branch-naming.sh (exit $rc)"; fi

# protect-main and tests-green sit behind a guard that fails first; isolate each one.
R2="$TMP/protect"; new_repo "$R2"
printf '#!/usr/bin/env bash\nexit 0\n' > "$R2/scripts/secret-scan.sh"; chmod 644 "$R2/scripts/secret-scan.sh"
(cd "$R2" && bash "$INSTALLER" --protect-main >/dev/null)
run_hook "$R2" pre-commit
rc=$?
if [ "$rc" -ne 0 ] && ran "$R2" hooks/git/protect-main.sh; then ok "pre-commit runs a non-executable protect-main.sh"
else bad "pre-commit skipped non-executable protect-main.sh (exit $rc)"; fi

R3="$TMP/verify"; new_repo "$R3"
(cd "$R3" && bash "$INSTALLER" --tests-green >/dev/null)
run_hook "$R3" pre-push
rc=$?
if [ "$rc" -ne 0 ] && ran "$R3" scripts/verify.sh; then ok "pre-push runs a non-executable verify.sh"
else bad "pre-push skipped non-executable verify.sh (exit $rc)"; fi

echo "install-git-hooks: a real commit is refused by a non-executable secret-scan guard"
R4="$TMP/commit"; new_repo "$R4"
(cd "$R4" && bash "$INSTALLER" --minimal >/dev/null)
echo staged > "$R4/file.txt"
git -C "$R4" add file.txt
if git -C "$R4" commit -q -m "feat: staged" >/dev/null 2>&1; then
  bad "git commit succeeded although the secret-scan guard refused it"
else
  ok "git commit is blocked by the secret-scan guard"
fi

echo "install-git-hooks: a missing guard still does not block"
R5="$TMP/missing"; new_repo "$R5"
rm -f "$R5/scripts/secret-scan.sh"
(cd "$R5" && bash "$INSTALLER" --minimal >/dev/null)
if run_hook "$R5" pre-commit; then ok "pre-commit passes when secret-scan.sh is absent"
else bad "pre-commit failed although secret-scan.sh is absent"; fi

echo
echo "install-git-hooks: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
