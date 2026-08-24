#!/usr/bin/env bash
# test-ui-design-reminder.sh — non-regression suite for hooks/ui-design-reminder.sh.
#
# This is the core/60 guard for the design-system feature: the reason the harness now nudges on UI
# edits is a real incident (a portal shipped ignoring its design system). This suite fails if that
# nudge regresses — either by going silent when it should fire, or by firing when it must not
# (backend projects, non-UI files) or firing on every edit instead of once per session.
#
# Point it at a deliberately-broken copy to prove it can fail (a guard nobody has watched fail is a
# claim, not a guard — R2):   HOOK_BIN=/path/to/broken.sh bash scripts/test-ui-design-reminder.sh
#
# Usage: bash scripts/test-ui-design-reminder.sh     # exit 0 = all pass, 1 = a test failed
set -uo pipefail   # deliberately NOT -e: run every test, then report

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="${HOOK_BIN:-$SCRIPT_DIR/../hooks/ui-design-reminder.sh}"
BASH_BIN="$(command -v bash)"

# jq is a harness prerequisite (CI installs it, setup.sh requires it, the hook uses it). Without jq
# the hook no-ops by design, so the nudge path cannot be exercised at all — fail-safe, not fail-loud.
# Skip LOUDLY rather than paint a false red on a jq-less dev box; CI always has jq and runs it fully.
if ! command -v jq >/dev/null 2>&1; then
  echo "test-ui-design-reminder: SKIP — jq not installed, nudge path not exercised (CI covers it)."
  exit 0
fi

# Isolate markers + fixtures under one throwaway TMPDIR: the hook writes its once-per-session marker
# to $TMPDIR, and every fixture project lives here too, so cases can't leak into each other or the
# real /tmp. mktemp -d fixtures are NOT git repos, so the hook's git-root fallback is a clean no-op.
WORK="$(mktemp -d)"; export TMPDIR="$WORK"
trap 'rm -rf "$WORK"' EXIT

pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

# emit <cwd> <tool> <file_path> <session_id> -> the Claude hook's stdout
emit() {
  printf '{"tool_name":"%s","tool_input":{"file_path":"%s"},"cwd":"%s","session_id":"%s"}' \
    "$2" "$3" "$1" "$4" | bash "$HOOK" 2>/dev/null
}
# emit_patch <cwd> <patch> <session_id> -> the Codex hook's stdout. jq builds the fixture so
# newlines and backslashes exercise the real JSON string shape rather than hand-escaped test data.
emit_patch() {
  jq -nc --arg cwd "$1" --arg command "$2" --arg sid "$3" '{
    hook_event_name:"PreToolUse", turn_id:"turn-test", tool_name:"apply_patch",
    tool_input:{command:$command}, cwd:$cwd, session_id:$sid
  }' | bash "$HOOK" 2>/dev/null
}
nudged()  { grep -q 'DESIGN.md' <<<"$1"; }   # a real nudge names DESIGN.md in additionalContext
silent()  { [ -z "${1//[[:space:]]/}" ]; }   # a no-op prints nothing

echo "test-ui-design-reminder — fires on UI edits with a DESIGN.md"

proj="$(mktemp -d)"; : > "$proj/DESIGN.md"
out="$(emit "$proj" Edit "$proj/Button.tsx" sess-1)"
if nudged "$out"; then ok ".tsx edit + DESIGN.md present → nudges once"; else bad ".tsx edit + DESIGN.md present → NOT nudged (the incident would recur)"; fi

# Same session, second UI edit → silent. This is the "once per session, not per edit" property.
out="$(emit "$proj" Edit "$proj/Card.tsx" sess-1)"
if silent "$out"; then ok "second UI edit, same session → silent (once per session, not per edit)"; else bad "second UI edit re-nudged — would nag on every edit"; fi

# A new session gets a fresh nudge: the marker is per-session, not global.
out="$(emit "$proj" Edit "$proj/Modal.tsx" sess-2)"
if nudged "$out"; then ok "new session → nudges again (marker is per-session)"; else bad "new session stayed silent — marker leaked across sessions"; fi

# A file under components/ that isn't a listed extension still counts as UI.
out="$(emit "$proj" Write "$proj/components/nav.ts" sess-3)"
if nudged "$out"; then ok "components/ path (non-listed ext) → nudges"; else bad "components/ path → NOT nudged"; fi

echo "test-ui-design-reminder — recognizes Codex apply_patch paths"

update_patch="$(printf '%s\n' '*** Begin Patch' '*** Update File: src/components/Button.tsx' '@@' '-old' '+new' '*** End Patch')"
out="$(emit_patch "$proj" "$update_patch" codex-update)"
if nudged "$out" && grep -q 'src/components/Button.tsx' <<<"$out"; then
  ok "Codex Update File UI patch → nudges with affected path"
else
  bad "Codex Update File UI patch → NOT nudged"
fi

# Once per session also applies to Codex patches; re-running an installer must not create a
# duplicate reminder path or cause a second nudge in the same session.
out="$(emit_patch "$proj" "$update_patch" codex-update)"
if silent "$out"; then ok "second Codex patch, same session → silent"; else bad "second Codex patch re-nudged"; fi

add_patch="$(printf '%s\n' '*** Begin Patch' '*** Add File: src/styles/new-view.scss' '+.view {}' '*** End Patch')"
out="$(emit_patch "$proj" "$add_patch" codex-add)"
if nudged "$out" && grep -q 'src/styles/new-view.scss' <<<"$out"; then
  ok "Codex Add File UI patch → nudges"
else
  bad "Codex Add File UI patch → NOT nudged"
fi

delete_patch="$(printf '%s\n' '*** Begin Patch' '*** Delete File: src/legacy/OldView.vue' '*** End Patch')"
out="$(emit_patch "$proj" "$delete_patch" codex-delete)"
if nudged "$out" && grep -q 'src/legacy/OldView.vue' <<<"$out"; then
  ok "Codex Delete File UI patch → nudges"
else
  bad "Codex Delete File UI patch → NOT nudged"
fi

# The first file is backend-only. The hook must inspect every patch header and find the later UI
# file instead of stopping at the first affected path.
multi_patch="$(printf '%s\n' '*** Begin Patch' '*** Update File: server/main.go' '@@' '-old' '+new' '*** Add File: src/ui/panel.ts' '+export {}' '*** End Patch')"
out="$(emit_patch "$proj" "$multi_patch" codex-multi)"
if nudged "$out" && grep -q 'src/ui/panel.ts' <<<"$out" && ! grep -q 'server/main.go' <<<"$out"; then
  ok "multi-file patch finds later UI path after backend path"
else
  bad "multi-file patch did not isolate the affected UI path"
fi

move_patch="$(printf '%s\n' '*** Begin Patch' '*** Update File: src/backend/template.txt' '*** Move to: src/components/Template.ts' '@@' ' old' '*** End Patch')"
out="$(emit_patch "$proj" "$move_patch" codex-move)"
if nudged "$out" && grep -q 'src/components/Template.ts' <<<"$out"; then
  ok "Codex Move to UI path → nudges on destination"
else
  bad "Codex Move to UI path → NOT nudged"
fi

echo "test-ui-design-reminder — stays silent when it must"

# Backend file, DESIGN.md present → silent (this is the whole point: don't nag non-UI work).
out="$(emit "$proj" Edit "$proj/main.go" sess-4)"
if silent "$out"; then ok ".go edit → silent"; else bad ".go edit nudged — would fire on backend work"; fi

backend_patch="$(printf '%s\n' '*** Begin Patch' '*** Update File: server/main.go' '@@' '-old' '+new' '*** End Patch')"
out="$(emit_patch "$proj" "$backend_patch" codex-backend)"
if silent "$out"; then ok "Codex backend-only patch → silent"; else bad "Codex backend-only patch nudged"; fi

out="$(emit_patch "$proj" 'not an apply_patch document' codex-malformed)"; rc=$?
if [ "$rc" -eq 0 ] && silent "$out"; then
  ok "malformed Codex patch → successful silent no-op"
else
  bad "malformed Codex patch did not fail open (rc=$rc)"
fi

# UI file but NO DESIGN.md at root → silent (backend/CLI projects with no design system).
noproj="$(mktemp -d)"    # deliberately no DESIGN.md
out="$(emit "$noproj" Edit "$noproj/Button.tsx" sess-5)"
if silent "$out"; then ok ".tsx edit + no DESIGN.md → silent (self-gates on DESIGN.md)"; else bad ".tsx edit without DESIGN.md nudged — self-gate broken"; fi

echo "test-ui-design-reminder — fail-open (never blocks an edit)"

# jq absent: run with an empty PATH so `command -v jq` finds nothing. The hook must no-op silently,
# never emit a blocking decision. (bash builtins need no PATH; the guard exits before reading stdin.)
out="$(printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"},"cwd":"%s","session_id":"sess-6"}' "$proj/Button.tsx" "$proj" | PATH="" "$BASH_BIN" "$HOOK" 2>/dev/null)"
if silent "$out"; then ok "jq absent → silent no-op"; else bad "jq absent produced output — not fail-safe"; fi

# Malformed input → silent no-op, not a crash or a block.
out="$(printf 'not json {{' | bash "$HOOK" 2>/dev/null)"
if silent "$out"; then ok "malformed input → silent no-op"; else bad "malformed input produced output"; fi

# The emitted nudge must NEVER carry a permission decision (that would block or auto-approve).
freshproj="$(mktemp -d)"; : > "$freshproj/DESIGN.md"
out="$(emit "$freshproj" Edit "$freshproj/App.tsx" sess-7)"
if nudged "$out" && ! grep -q 'permissionDecision' <<<"$out"; then
  ok "nudge injects additionalContext only — no permissionDecision (never blocks/auto-approves)"
else
  bad "nudge carried a permissionDecision — could block or auto-approve the edit"
fi

out="$(emit_patch "$freshproj" "$update_patch" codex-permission)"
if nudged "$out" && jq -e '.hookSpecificOutput.hookEventName == "PreToolUse" and (.hookSpecificOutput | has("permissionDecision") | not)' >/dev/null 2>&1 <<<"$out"; then
  ok "Codex nudge uses PreToolUse context only — no permission decision"
else
  bad "Codex nudge carried a permission decision or wrong event shape"
fi

echo
printf 'test-ui-design-reminder: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
