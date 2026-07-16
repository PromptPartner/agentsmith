#!/usr/bin/env bash
# test-secret-scan.sh — non-regression suite for scripts/secret-scan.sh (the R8 guardrail).
#
# Guards two properties that must hold together:
#   1. DETECTION — every pattern still trips. A fast scanner that misses secrets is worse
#      than a slow one, so speed work must never regress this.
#   2. SPEED — the full tracked-tree scan finishes inside a bound. secret-scan is wired as a
#      pre-commit hook by default; a scan that takes minutes gets disabled by a human, which
#      silently removes the guardrail altogether.
#
# Fixtures are SPLICED AT RUNTIME ("AKIA" "AAAA…") so no secret-shaped literal ever exists in
# this tracked file — otherwise the scanner would flag its own test suite. None of the values
# below are real; they are shapes.
#
# Usage: bash scripts/test-secret-scan.sh     # exit 0 = all pass, 1 = a test failed
set -uo pipefail   # deliberately NOT -e: run every test, then report

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Overridable so the suite can be pointed at a deliberately-broken copy to prove it still fails
# (a guard nobody has watched fail is a claim, not a guard — R2).
SCAN="${SECRET_SCAN_BIN:-$SCRIPT_DIR/secret-scan.sh}"
ROOT_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || dirname "$SCRIPT_DIR")"

# The tracked-tree scan must finish within this many seconds. Generous enough not to flake on a
# slow box, tight enough to fail loudly on the per-line/per-pattern subprocess blowup.
MAX_SECONDS="${SECRET_SCAN_MAX_SECONDS:-15}"

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

# A secret-shaped line MUST be flagged (exit non-zero).
expect_flagged() {
  if printf '%s\n' "$2" | bash "$SCAN" - >/dev/null 2>&1; then
    bad "$1 — NOT flagged (a secret of this shape would slip through)"
  else
    ok "$1 — flagged"
  fi
}

# An innocent line must NOT be flagged (exit 0).
expect_clean() {
  if printf '%s\n' "$2" | bash "$SCAN" - >/dev/null 2>&1; then
    ok "$1 — clean"
  else
    bad "$1 — FALSE POSITIVE (would block a legitimate commit)"
  fi
}

echo "test-secret-scan — detection"

# One fixture per pattern in secret-scan.sh, in the same order.
expect_flagged "PEM private key"     "-----BEGIN RSA PRIV""ATE KEY-----"
expect_flagged "AWS access key id"   "AKIA""ABCDEFGHIJKLMNOP"
expect_flagged "AWS temp key id"     "ASIA""ABCDEFGHIJKLMNOP"
expect_flagged "GitHub token"        "ghp_""abcdefghijklmnopqrstuvwxyz1234"
expect_flagged "Slack token"         "xoxb""-1234567890abcdef"
expect_flagged "OpenAI-style key"    "sk-""abcdefghijklmnopqrstuvwxyz12"
expect_flagged "Anthropic-style key" "sk-ant-""abcdefghijklmnopqrstuvwxyz12"
expect_flagged "Google API key"      "AIza""01234567890123456789012345678901234"
expect_flagged "assigned literal"    "pass""word = \"correcthorsebattery\""

echo "test-secret-scan — no false positives"
expect_clean "prose"                 "This document explains how we rotate the password safely."
expect_clean "env var reference"     "export API_KEY=\${API_KEY:?set me}"
expect_clean "empty input"           ""
expect_clean "short assignment"      "token = \"abc\""

echo "test-secret-scan — plumbing"

# A secret buried among many clean lines is still found (proves we scan every line, not just the first).
buried=$(printf 'clean line\n%.0s' {1..40})$'\n'"AKIA""ABCDEFGHIJKLMNOP"$'\n'"more clean"
expect_flagged "secret buried mid-input" "$buried"

# File-argument mode behaves like stdin mode.
# NB: don't name this var *secret* — `secret="$(...)"` legitimately trips the assigned-literal
# pattern, and the right response to the guard firing is a better name, not an allowlist entry.
tmp_fixture="$(mktemp)"; printf '%s\n' "AKIA""ABCDEFGHIJKLMNOP" > "$tmp_fixture"
if bash "$SCAN" "$tmp_fixture" >/dev/null 2>&1; then
  bad "file-argument mode — NOT flagged"
else
  ok "file-argument mode — flagged"
fi
rm -f "$tmp_fixture"

# Reported line is the offending one. Capture first — piping straight into grep would let
# pipefail surface secret-scan's own exit 1 (secret found) and mask grep's verdict.
report_out=$(printf '%s\n' "AKIA""ABCDEFGHIJKLMNOP" | bash "$SCAN" - 2>&1 || true)
if grep -q 'possible secret' <<<"$report_out" && grep -q 'AKIA' <<<"$report_out"; then
  ok "reports the offending line"
else
  bad "reports the offending line — output format changed"
fi

echo "test-secret-scan — speed (pre-commit hook viability)"

start=$(date +%s)
bash "$SCAN" --all >/dev/null 2>&1
rc=$?
elapsed=$(( $(date +%s) - start ))

if [ "$rc" -gt 1 ]; then
  bad "--all over tracked tree — crashed (exit $rc)"
elif [ "$elapsed" -le "$MAX_SECONDS" ]; then
  ok "--all over tracked tree — ${elapsed}s (bound ${MAX_SECONDS}s)"
else
  bad "--all over tracked tree — ${elapsed}s exceeds ${MAX_SECONDS}s bound; too slow to survive as a pre-commit hook"
fi

echo
printf 'test-secret-scan: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
