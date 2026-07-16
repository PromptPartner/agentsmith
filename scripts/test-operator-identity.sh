#!/usr/bin/env bash
# test-operator-identity.sh — non-regression suite for feedback 0003.
#
# The incident: `setup.sh --global` re-rendered ~/.claude/CLAUDE.md from scratch every run, so a
# re-run with no operator flags silently replaced a real name/role/tracker with "the project lead /
# owner / decision-maker". It landed twice — the second time on the person who had written the
# handoff warning about it, during a *measurement* rather than a change, which is exactly the
# moment suspicion is lowest. core/60 predicted the outcome: "prefer the deterministic fix over the
# reminder", "guardrails hold what prose forgets". A third warning would have been the same bug.
#
# The properties that must stay true for the fix to be real:
#   1. A RE-RUN PRESERVES IDENTITY — the headline. Re-running --global with no operator flags keeps
#      whatever is already in the managed block. This is the regression that caused the incident.
#   2. EXPLICIT FLAGS STILL WIN — or the fix has just made the fields un-changeable, trading a
#      data-loss bug for a data-frozen one.
#   3. A FRESH INSTALL STILL RENDERS — the sentinel defaults must resolve to real prose, not leak
#      "" or [TODO] into rules an agent has to follow.
#   4. THE UNSAFE-LOOKING FLAGS TELL THE TRUTH — --target is refused rather than silently ignored,
#      and --assemble-only admits it still writes. Those two flags are what a careful person
#      reaches for to make a --global run safe, and neither constrained it.
#
# Every --global case runs against a FAKE $HOME. That is the only safe way to exercise this path:
# under --global, CLAUDE.md IS the global file, and neither --assemble-only nor --target redirects
# it — $HOME is what decides. A suite that got this wrong would reproduce the incident on the
# machine running the tests.
#
# Usage: bash scripts/test-operator-identity.sh   # exit 0 = all pass, 1 = a test failed
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

# Fictional on purpose: a real name here would be a leak in a public repo (scripts/leak-gate.sh).
NAME="Ada Lovelace"; ROLE="Chief Engineer"; TRK="Jira"

# Run setup.sh --global with $HOME pointed at a throwaway dir. Never call setup.sh --global in this
# suite without going through here.
gsetup() {  # <fake-home> [extra args...]
  local home="$1"; shift
  HOME="$home" bash "$SETUP" --global --assemble-only "$@" >/dev/null 2>&1
}
gfile() { printf '%s/.claude/CLAUDE.md' "$1"; }

echo "test-operator-identity — a re-run must not blank the operator (feedback 0003)"

H="$WORK/h1"; mkdir -p "$H"
gsetup "$H" --operator-name "$NAME" --operator-role "$ROLE" --tracker "$TRK"
G="$(gfile "$H")"

if [ -f "$G" ] && grep -q "\*\*$NAME\*\* is the lead\. Role: \*\*$ROLE\*\*" "$G"; then
  ok "fresh --global renders the operator identity it was given"
else
  bad "fresh --global renders the operator identity it was given — nothing else below is meaningful"
fi

# THE INCIDENT, exactly: same command, minus the operator flags.
gsetup "$H"
if grep -q "\*\*$NAME\*\* is the lead\. Role: \*\*$ROLE\*\*" "$G"; then
  ok "re-run with no operator flags KEEPS name and role"
else
  bad "re-run with no operator flags BLANKED name/role — feedback 0003 has regressed"
fi
if grep -q "The team's record is \*\*$TRK\*\*" "$G"; then
  ok "re-run with no operator flags KEEPS the tracker"
else
  bad "re-run with no operator flags BLANKED the tracker — feedback 0003 has regressed"
fi

echo "test-operator-identity — but explicit flags still win"

gsetup "$H" --operator-name "Grace Hopper"
if grep -q '\*\*Grace Hopper\*\* is the lead' "$G"; then
  ok "an explicitly-passed --operator-name overrides what was recovered"
else
  bad "an explicitly-passed --operator-name did NOT take effect — the fields are now frozen"
fi
# The role was NOT passed on that run, so it must have been carried, not reset.
if grep -q "Role: \*\*$ROLE\*\*" "$G"; then
  ok "fields you did not pass are carried, not reset, when you change one"
else
  bad "changing one field reset the others — a partial re-run still loses data"
fi

echo "test-operator-identity — a fresh install still renders real prose"

H2="$WORK/h2"; mkdir -p "$H2"
gsetup "$H2"
G2="$(gfile "$H2")"
if grep -q '\*\*the project lead\*\* is the lead' "$G2"; then
  ok "no flags, no existing file — the generic default renders"
else
  bad "no flags, no existing file — the generic default did NOT render (sentinels leaked)"
fi
if grep -q '\[TODO: set ' "$G2"; then
  bad "fresh install leaked a [TODO] placeholder into the rules"
else
  ok "fresh install leaks no [TODO] placeholder"
fi
if grep -qE '\{\{[A-Z_]+\}\}' "$G2"; then
  bad "fresh install leaked an unrendered {{TOKEN}} into the rules"
else
  ok "fresh install leaks no unrendered {{TOKEN}}"
fi

echo "test-operator-identity — the unsafe-looking flags tell the truth"

# --target reads as "write over there, not to my real config". It never did. Refusing beats
# warning: the incident WAS someone passing it in good faith.
H3="$WORK/h3"; mkdir -p "$H3"
out="$(HOME="$H3" bash "$SETUP" --global --assemble-only --target "$WORK/elsewhere" 2>&1)"; rc=$?
if [ "$rc" -ne 0 ]; then
  ok "--global --target is refused (exit $rc), not silently ignored"
else
  bad "--global --target was accepted — the flag still implies a redirect it does not do"
fi
if [ -f "$(gfile "$H3")" ]; then
  bad "--global --target was refused but STILL wrote the global file"
else
  ok "--global --target wrote nothing before refusing"
fi
if grep -qi 'target' <<<"$out"; then
  ok "the refusal names --target as the problem"
else
  bad "the refusal does not say which flag was wrong"
fi

# --assemble-only reads as "touch nothing global". Under --global it writes the global file.
H4="$WORK/h4"; mkdir -p "$H4"
out2="$(HOME="$H4" bash "$SETUP" --global --assemble-only 2>&1)"
if grep -qi 'still WRITES' <<<"$out2"; then
  ok "--assemble-only --global says out loud that it still writes the global file"
else
  bad "--assemble-only --global does not admit it writes — the flag implies a safety it lacks"
fi

# --dry-run is the flag that really writes nothing. If it doesn't, there is no safe way to look.
H5="$WORK/h5"; mkdir -p "$H5"
HOME="$H5" bash "$SETUP" --global --dry-run >/dev/null 2>&1
if [ -f "$(gfile "$H5")" ]; then
  bad "--global --dry-run WROTE the global file — nothing is safe to run"
else
  ok "--global --dry-run writes nothing"
fi

echo "test-operator-identity — project mode has the same trap, and the same fix"

P="$WORK/proj"; mkdir -p "$P"
bash "$SETUP" --profile software-dev --assemble-only --target "$P" \
     --operator-name "$NAME" --operator-role "$ROLE" >/dev/null 2>&1
bash "$SETUP" --profile software-dev --assemble-only --target "$P" >/dev/null 2>&1
if grep -q "\*\*$NAME\*\* is the lead\. Role: \*\*$ROLE\*\*" "$P/CLAUDE.md"; then
  ok "re-running a project assemble keeps the operator identity"
else
  bad "re-running a project assemble BLANKED the operator identity"
fi

echo "test-operator-identity — setup.ps1 does the same thing, actually run"

# setup.ps1 is a hand-maintained port, so it drifts silently and only Windows users find out.
# Grepping it for function names would only prove someone typed the name, so run it for real.
#
# $HOME is READ-ONLY inside PowerShell — assigning it throws, and the run then goes to the
# operator's REAL ~/.claude. (Found the hard way: a --dry-run probe that "redirected" $HOME
# reported C:\Users\<me>\.claude and would have rewritten it for real without --dry-run.) A CHILD
# pwsh, however, takes $HOME from the environment it is spawned with — USERPROFILE on Windows,
# HOME elsewhere. Setting both is the only safe way to exercise --global here. Never call
# setup.ps1 --global in this suite without going through psetup().
if command -v pwsh >/dev/null 2>&1; then
  psetup() {  # <fake-home> [extra args...]
    local home="$1"; shift
    USERPROFILE="$home" HOME="$home" pwsh -NoProfile -File "$ROOT_DIR/setup.ps1" \
      --global --assemble-only "$@" >/dev/null 2>&1
  }

  PH="$WORK/psh"; mkdir -p "$PH"
  psetup "$PH" --operator-name "$NAME" --operator-role "$ROLE" --tracker "$TRK"
  PG="$(gfile "$PH")"

  # Guard the guard: if the redirect ever silently fails, the fake home stays empty and every
  # assertion below would "pass" while the real config took the writes.
  if [ -f "$PG" ]; then
    ok "setup.ps1 --global honours the redirected home (the real ~/.claude is untouched)"
  else
    bad "setup.ps1 --global wrote nothing to the fake home — redirect failed; treat the ps1 results below as meaningless"
  fi

  if [ -f "$PG" ] && grep -q "\*\*$NAME\*\* is the lead\. Role: \*\*$ROLE\*\*" "$PG"; then
    ok "setup.ps1: fresh --global renders the operator identity it was given"
  else
    bad "setup.ps1: fresh --global does not render the identity it was given"
  fi

  # THE INCIDENT, on the Windows port.
  psetup "$PH"
  if [ -f "$PG" ] && grep -q "\*\*$NAME\*\* is the lead\. Role: \*\*$ROLE\*\*" "$PG"; then
    ok "setup.ps1: re-run with no operator flags KEEPS name and role"
  else
    bad "setup.ps1: re-run with no operator flags BLANKED name/role — Windows still has 0003"
  fi
  if [ -f "$PG" ] && grep -q "The team's record is \*\*$TRK\*\*" "$PG"; then
    ok "setup.ps1: re-run with no operator flags KEEPS the tracker"
  else
    bad "setup.ps1: re-run with no operator flags BLANKED the tracker"
  fi

  PH2="$WORK/psh2"; mkdir -p "$PH2"
  USERPROFILE="$PH2" HOME="$PH2" pwsh -NoProfile -File "$ROOT_DIR/setup.ps1" \
    --global --assemble-only --target "$WORK/elsewhere2" >/dev/null 2>&1
  rc=$?
  if [ "$rc" -ne 0 ] && [ ! -f "$(gfile "$PH2")" ]; then
    ok "setup.ps1: --global --target is refused and writes nothing"
  else
    bad "setup.ps1: --global --target was accepted (rc=$rc) — the ports disagree"
  fi
else
  # Not a silent pass: say the coverage is missing rather than let a green run imply it ran.
  printf '  \033[33m—\033[0m %s\n' "SKIPPED: pwsh not installed, so setup.ps1 was never run. Install PowerShell 7+ to cover the Windows port."
fi

echo
printf 'test-operator-identity: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
