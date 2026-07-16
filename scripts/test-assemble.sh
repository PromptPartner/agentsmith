#!/usr/bin/env bash
# test-assemble.sh — every profile must assemble into rules a human can actually follow.
#
# The harness's whole output is an assembled CLAUDE.md. If assembly breaks, the agent doesn't
# crash — it quietly follows *wrong or half-rendered rules*, which is worse. The failures this
# catches, all of which have happened or nearly happened in this repo:
#   1. A profile stops assembling at all (renamed/moved file, bad glob).
#   2. An unrendered {{PLACEHOLDER}} reaches the agent — it improvises around the gap.
#   3. A [TODO: set X] reaches the agent — a rule that reads as an unfilled blank is not a rule.
#   4. --help stops rendering, so nobody can discover the flags.
#
# Runs OFFLINE and touches nothing global. Never uses --global: under --global, --assemble-only
# does NOT stop the write and --target is ignored, so a --global run here would overwrite the
# real ~/.claude/CLAUDE.md — the operator's actual rules (see docs/feedback/0003).
#
# Usage: bash scripts/test-assemble.sh    # exit 0 = all pass, 1 = a test failed
set -uo pipefail   # deliberately NOT -e: run every test, then report

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SETUP="${SETUP_BIN:-$ROOT_DIR/setup.sh}"

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --help must render: it is the only discovery surface for the flags.
if bash "$SETUP" --help 2>/dev/null | grep -q -- '--profile'; then
  ok "--help renders and documents --profile"
else
  bad "--help does not render (nobody can discover the flags)"
fi

# Every profile on disk must assemble. Globbing the directory rather than hardcoding a list means
# a newly added profile is covered automatically instead of being silently untested.
shopt -s nullglob
profiles=("$ROOT_DIR"/profiles/*.md)
if [ ${#profiles[@]} -eq 0 ]; then
  bad "no profiles found in profiles/ (glob broken?)"
fi

for p in "${profiles[@]}"; do
  name="$(basename "$p" .md)"
  out="$WORK/$name"
  mkdir -p "$out"
  if ! bash "$SETUP" --profile "$name" --assemble-only --target "$out" \
        --operator-name "Test" --tracker "Linear" >/dev/null 2>&1; then
    bad "$name: assembly failed outright"
    continue
  fi
  f="$out/CLAUDE.md"
  if [ ! -s "$f" ]; then
    bad "$name: produced no CLAUDE.md"
    continue
  fi

  errs=""
  # An unrendered token means the agent reads a literal "{{TRACKER}}" as if it were the rule.
  # Never acceptable, in any profile.
  leaked="$(grep -oE '\{\{[A-Z_]+\}\}' "$f" 2>/dev/null | sort -u | tr '\n' ' ')"
  [ -n "$leaked" ] && errs="$errs unrendered:[$leaked]"
  # [TODO: set X] means "the assembler had no value for X". Two very different cases:
  #   - X is flag-driven (below) → setup COULD have filled it and didn't. That's a bug: the agent
  #     gets a blank where a rule should be. This is the regression that would fire if a
  #     placeholder were renamed in core/ but not in fill_placeholders().
  #   - X has no flag (BRAND_PALETTE, BRAND_FONT) → the TODO IS the product. It's the documented
  #     handoff to the human (INSTALL.md's placeholder table; setup's own "resolve any [TODO]"
  #     next-step). Flagging it would make this suite red by design and train people to ignore it.
  for tok in OPERATOR_NAME OPERATOR_ROLE OPERATOR_BIO TRACKER TRACKER_POLICY; do
    grep -qF "[TODO: set $tok]" "$f" 2>/dev/null && errs="$errs unfilled-flag-token:[$tok]"
  done

  if [ -n "$errs" ]; then
    bad "$name: assembled with leaks —$errs"
  else
    ok "$name: assembles clean (no unrendered tokens, no TODO blanks)"
  fi
done

# Stacking is a documented feature (a work-type profile + autonomous-loops). If it only worked for
# single profiles, the docs would be lying.
if [ -f "$ROOT_DIR/profiles/software-dev.md" ] && [ -f "$ROOT_DIR/profiles/autonomous-loops.md" ]; then
  out="$WORK/stacked"; mkdir -p "$out"
  if bash "$SETUP" --profile software-dev,autonomous-loops --assemble-only --target "$out" \
        --operator-name "Test" --tracker "Linear" >/dev/null 2>&1 \
     && [ -s "$out/CLAUDE.md" ] \
     && ! grep -qE '\{\{[A-Z_]+\}\}' "$out/CLAUDE.md"; then
    ok "stacked profiles (software-dev,autonomous-loops) assemble clean"
  else
    bad "stacked profiles failed to assemble clean"
  fi
fi

echo
printf 'assemble: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
