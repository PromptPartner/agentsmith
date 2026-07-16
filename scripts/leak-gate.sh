#!/usr/bin/env bash
# leak-gate.sh — deterministic guardrail for "this harness stays generic".
#
# WHY: this harness is installed by other people and is headed for open source. Anything
# that identifies ONE operator or ONE environment — a personal name in --help, a server IP
# in a doc, a home directory in an example — is confusing noise for every other user at
# best, and a leak at worst. The roadmap carried this as a by-hand reminder ("run the leak gate
# before any zip/publish: no IPs/creds/hostnames/client-project specifics"). A check that runs
# only when someone remembers it is not a check — it had already silently missed the operator's
# own name in setup.sh/setup.ps1 --help and in the branch-naming hook, while the roadmap recorded
# it as "clean every session". This makes "keep it generic" verifiable instead of aspirational.
#
# Complements scripts/secret-scan.sh, which covers the "creds" half of that line by matching
# secret SHAPES. This covers the other half: identity and environment specifics.
#
# Usage:
#   ./scripts/leak-gate.sh          # scan the tracked tree
# Exit 0 = clean, 1 = leak found, 2 = usage error.
#
# Scope is EVERY tracked file, with no exemptions. This project's own working records — .planning/
# and its numbered docs/feedback/ post-incidents — used to be tracked and used to be exempt, on the
# grounds that a record about a person may name them. They are now untracked and gitignored (kept
# on disk, never published), so the exemption is gone and the rule is simply: nothing published by
# this repo names anybody. If such a file is ever force-added back, the gate fails on it, which is
# the intended answer rather than a special case.
#
# Tune with an optional .harness/leak-gate.allow file: one extended-regex per line; any
# matching finding is ignored. Use it for a genuine false positive — never to wave through
# a real leak.
#
# KNOWN GAP (deliberate, not an oversight): the roadmap line also says "hostnames". There is
# no generic hostname check here, because every URL in every doc contains a hostname and a
# denylist of internal ones would have to name them in a public repo to look for them — the
# check would leak the thing it protects. Hostnames are covered only where they show up as an
# IP, an email, or a credential shape. Same reason there is no client-name list: adding one
# here would publish it. If you need to scan for a name you cannot commit, add it to the
# untracked .harness/leak-gate.allow's sibling — i.e. grep for it by hand before that bundle
# ships, or extend TERMS in a local, unpushed edit.
set -euo pipefail

[ $# -eq 0 ] || { echo "usage: $0   (no arguments)" >&2; exit 2; }

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"
ALLOW="$ROOT_DIR/.harness/leak-gate.allow"

# No exemptions, for any check. The files that once needed one (this project's own records, which
# are ABOUT an operator and so name them) are no longer tracked at all — see .gitignore. Keeping an
# empty list rather than deleting the concept: `git grep` takes the pathspec either way, and an
# exemption is exactly the kind of thing that should have to be added deliberately and argued for.
SCOPE=()

# Identity terms that must never appear in the shipped surface. These are public-safe (this
# repo's author is already named throughout its git history and .planning/) — the point is not
# that the name is secret, it is that a stranger installing this should never read it.
#
# Each term wraps one letter in a character class so this list cannot match ITSELF: 'w[o]rd' is
# the regex for "word", while the literal text here is not that word. That is what lets the gate
# scan its own source instead of being excluded from it — an excluded file is a hole a real leak
# can sit in. If you add a term, keep the trick, and do not spell the plain word out in a comment
# either: this very block used to explain the trick by example and tripped the gate on itself.
# (Get it wrong and the gate flags this file by name on the next run — a loud failure, not a hole.)
TERMS='l[u]kas|hert[i]g'

fail=0

# Drop allowlisted findings. Skipped when the file is absent/empty so an empty allowlist
# cannot turn into "match nothing / invert / drop every finding".
allow_filter() {
  if [ -s "$ALLOW" ]; then grep -Evf "$ALLOW"; else cat; fi
}

# check <label> <extended-regex> <exempt-regex|""> <hint>
# Findings print as file:line:match, so <exempt-regex> can anchor on the match with $.
check() {
  local label="$1" ere="$2" exempt="$3" hint="$4" hits line
  # -I skips binaries; -o prints just the match so exemptions test the match, not the whole
  # line (a line holding both a safe and an unsafe value must still fail).
  # `|| true` absorbs grep's exit-1-on-no-match, which pipefail would treat as a hard error.
  hits="$(git grep -noIiE -- "$ere" -- . "${SCOPE[@]+"${SCOPE[@]}"}" 2>/dev/null || true)"
  [ -n "$hits" ] || return 0
  if [ -n "$exempt" ]; then
    hits="$(printf '%s\n' "$hits" | grep -Evi "$exempt" || true)"
    [ -n "$hits" ] || return 0
  fi
  hits="$(printf '%s\n' "$hits" | allow_filter || true)"
  [ -n "$hits" ] || return 0
  echo "  ✗ $label — $hint"
  while IFS= read -r line; do
    echo "      $line"
  done <<<"$hits"
  fail=1
}

# 1. The operator's identity. The evidenced failure: --operator-name "<author>" sat in the
#    --help of both setup scripts, so every open-source user read a stranger's name.
check "operator identity" \
      "\\b(${TERMS})\\b" \
      "" \
      "a specific person's name — use the repo's placeholder convention (\"Your Name\", \"You\", \"you/...\")"

# 2. Routable IPv4. Loopback/private/link-local/broadcast and the RFC 5737 documentation
#    ranges are legitimate in docs and examples, so only a real, routable address fails.
check "public IP address" \
      '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' \
      ':(0\.0\.0\.0|127\.[0-9.]+|10\.[0-9.]+|192\.168\.[0-9.]+|169\.254\.[0-9.]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9.]+|255\.255\.[0-9.]+|192\.0\.2\.[0-9]+|198\.51\.100\.[0-9]+|203\.0\.113\.[0-9]+)$' \
      "a routable IP pins this to one environment — use a private/documentation range (192.0.2.x)"

# 3. Real email addresses. example.com/.org/.net are the reserved documentation domains.
check "email address" \
      '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b' \
      ':(noreply@|[A-Za-z0-9._%+-]+@(example\.(com|org|net)|host|localhost|domain\.com))' \
      "a real address — use user@example.com"

# 4. Absolute home directories. These pin a path to one machine and one username.
check "absolute home path" \
      '([A-Za-z]:\\Users\\[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+)' \
      ':([A-Za-z]:\\Users\\(you|your-name|username|user|name)|/(home|Users)/(you|your-name|username|user|me|name))$' \
      "a machine-specific path — use \$HOME or ~/"

echo
if [ "$fail" -eq 0 ]; then
  echo "leak-gate: clean — the shipped surface names no operator and no environment."
  exit 0
fi
echo "leak-gate: BLOCKED — the shipped surface leaks something specific to one operator/environment."
echo "Replace it with the placeholder convention this repo already uses, or (only for a genuine"
echo "false positive) add a regex to .harness/leak-gate.allow."
exit 1
