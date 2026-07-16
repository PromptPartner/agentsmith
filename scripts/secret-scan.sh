#!/usr/bin/env bash
# secret-scan.sh — deterministic guardrail for Rule 8 (no live secrets in tracked files).
# Scans ADDED lines (staged diff by default) for GENERIC secret patterns. Contains NO real
# secrets and no project-specific values — it looks for shapes, not known strings.
#
# Usage:
#   ./scripts/secret-scan.sh                 # scan staged diff (use as a pre-commit hook)
#   ./scripts/secret-scan.sh --all           # scan the whole working tree (tracked files)
#   ./scripts/secret-scan.sh <file> [file..] # scan specific files
#   echo "...text..." | ./scripts/secret-scan.sh -   # scan stdin
# Exit 0 = clean, 1 = likely secret found, 2 = usage error.
#
# Tune with an optional .harness/secret-scan.allow file: one extended-regex per line; any
# matching line is ignored (use for known test fixtures — NEVER to silence a real secret).
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ALLOW="$ROOT_DIR/.harness/secret-scan.allow"

# Generic high-signal secret patterns (shapes, not values).
PATTERNS=(
  'BEGIN [A-Z ]*PRIVATE KEY'                            # PEM private keys (RSA/OPENSSH/EC/bare/ENCRYPTED)
  'AKIA[0-9A-Z]{16}'                                    # AWS access key id
  'ASIA[0-9A-Z]{16}'                                    # AWS temp key id
  'gh[pousr]_[A-Za-z0-9]{20,}'                          # GitHub tokens
  'xox[baprs]-[A-Za-z0-9-]{10,}'                        # Slack tokens
  'sk-[A-Za-z0-9]{20,}'                                 # OpenAI-style keys
  'sk-ant-[A-Za-z0-9_-]{20,}'                           # Anthropic-style keys
  'AIza[0-9A-Za-z_-]{35}'                               # Google API key
  '(password|passwd|pwd|secret|token|api[_-]?key)["'"'"' ]*[:=][[:space:]]*["'"'"'][^"'"'"' ]{8,}'  # assigned secret literal
)

# Patterns go to a temp file so the whole scan is ONE grep pass (-f ORs every line of the file).
# Matching per-line in a shell loop costs a subprocess per line per pattern — imperceptible on
# Linux (~1ms spawns), minutes on Windows/Git Bash (~30ms). This script runs as a pre-commit
# hook, and a hook slow enough to be disabled is a guardrail that isn't there (R8).
PATTERN_FILE="$(mktemp)"
trap 'rm -f "$PATTERN_FILE"' EXIT
printf '%s\n' "${PATTERNS[@]}" > "$PATTERN_FILE"

input_lines() {
  if [ "${1:-}" = "--all" ]; then
    # -n 64 batches files per shell instead of -I{} spawning one shell PER FILE. The trailing
    # newline keeps a file that lacks one from welding its last line onto the next file's first.
    git -C "$ROOT_DIR" ls-files -z \
      | xargs -0 -n 64 sh -c 'for f in "$@"; do cat -- "$f"; printf "\n"; done' _ 2>/dev/null
  elif [ "${1:-}" = "-" ]; then
    cat
  elif [ $# -gt 0 ]; then
    cat "$@"
  else
    # staged diff: only ADDED lines (strip the leading +). The `|| true` keeps an empty or
    # deletion-only staged diff from tripping `set -o pipefail` (grep exits 1 on no match),
    # which previously produced a false BLOCKED when there was nothing to scan.
    { git -C "$ROOT_DIR" diff --cached --no-color -U0 2>/dev/null | grep -E '^\+' | grep -Ev '^\+\+\+' | sed 's/^+//'; } || true
  fi
}

# Drop allowlisted lines. Skipped entirely when the allowlist is absent or empty, so an empty
# file can't turn into "match nothing / invert / drop everything" on a stricter grep.
allow_filter() {
  if [ -s "$ALLOW" ]; then grep -Evf "$ALLOW"; else cat; fi
}

scan() {
  local hits line
  # Blank lines out, allowlisted lines out, then every pattern matched in a single pass.
  # `|| true` absorbs grep's exit-1-on-no-match, which pipefail would otherwise treat as failure.
  hits="$(grep -Ev '^[[:space:]]*$' | allow_filter | grep -E -f "$PATTERN_FILE" || true)"
  [ -n "$hits" ] || return 0
  while IFS= read -r line; do
    echo "  ✗ possible secret: $(echo "$line" | cut -c1-100)"
  done <<<"$hits"
  return 1
}

if input_lines "$@" | scan; then
  echo "secret-scan: clean."
  exit 0
else
  echo
  echo "secret-scan: BLOCKED — a line looks like a live secret (Rule 8)."
  echo "Move it to env/secret-manager, or (only for a genuine test fixture) add a regex to .harness/secret-scan.allow."
  exit 1
fi
