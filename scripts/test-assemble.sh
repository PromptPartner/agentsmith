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
#   5. The assembly quietly outgrows its budget. Static context is paid every turn; past the
#      budget, rules stop competing for attention and start drowning each other (docs/04).
#      Gated per-profile (core + one profile) because that is the supported common case.
#      Stacked assemblies are measured and reported below, not gated; incident record is private.
#
# Runs OFFLINE and touches nothing global. Never uses --global: under --global, --assemble-only
# does NOT stop the write and --target is ignored, so a --global run here would overwrite the
# real ~/.claude/CLAUDE.md — the operator's actual rules (incident record is private).
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

# Root help must make the subcommand boundary discoverable, and install help owns the flags.
if bash "$SETUP" --help 2>/dev/null | grep -q -- 'install --help'; then
  ok "root help points to install --help"
else
  bad "root help does not point to install --help"
fi
install_help="$(bash "$SETUP" install --help 2>/dev/null)"
install_help_flat="$(printf '%s' "$install_help" | tr '\n' ' ' | tr -s ' ')"
if printf '%s' "$install_help" | grep -q -- '--profile'; then
  ok "install help renders and documents --profile"
else
  bad "install help does not expose the profile flags"
fi
if printf '%s' "$install_help_flat" | grep -q -- '--operator-role.*responsibility' \
   && printf '%s' "$install_help_flat" | grep -q -- '--operator-bio.*background'; then
  ok "install help keeps role and bio as the explanation-calibration controls"
else
  bad "install help does not explain operator role and bio"
fi
if printf '%s' "$install_help" | grep -q -- '--explanation-level'; then
  bad "install help exposes the rejected --explanation-level control"
else
  ok "install help does not add a separate explanation-level control"
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

  plain_english_missing=""
  plain_english_text="$(tr '\n' ' ' < "$f" | tr -s ' ')"
  for clause in \
    "plain international English by default" \
    "short sentences, common words, and one idea per sentence" \
    "Avoid idioms, slang, cultural references, and unexplained abbreviations" \
    "correct technical term" \
    "what state will change" \
    "English is usually more token-efficient" \
    "explicitly asks for another language"; do
    printf '%s' "$plain_english_text" | grep -qF "$clause" || plain_english_missing="$plain_english_missing [$clause]"
  done
  if [ -z "$plain_english_missing" ]; then
    ok "$name: plain international English rule assembles completely"
  else
    bad "$name: plain international English rule is incomplete —$plain_english_missing"
  fi

  # Budget gate. Prose in core/60 asked for lean static context and got drift instead; this is the
  # check that goes red rather than the reminder that gets skipped. --strict exits 1 over budget.
  measured="$(bash "$ROOT_DIR/scripts/lint-leanness.sh" --strict "$f" 2>&1)"; budget_rc=$?
  # Keep only the two measurement lines; the WARN prose and the temp path are noise here.
  summary="$(printf '%s' "$measured" | awk '/lines *:|tokens *:/{printf "%s  ", $0}' | tr -s ' ')"
  if [ "$budget_rc" -eq 0 ]; then
    ok "$name: within static-context budget — $summary"
  else
    bad "$name: OVER static-context budget — $summary(trim core/, or move it into a skill or docs/)"
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
    # Measured, not gated: stacking two large profiles already exceeds the budget, so gating here
    # would be red on arrival and train people to ignore this suite. Reported so it stays visible.
    printf '  \033[33m•\033[0m stacked budget (measured, not gated): %s\n' \
      "$(bash "$ROOT_DIR/scripts/lint-leanness.sh" "$out/CLAUDE.md" 2>&1 | awk '/lines|tokens/{printf "%s ", $0}' | tr -s ' ')"
  else
    bad "stacked profiles failed to assemble clean"
  fi
fi

# The repository's own AGENTS.md is a committed assembly (core + software-dev, default operator).
# Codex and anyone who clones the repo read it, so it must not drift from core/ and profiles/.
if [ -f "$ROOT_DIR/AGENTS.md" ]; then
  if ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import argparse, os, sys
from pathlib import Path
root = Path(os.environ["ROOT_DIR"])
sys.path.insert(0, str(root))
import agentsmith
ns = argparse.Namespace(operator_name=None, operator_role=None, operator_bio=None, tracker=None, tracker_writes=None)
expected = agentsmith.build_instructions(ns, ["software-dev"], True, {}).rstrip("\n")
actual = (root / "AGENTS.md").read_text(encoding="utf-8").rstrip("\n")
sys.exit(0 if actual == expected else 1)
PY
  then
    ok "root AGENTS.md matches core/ + profiles/software-dev.md"
  else
    bad "root AGENTS.md drifted from core/ + profiles/software-dev.md (regenerate it)"
  fi
fi

# profiles switch refuses an over-budget stack with constants in agentsmith.py; lint-leanness.sh
# gates assemblies with its own defaults. One budget, two places: keep them equal.
if ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import os, re, sys
from pathlib import Path
root = Path(os.environ["ROOT_DIR"])
sys.path.insert(0, str(root))
import agentsmith
lint = (root / "scripts" / "lint-leanness.sh").read_text(encoding="utf-8")
lines = int(re.search(r'LEANNESS_MAX_LINES:-(\d+)', lint).group(1))
tokens = int(re.search(r'LEANNESS_MAX_TOKENS:-(\d+)', lint).group(1))
print(f"lint={lines}/{tokens} cli={agentsmith.STATIC_CONTEXT_MAX_LINES}/{agentsmith.STATIC_CONTEXT_MAX_TOKENS}")
sys.exit(0 if (lines, tokens) == (agentsmith.STATIC_CONTEXT_MAX_LINES, agentsmith.STATIC_CONTEXT_MAX_TOKENS) else 1)
PY
then
  ok "profiles switch and lint-leanness use the same static-context budget"
else
  bad "STATIC_CONTEXT_MAX_* in agentsmith.py differ from lint-leanness.sh defaults"
fi

# Shipped rules are read inside the user's project, which has no docs/, scripts/, skills/ or
# templates/ from this repository (templates arrive as .harness/templates/). A rule that cites
# one of those files points the agent at nothing. Directories (trailing /) are locations the
# rules ask a project to keep, so they are allowed.
if ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import os, re, sys
from pathlib import Path
root = Path(os.environ["ROOT_DIR"])
offenders = []
for source in sorted([*(root / "core").glob("*.md"), *(root / "profiles").glob("*.md")]):
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        for cited in re.findall(r"`\.?/?((?:docs|scripts|skills|templates)/[^`\s]*[^/`\s])[^`]*`", line):
            # <placeholder> paths name a location the project keeps, not a shipped file.
            if re.search(r"\.[A-Za-z0-9]+$", cited) and "<" not in cited:
                offenders.append(f"{source.relative_to(root)}:{number}: {cited}")
for offender in offenders:
    print(offender)
sys.exit(1 if offenders else 0)
PY
then
  ok "core/ and profiles/ cite only files an installed project has"
else
  bad "core/ or profiles/ cite repository-only files (see list above)"
fi

# Installed runtimes have no core/ tree and report a fixed token figure; keep it honest.
if ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ["ROOT_DIR"])
import agentsmith
live, fallback = agentsmith.estimate_instruction_tokens(), agentsmith.INSTRUCTION_TOKENS_FALLBACK
print(f"live={live} fallback={fallback}")
sys.exit(0 if abs(fallback - live) <= live * 0.10 else 1)
PY
then
  ok "installed-runtime token fallback is within 10% of the live estimate"
else
  bad "INSTRUCTION_TOKENS_FALLBACK in agentsmith.py is stale (update it to the live estimate)"
fi

echo
printf 'assemble: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
