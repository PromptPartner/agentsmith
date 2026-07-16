#!/usr/bin/env bash
# test-tracker-consent.sh — non-regression suite for the consent rule (feedback 0002).
#
# The incident: the wizard asked WHERE the operator tracks work, and setup compiled that answer
# into R7 as a mandatory write directive ("File it in **Linear**"). An obedient agent then created
# issues and posted comments in a live workspace nobody had authorized it to touch.
#
# Prose alone can't hold this — the model can skip prose (core/60). These are the properties that
# must stay true for the fix to be real:
#   1. CONSENT IS NOT INFERRED — naming a tracker renders the ask-first policy, never a bare
#      write directive. This is the exact regression that caused the incident.
#   2. OPT-IN STILL WORKS — an operator who explicitly says "allowed" gets a harness that writes,
#      or the flag is theatre and they'll go back to editing rules by hand.
#   3. THE POLICY SURVIVES SELF-UPDATE — re-assembly recovers tracker + policy from a rendered
#      block. R7's wording is also recover_operator_fields()'s anchor; rewording R7 without
#      updating the anchor silently blanks the operator's tracker to [TODO].
#   4. UPGRADES FAIL CLOSED — a pre-consent CLAUDE.md must NOT carry its inferred writes forward.
#      Those writes were never granted; an upgrade that preserves them re-commits the incident.
#
# Usage: bash scripts/test-tracker-consent.sh   # exit 0 = all pass, 1 = a test failed
set -uo pipefail   # deliberately NOT -e: run every test, then report

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Overridable so the suite can be pointed at a deliberately-broken copy to prove it still fails
# (a guard nobody has watched fail is a claim, not a guard — R2).
SETUP="${SETUP_BIN:-$ROOT_DIR/setup.sh}"

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Assemble a CLAUDE.md into a throwaway dir. --assemble-only + an explicit --target: never --global,
# which would write the real ~/.claude/CLAUDE.md even under --assemble-only.
assemble() {  # <outdir> [extra setup args...]
  local out="$1"; shift
  mkdir -p "$out"
  bash "$SETUP" --profile software-dev --assemble-only --target "$out" \
       --operator-name "Test Operator" --tracker "Linear" "$@" >/dev/null 2>&1
}

has()    { grep -qF "$2" "$1" 2>/dev/null; }
report() { local d="$1" f="$2" n="$3"; if has "$f" "$n"; then bad "$d"; else ok "$d"; fi; }

# ── 1. Consent is not inferred: the default must be ask-first ──────────────────
D="$WORK/default"
if assemble "$D"; then
  F="$D/CLAUDE.md"
  has "$F" 'writes are NOT authorized' \
    && ok "default: renders the ask-first policy" \
    || bad "default: ask-first policy MISSING — naming a tracker is granting writes again"
  has "$F" 'writes are authorized' \
    && bad "default: renders the AUTHORIZED policy — consent is being inferred from --tracker" \
    || ok "default: does not render the authorized policy"
  has "$F" 'Linear' \
    && ok "default: the tracker name still reaches R7" \
    || bad "default: tracker name lost — R7 no longer names where the team tracks work"
  # The incident's literal shape. R7 must never again read as a bare, unconditional directive.
  report "default: no bare 'File it in **' write directive (the pre-consent wording)" "$F" 'File it in **'
  # Unrendered token = the rule reads '[TODO: set TRACKER_POLICY]' and the agent improvises.
  report "default: no unrendered {{TRACKER_POLICY}} token" "$F" '{{TRACKER_POLICY}}'
  report "default: no [TODO: set TRACKER_POLICY] leak"     "$F" '[TODO: set TRACKER_POLICY]'
  # The general rule — this is what covers bexio/Slack/Instantly, not just the tracker.
  has "$F" 'Availability is not authorization' \
    && ok "default: core/10 carries the general consent trigger" \
    || bad "default: 'Availability is not authorization' MISSING from the pause-list"
else
  bad "default: assembly failed outright"
fi

# ── 2. The explicit opt-in still works ────────────────────────────────────────
A="$WORK/allowed"
if assemble "$A" --tracker-writes allowed; then
  F="$A/CLAUDE.md"
  has "$F" 'writes are authorized' \
    && ok "allowed: renders the authorized policy" \
    || bad "allowed: --tracker-writes allowed did NOT authorize writes (flag is theatre)"
  has "$F" 'writes are NOT authorized' \
    && bad "allowed: still renders the ask-first policy — the opt-in is ignored" \
    || ok "allowed: does not render the ask-first policy"
else
  bad "allowed: assembly failed outright"
fi

# ── 3. A bogus value must be rejected, not silently treated as 'allowed' ───────
if bash "$SETUP" --profile software-dev --assemble-only --target "$WORK/bogus" \
        --tracker "Linear" --tracker-writes yes-please >/dev/null 2>&1; then
  bad "validation: --tracker-writes accepted a bogus value (typo → silent wrong policy)"
else
  ok "validation: --tracker-writes rejects a bogus value"
fi

# ── 4/5. Self-update recovery: unit-test recover_operator_fields() directly ───
# It's only reachable via self_update(), which does a live git fetch AND re-assembles
# ~/.claude/CLAUDE.md — the operator's real global file. A test suite must never go near that, so
# extract the function and drive it against fixtures instead. If extraction fails the test fails
# loudly, which is the point: this function's anchors are coupled to R7's wording in core/20.
extract_fn() {  # <name> -> echoes the function source out of setup.sh
  sed -n "/^$1() {/,/^}/p" "$SETUP"
}

recovery_probe() {  # <fixture-file> -> echoes "TRACKER|TRACKER_WRITES" as recovered
  (
    set +u
    warn() { :; }   # stub: the real one writes colourised output we don't want in test results
    OPERATOR_NAME=""; OPERATOR_ROLE=""; OPERATOR_BIO=""
    TRACKER="UNRECOVERED"; TRACKER_WRITES="UNRECOVERED"
    eval "$(extract_fn recover_operator_fields)"
    recover_operator_fields "$1" >/dev/null 2>&1
    printf '%s|%s' "$TRACKER" "$TRACKER_WRITES"
  )
}

if [ -z "$(extract_fn recover_operator_fields)" ]; then
  bad "recovery: could not extract recover_operator_fields() from setup.sh (renamed? update this test)"
else
  # 4. Current wording, writes authorized → both must survive a self-update.
  R="$WORK/reassemble"
  if assemble "$R" --tracker-writes allowed; then
    got="$(recovery_probe "$R/CLAUDE.md")"
    case "$got" in
      Linear\|allowed) ok "recovery: tracker + authorized policy both recovered from a rendered block";;
      UNRECOVERED\|*)  bad "recovery: tracker LOST ('$got') — R7's wording drifted from its anchor; --self-update would blank it to [TODO]";;
      Linear\|ask)     bad "recovery: policy LOST ('$got') — the operator's opt-in is silently revoked on --self-update";;
      *)               bad "recovery: unexpected result '$got' (want 'Linear|allowed')";;
    esac
  else
    bad "recovery: fixture assembly failed outright"
  fi

  # 5. Pre-consent wording → tracker still recovers, but writes must FAIL CLOSED to ask.
  # Those writes were inferred from a pointer, never granted; carrying them forward on upgrade
  # would silently re-commit the original incident across every existing install.
  M="$WORK/migrate"; mkdir -p "$M"
  cat > "$M/CLAUDE.md" <<'PRECONSENT'
**Test Operator** is the lead. Role: **Founder**.

They decide direction and accept the risk; you are the technical co-pilot.

When you explain anything:

**7. Track every defect.** File it in **Linear** — every bug or gap you find, even one you
fix immediately. Make agent work visible there (a note when work starts and when it lands).
PRECONSENT
  got="$(recovery_probe "$M/CLAUDE.md")"
  case "$got" in
    Linear\|ask)     ok "migrate: pre-consent block keeps its tracker and fails closed to ask-first";;
    Linear\|allowed) bad "migrate: upgrade GRANTED writes that were never authorized — fails OPEN";;
    UNRECOVERED\|*)  bad "migrate: tracker LOST ('$got') — upgrading a pre-consent install blanks it to [TODO]";;
    *)               bad "migrate: unexpected result '$got' (want 'Linear|ask')";;
  esac
fi

# ── 6. setup.sh and setup.ps1 must render the SAME policy ────────────────────
# The two policy sentences are duplicated across the bash and PowerShell installers by necessity
# (no shared runtime). Duplication drifts: edit one, forget the other, and Windows users get a
# different contract from everyone else — the config-drift failure mode. Both are also the
# recovery anchors, so a drifted sentence silently breaks --self-update on one platform only.
PS1="$ROOT_DIR/setup.ps1"
if [ ! -f "$PS1" ]; then
  bad "parity: setup.ps1 not found"
else
  # Pull the quoted payload out of each definition, tolerating the two languages' assignment syntax.
  sh_ask="$(sed -n 's/^TRACKER_POLICY_ASK="\(.*\)"$/\1/p'          "$SETUP" | head -1)"
  sh_alw="$(sed -n 's/^TRACKER_POLICY_ALLOWED="\(.*\)"$/\1/p'      "$SETUP" | head -1)"
  ps_ask="$(sed -n 's/^ *TrackerPolicyAsk *= *"\(.*\)"$/\1/p'      "$PS1"   | head -1)"
  ps_alw="$(sed -n 's/^ *TrackerPolicyAllowed *= *"\(.*\)"$/\1/p'  "$PS1"   | head -1)"
  for v in sh_ask sh_alw ps_ask ps_alw; do
    [ -n "${!v}" ] || bad "parity: could not extract \$$v (assignment reformatted? update this test)"
  done
  if [ -n "$sh_ask" ] && [ -n "$ps_ask" ]; then
    [ "$sh_ask" = "$ps_ask" ] \
      && ok "parity: ask-first policy identical in setup.sh and setup.ps1" \
      || bad "parity: ask-first policy DRIFTED between setup.sh and setup.ps1 (Windows users get different rules)"
  fi
  if [ -n "$sh_alw" ] && [ -n "$ps_alw" ]; then
    [ "$sh_alw" = "$ps_alw" ] \
      && ok "parity: authorized policy identical in setup.sh and setup.ps1" \
      || bad "parity: authorized policy DRIFTED between setup.sh and setup.ps1 (Windows users get different rules)"
  fi
  # Both installers must know the current AND the pre-consent anchor, or --self-update blanks the
  # tracker to [TODO] on whichever platform forgot.
  for f in "$SETUP" "$PS1"; do
    n="$(basename "$f")"
    grep -qF "The team's record is" "$f" && grep -qF 'File it in ' "$f" \
      && ok "parity: $n carries both the current and pre-consent tracker anchors" \
      || bad "parity: $n is missing a tracker recovery anchor — --self-update would blank the tracker there"
  done
fi

echo
printf 'tracker-consent: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
