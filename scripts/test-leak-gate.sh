#!/usr/bin/env bash
# test-leak-gate.sh — non-regression suite for scripts/leak-gate.sh.
#
# Guards two properties that must hold together:
#   1. DETECTION — every check still trips. Three of the four checks (IP, email, home path)
#      match NOTHING in this repo today: they exist purely to fire the day someone pastes
#      their server or their home directory into a doc. A check that has never been watched
#      failing is a claim, not a guard (R2) — so each one gets a planted leak here.
#   2. NO FALSE POSITIVES — the placeholders this repo legitimately uses (127.0.0.1,
#      user@example.com, $HOME, "Your Name") stay clean. A gate that cries wolf on a loopback
#      address in a devops doc is a gate someone deletes, which removes it just as surely.
#
# Fixtures are SPLICED AT RUNTIME ('luk''as', '51.75.' '20.9') so no leak-shaped literal ever
# exists in this tracked file. leak-gate scans the whole shipped surface INCLUDING this suite
# and its own source, so an un-spliced fixture here would make the gate flag its own tests.
#
# Every case runs against a THROWAWAY git repo, never this one: the gate scans the tracked
# tree, so testing it in place would mean committing leaks to the real repo to watch it fire.
#
# Usage: bash scripts/test-leak-gate.sh     # exit 0 = all pass, 1 = a test failed
set -uo pipefail   # deliberately NOT -e: run every test, then report

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Overridable so the suite can be pointed at a deliberately-broken copy to prove it still fails
# (a guard nobody has watched fail is a claim, not a guard — R2).
GATE="${LEAK_GATE_BIN:-$SCRIPT_DIR/leak-gate.sh}"
ROOT_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || dirname "$SCRIPT_DIR")"

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

# One throwaway repo, reused: `git grep` reads the index, so `git add` is enough — no commit,
# and no re-init per case.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# mktemp hands back an msys path (/tmp/tmp.XXX) under git-bash, and this suite drives the scratch
# repo with native git-for-Windows (git -C "$TMP" ...). Native git can only reach that path if msys
# converts it first; when it doesn't — path-conversion disabled, or a cold /tmp mount right after a
# reboot — every `git -C "$TMP" ...` dies with "cannot change to '/tmp/...'". The setup calls below
# suppress stderr, so the scratch repo would then end up EMPTY, the gate would find nothing, and
# every "expect-flagged" case would silently pass the gate — surfacing as fake leak-gate logic
# failures (the infamous 18 passed / 16 failed) that say nothing about the guardrail. Normalise to a
# path native git resolves on any platform: cygpath on git-bash, a no-op fallback on Linux/macOS.
TMP="$(cygpath -m "$TMP" 2>/dev/null || printf '%s' "$TMP")"
git -C "$TMP" init -q
mkdir -p "$TMP/scripts"
cp "$GATE" "$TMP/scripts/leak-gate.sh"

# SANITY — the belt to that suspenders. Prove git can actually track AND grep a file in the scratch
# repo before running a single case, using the same `git -C "$TMP"` the cases rely on. If it can't
# (residual path issue, no git on PATH, read-only TEMP), the whole suite is meaningless: fail LOUD
# with the real diagnosis instead of 16 fake logic failures a reader would chase into leak-gate.sh.
# R2/core-60: a guard that reports an environment fault as a logic fault is not a guard.
printf 'PROBE_51_75_20_9\n' > "$TMP/.sanity-probe"
git -C "$TMP" add -A >/dev/null 2>&1
if ! git -C "$TMP" grep -q PROBE_51_75_20_9 -- .sanity-probe 2>/dev/null; then
  echo "FATAL: git cannot track/grep a file in the scratch repo at:" >&2
  echo "         $TMP" >&2
  echo "  This is an ENVIRONMENT problem (msys path conversion, git on PATH, or TEMP perms)," >&2
  echo "  NOT a leak-gate failure. On git-bash it is usually mktemp handing native git an msys" >&2
  echo "  /tmp path it cannot resolve. Fix the environment, then re-run — leave leak-gate.sh alone." >&2
  exit 2
fi
rm -f "$TMP/.sanity-probe"
git -C "$TMP" add -A >/dev/null 2>&1

# Run the gate over a scratch repo whose only content is $1. Echoes output; returns gate exit.
gate_on() {
  printf '%s\n' "$1" > "$TMP/fixture.md"
  git -C "$TMP" add -A >/dev/null 2>&1
  ( cd "$TMP" && bash scripts/leak-gate.sh 2>&1 )
}

expect_flagged() {
  if gate_on "$2" >/dev/null; then
    bad "$1 — NOT flagged (this would ship)"
  else
    ok "$1 — flagged"
  fi
}

expect_clean() {
  if gate_on "$2" >/dev/null; then
    ok "$1 — clean"
  else
    bad "$1 — FALSE POSITIVE (would block legitimate content)"
  fi
}

echo "test-leak-gate — detection (each check must actually fire)"

expect_flagged "operator's first name"  'run: --operator-name "Luk''as"'
expect_flagged "operator's surname"     'maintainer: Jane Hert''ig'
expect_flagged "name inside a branch example" 'name branches like "luk''as/ai-123-slug"'
expect_flagged "routable IPv4"          'ssh ubuntu@51.75.''20.9'
expect_flagged "real email address"     'mail ops''@acme-internal.io for access'
expect_flagged "Windows home path"      'config lives in C:\Users''\jdoe\.claude'
expect_flagged "Unix home path"         'config lives in /home/''jdoe/.claude'
expect_flagged "macOS home path"        'config lives in /Users/''jdoe/.claude'

echo "test-leak-gate — no false positives (legitimate placeholders stay clean)"

expect_clean "placeholder name"         'run: --operator-name "Your Name"'
expect_clean "placeholder branch"       'name branches like "you/ai-123-slug"'
expect_clean "loopback"                 'the server listens on 127.0.0.1:8080'
expect_clean "bind-all address"         'bind 0.0.0.0 to accept external traffic'
expect_clean "private LAN range"        'the box sits at 192.168.1.10 on the LAN'
expect_clean "private 10/8 range"       'internal gateway: 10.0.0.1'
expect_clean "RFC 5737 doc range"       'point DNS at 192.0.2.5 in this example'
expect_clean "example.com email"        'mail user@example.com to get access'
expect_clean "commit-trailer address"   'Co-Authored-By: Someone <noreply@example.org>'
expect_clean "home via \$HOME"          'config lives in $HOME/.claude/CLAUDE.md'
expect_clean "home via tilde"           'config lives in ~/.claude/CLAUDE.md'
expect_clean "generic /home/user path"  'config lives in /home/user/.claude'
expect_clean "prose with no specifics"  'The operator decides direction; you are the co-pilot.'
expect_clean "semver-ish four-part"     'toolchain pinned at version 4.8.1 for now'

echo "test-leak-gate — scope and plumbing"

# NO file is exempt. This project's own working records (.planning/, the numbered
# docs/feedback/ post-incidents) used to be tracked and used to be exempt, on the grounds that a
# record about a person may name them. They are untracked and gitignored now — kept on disk, never
# published (R9) — so the exemption is gone. A name turning up in a TRACKED file of that shape
# means someone force-added a private record past .gitignore, which is precisely when the gate
# should fire rather than stay quiet. Each path below is a place a name has actually tried to live.
# (README.md is deliberately absent here: the operator's name IS allowed in the README author
# section via .harness/leak-gate.allow — config, not a code exemption — and that scoped exception
# gets its own block below.)
scratch_file() {   # $1 = path under the scratch repo, $2 = content
  mkdir -p "$(dirname "$TMP/$1")"
  printf '%s\n' "$2" > "$TMP/$1"
  git -C "$TMP" add -A >/dev/null 2>&1
  ( cd "$TMP" && bash scripts/leak-gate.sh >/dev/null 2>&1 )
}

for rec in ".planning/NOTES.md" "docs/feedback/0007-an-incident.md" "docs/feedback/README.md" \
           "hooks/git/branch-naming.sh"; do
  if scratch_file "$rec" 'run: --operator-name "Luk''as"'; then
    bad "name in $rec NOT flagged — the identity check has an exemption it should not have"
  else
    ok "name in $rec is flagged — nothing tracked is exempt"
  fi
  rm -f "$TMP/$rec"
done
git -C "$TMP" add -A >/dev/null 2>&1

# The gate's own TERMS list must not match itself, or the gate is permanently red on its own
# source. The scratch repo tracks a copy of leak-gate.sh, so a clean run here proves it.
if ( cd "$TMP" && bash scripts/leak-gate.sh >/dev/null 2>&1 ); then
  ok "gate scans its own source without flagging its own TERMS list"
else
  bad "gate flags itself — TERMS must be written 'w[o]rd', not 'word'"
fi

# The finding must name the file and line, or it is not actionable.
report_out="$(gate_on 'run: --operator-name "Luk''as"' || true)"
if grep -q 'fixture.md:1:' <<<"$report_out" && grep -qi 'operator identity' <<<"$report_out"; then
  ok "reports file:line and the check that fired"
else
  bad "reports file:line and the check that fired — output format changed"
fi

# A leak buried among many clean lines is still found (proves every line is scanned).
buried="$(printf 'clean line\n%.0s' {1..40})"$'\n''ssh ubuntu@51.75.''20.9'$'\n''more clean'
expect_flagged "leak buried mid-file" "$buried"

# Arguments are a usage error (exit 2), not a silently-ignored typo.
gate_on 'nothing here' >/dev/null
( cd "$TMP" && bash scripts/leak-gate.sh --all >/dev/null 2>&1 )
if [ "$?" -eq 2 ]; then
  ok "rejects unexpected arguments with exit 2"
else
  bad "rejects unexpected arguments with exit 2 — a typo'd flag would look like a pass"
fi

echo "test-leak-gate — the README operator-credit exception (.harness/leak-gate.allow)"

# WHY: the maintainer chose to be named in the README author section (and only there). The gate
# ships .harness/leak-gate.allow to permit exactly that. These cases prove the exception is real
# yet tightly scoped: allowed in README, still caught everywhere else, and OFF by default — absent
# the allow file even README is caught, so it is opt-in config, not a hole in the gate's code.
# The name is spliced at runtime ('Luk''as Hert''ig') so no literal ever lives in this tracked file.
ALLOW_SRC="$ROOT_DIR/.harness/leak-gate.allow"
NAME='**Luk''as Hert''ig** leads the project.'

if [ ! -f "$ALLOW_SRC" ]; then
  bad "the allow file $ALLOW_SRC is missing — the README credit exception has no config to test"
else
  mkdir -p "$TMP/.harness"
  cp "$ALLOW_SRC" "$TMP/.harness/leak-gate.allow"

  # 1. name in README.md — clean WITH the allow file present
  if scratch_file "README.md" "$NAME"; then
    ok "operator name in README.md — allowed by .harness/leak-gate.allow"
  else
    bad "operator name in README.md — should be allowed by .harness/leak-gate.allow"
  fi
  rm -f "$TMP/README.md"

  # 2. same name OUTSIDE README — still flagged even with the allow file present
  if scratch_file "setup.sh" "echo '$NAME'"; then
    bad "operator name in setup.sh slipped through — the allow scope is too wide"
  else
    ok "operator name outside README — still flagged with the allow file present"
  fi
  rm -f "$TMP/setup.sh"

  # 3. remove the allow file — even README is caught again (the exception is opt-in, not baked in)
  rm -f "$TMP/.harness/leak-gate.allow"
  if scratch_file "README.md" "$NAME"; then
    bad "README name passed with NO allow file — the gate has a built-in exemption it must not have"
  else
    ok "operator name in README.md — flagged when the allow file is absent"
  fi
  rm -f "$TMP/README.md"
  rmdir "$TMP/.harness" 2>/dev/null || true
  git -C "$TMP" add -A >/dev/null 2>&1
fi

echo "test-leak-gate — the real repo"

# The property the whole gate exists to protect, asserted against the actual shipped surface.
if ( cd "$ROOT_DIR" && bash "$GATE" >/dev/null 2>&1 ); then
  ok "this repo's shipped surface is generic"
else
  bad "this repo's shipped surface leaks — run scripts/leak-gate.sh to see what"
fi

echo
printf 'test-leak-gate: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
