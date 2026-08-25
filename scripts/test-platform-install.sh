#!/usr/bin/env bash
# End-to-end platform installer checks. Every HOME/CODEX_HOME is a throwaway directory.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
assert() { local label="$1"; shift; if "$@"; then ok "$label"; else bad "$label"; fi; }
run() { local case_dir="$1"; shift; HOME="$case_dir/home" CODEX_HOME="$case_dir/Orca Account/codex home" bash "$ROOT/setup.sh" "$@" >"$case_dir/out" 2>&1; }
new_case() { local d="$TMP/$1"; mkdir -p "$d/home" "$d/Orca Account/codex home" "$d/project"; printf '%s' "$d"; }

echo "platform-install — native project rules and dry-run isolation"
help_out="$(bash "$ROOT/setup.sh" --help)"
assert "Bash help documents all platform choices" grep -q -- '--platform claude|codex|both' <<<"$help_out"
wizard_out="$(bash "$ROOT/setup.sh" --wizard </dev/null 2>&1 || true)"
assert "Bash wizard asks for platform" grep -q 'Which assistant should receive native rules' <<<"$wizard_out"
c="$(new_case default-claude)"
run "$c" --profile general-admin --assemble-only --target "$c/project"
assert "default remains Claude" test -f "$c/project/CLAUDE.md"
assert "default creates no Codex rule" test ! -e "$c/project/AGENTS.md"

c="$(new_case codex-project)"
run "$c" --platform codex --profile general-admin --assemble-only --target "$c/project"
assert "Codex writes AGENTS.md" test -f "$c/project/AGENTS.md"
assert "Codex-only writes no CLAUDE.md" test ! -e "$c/project/CLAUDE.md"
assert "Codex-only scaffolds no .claude" test ! -e "$c/project/.claude"
assert "assemble-only touches no Codex user config" test ! -e "$c/Orca Account/codex home/config.toml"

c="$(new_case both-project)"
run "$c" --platform both --profile software-dev --assemble-only --target "$c/project"
assert "both writes CLAUDE.md" test -f "$c/project/CLAUDE.md"
assert "both writes AGENTS.md" test -f "$c/project/AGENTS.md"
assert "both rule copies are byte-identical" cmp -s "$c/project/CLAUDE.md" "$c/project/AGENTS.md"

c="$(new_case codex-to-both)"
run "$c" --platform codex --profile general-admin --assemble-only --operator-name "Test Operator" --target "$c/project"
run "$c" --platform both --profile general-admin --assemble-only --target "$c/project"
assert "adding Claude preserves Codex operator identity" grep -Eq '^\*\*Test Operator\*\* is the lead' "$c/project/CLAUDE.md"
assert "transition to both keeps rule copies equivalent" cmp -s "$c/project/CLAUDE.md" "$c/project/AGENTS.md"

for p in claude codex both; do
  c="$(new_case dry-$p)"
  run "$c" --platform "$p" --profile general-admin --target "$c/project" --dry-run
  assert "$p dry-run writes no project files" test -z "$(find "$c/project" -mindepth 1 -print -quit)"
  assert "$p dry-run writes no home files" test -z "$(find "$c/home" "$c/Orca Account/codex home" -mindepth 1 -print -quit)"
  c="$(new_case global-dry-$p)"
  run "$c" --platform "$p" --global --dry-run
  assert "$p global dry-run writes no home files" test -z "$(find "$c/home" "$c/Orca Account/codex home" -mindepth 1 -print -quit)"
done

echo "platform-install — RTK runtime wiring and doctor diagnostics"
make_fake_rtk() {
  local bin="$1"
  mkdir -p "$bin"
  printf '%s\n' '#!/usr/bin/env bash' \
    'if [ "${1:-}" = "--version" ]; then echo "rtk fake"; exit 0; fi' \
    'printf "%s|%s\n" "${CODEX_HOME:-}" "$*" >> "$AGENTSMITH_RTK_CALL_LOG"' \
    > "$bin/rtk"
  chmod +x "$bin/rtk"
}

c="$(new_case rtk-codex-default)"; make_fake_rtk "$c/bin"
AGENTSMITH_RTK_CALL_LOG="$c/calls" PATH="$c/bin:$PATH" HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" \
  bash "$ROOT/setup.sh" --platform codex --profile software-dev --target "$c/project" >"$c/out" 2>&1
assert "Codex code profile enables RTK by default" grep -Fxq "$c/Orca Account/codex home|init -g --codex" "$c/calls"
assert "Codex RTK wiring preserves CODEX_HOME paths with spaces" grep -Fq "$c/Orca Account/codex home|" "$c/calls"
assert "Codex RTK no longer emits a Claude-only warning" sh -c "! grep -q 'Claude-specific wiring.*ignored' '$c/out'"

c="$(new_case rtk-both)"; make_fake_rtk "$c/bin"
AGENTSMITH_RTK_CALL_LOG="$c/calls" PATH="$c/bin:$PATH" HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" \
  bash "$ROOT/setup.sh" --platform both --profile general-admin --with-rtk --target "$c/project" >"$c/out" 2>&1
assert "both-mode initializes Claude RTK" grep -Fq '|init -g --auto-patch' "$c/calls"
assert "both-mode initializes Codex RTK" grep -Fxq "$c/Orca Account/codex home|init -g --codex" "$c/calls"
assert "both-mode initializes RTK exactly once per runtime" test "$(wc -l < "$c/calls" | tr -d ' ')" -eq 2

c="$(new_case rtk-opt-out)"; make_fake_rtk "$c/bin"
AGENTSMITH_RTK_CALL_LOG="$c/calls" PATH="$c/bin:$PATH" HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" \
  bash "$ROOT/setup.sh" --platform codex --profile software-dev --no-rtk --target "$c/project" >"$c/out" 2>&1
assert "--no-rtk suppresses default Codex RTK initialization" test ! -e "$c/calls"

c="$(new_case rtk-doctor)"
printf '%s\n' '@RTK.md' > "$c/Orca Account/codex home/AGENTS.md"
HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" bash "$ROOT/setup.sh" --platform codex --doctor > "$c/doctor-missing" 2>&1
assert "doctor reports a dangling Codex RTK import" grep -Fq "Codex RTK import is dangling: $c/Orca Account/codex home/RTK.md" "$c/doctor-missing"
printf '%s\n' '# generated RTK instructions' > "$c/Orca Account/codex home/RTK.md"
HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" bash "$ROOT/setup.sh" --platform codex --doctor > "$c/doctor-healthy" 2>&1
assert "doctor recognizes healthy Codex RTK wiring" grep -Fq 'Codex RTK instructions wired' "$c/doctor-healthy"

echo "platform-install — Codex config, MCP, skills, hooks, and re-runs"
c="$(new_case codex-full)"
mkdir -p "$c/bin" "$c/project/.codex" "$c/project/.agents/skills/existing" "$c/Orca Account/codex home"
printf '#!/usr/bin/env bash\nprintf invoked >> "$AGENTSMITH_CALL_LOG"\n' > "$c/bin/claude"
cp "$c/bin/claude" "$c/bin/rtk"; chmod +x "$c/bin/claude" "$c/bin/rtk"
printf '# keep-user-comment\nmodel = "gpt-test"\n\n[foreign]\nvalue = 7\n' > "$c/Orca Account/codex home/config.toml"
printf '%s\n' '{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"foreign-user-hook"}]}],"Stop":[{"hooks":[{"type":"command","command":"foreign-stop-hook"}]}]}}' > "$c/Orca Account/codex home/hooks.json"
printf '# keep-project-comment\n\n[mcp_servers.playwright]\ncommand = "manual"\n' > "$c/project/.codex/config.toml"
AGENTSMITH_CALL_LOG="$c/calls" PATH="$c/bin:$PATH" HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" \
  bash "$ROOT/setup.sh" --platform codex --profile general-admin --target "$c/project" --with-skills \
  --with-mcp playwright,context7 --with-handoff-hooks --with-ui-design-hook --safety cautious >"$c/out" 2>&1
assert "Codex-only invokes no Claude/rtk command" test ! -e "$c/calls"
assert "CODEX_HOME with spaces receives config" test -f "$c/Orca Account/codex home/config.toml"
assert "Codex project skills preserve an existing skill" test -d "$c/project/.agents/skills/existing"
assert "Codex project skills install bundled skills" test -f "$c/project/.agents/skills/handoff/SKILL.md"
assert "Codex-only creates no Claude home" test ! -e "$c/home/.claude"
assert "Codex handoff hook installed" test -x "$c/Orca Account/codex home/hooks/handoff-on-keyword.sh"
assert "Codex UI hook installed" test -x "$c/Orca Account/codex home/hooks/ui-design-reminder.sh"
assert "Codex does not install Claude context nudge" test ! -e "$c/Orca Account/codex home/hooks/context-budget-nudge.sh"
assert "Codex does not install Claude statusline" test ! -e "$c/Orca Account/codex home/statusline-command.sh"
assert "foreign TOML comments survive" grep -Eq 'keep-user-comment' "$c/Orca Account/codex home/config.toml"
assert "foreign TOML tables survive" grep -Eq '^\[foreign\]' "$c/Orca Account/codex home/config.toml"
assert "manual MCP name wins" grep -Eq 'command = "manual"' "$c/project/.codex/config.toml"
assert "selected non-conflicting MCP is installed" grep -Eq '^\[mcp_servers\.context7\]' "$c/project/.codex/config.toml"
assert "foreign Codex UserPromptSubmit hook survives" test "$(jq '[.hooks.UserPromptSubmit[].hooks[] | select(.command == "foreign-user-hook")] | length' "$c/Orca Account/codex home/hooks.json")" -eq 1
assert "foreign Codex Stop hook survives" test "$(jq '[.hooks.Stop[].hooks[] | select(.command == "foreign-stop-hook")] | length' "$c/Orca Account/codex home/hooks.json")" -eq 1
python3 - "$c/Orca Account/codex home/config.toml" "$c/project/.codex/config.toml" <<'PY'
import sys, tomllib
user = tomllib.load(open(sys.argv[1], 'rb'))
project = tomllib.load(open(sys.argv[2], 'rb'))
assert user['approval_policy'] == 'on-request'
assert user['sandbox_mode'] == 'workspace-write'
assert user['foreign']['value'] == 7
assert project['mcp_servers']['playwright']['command'] == 'manual'
assert project['mcp_servers']['context7']['command'] == 'npx'
PY
assert "cautious mapping and TOML parse exactly" test $? -eq 0

# Re-run adds a new managed server, retains the prior selection, and does not duplicate hooks/tables.
printf '%s\n' '# stale Codex handoff hook' > "$c/Orca Account/codex home/hooks/handoff-on-keyword.sh"
jq '.hooks.UserPromptSubmit += [.hooks.UserPromptSubmit[] | select(any(.hooks[]?; .command | contains("handoff-on-keyword.sh")))]' \
  "$c/Orca Account/codex home/hooks.json" > "$c/Orca Account/codex home/hooks.json.duplicated"
mv "$c/Orca Account/codex home/hooks.json.duplicated" "$c/Orca Account/codex home/hooks.json"
run "$c" --platform codex --profile general-admin --target "$c/project" --with-mcp excalidraw --with-handoff-hooks --with-ui-design-hook --safety cautious
assert "re-run unions prior MCP selections" grep -Eq '^\[mcp_servers\.context7\]' "$c/project/.codex/config.toml"
assert "re-run adds new MCP selection" grep -Eq '^\[mcp_servers\.excalidraw\]' "$c/project/.codex/config.toml"
assert "managed MCP table is duplicate-free" test "$(grep -Ec '^\[mcp_servers\.context7\]$' "$c/project/.codex/config.toml")" -eq 1
assert "handoff hook definition is duplicate-free" test "$(jq '[.hooks.UserPromptSubmit[].hooks[] | select(.command | contains("handoff-on-keyword.sh"))] | length' "$c/Orca Account/codex home/hooks.json")" -eq 1
assert "stale Codex handoff script is refreshed" cmp -s "$ROOT/hooks/handoff-on-keyword.sh" "$c/Orca Account/codex home/hooks/handoff-on-keyword.sh"
assert "UI hook definition is duplicate-free" test "$(jq '[.hooks.PreToolUse[].hooks[] | select(.command | contains("ui-design-reminder.sh"))] | length' "$c/Orca Account/codex home/hooks.json")" -eq 1
assert "Codex UI hook matches apply_patch only" test "$(jq -r '.hooks.PreToolUse[] | select(any(.hooks[]; .command | contains("ui-design-reminder.sh"))) | .matcher' "$c/Orca Account/codex home/hooks.json")" = '^apply_patch$'
assert "re-run produces parseable user TOML" python3 -c 'import sys,tomllib; tomllib.load(open(sys.argv[1],"rb"))' "$c/Orca Account/codex home/config.toml"
assert "re-run produces parseable project TOML" python3 -c 'import sys,tomllib; tomllib.load(open(sys.argv[1],"rb"))' "$c/project/.codex/config.toml"

echo "platform-install — Claude handoff hook refresh and statusline ownership"
c="$(new_case claude-existing-handoff)"
mkdir -p "$c/home/.claude/hooks"
printf '%s\n' '#!/usr/bin/env bash' 'printf "custom statusline\\n"' > "$c/home/.claude/statusline-command.sh"
cp "$c/home/.claude/statusline-command.sh" "$c/custom-statusline.before"
printf '%s\n' '# stale keyword hook' > "$c/home/.claude/hooks/handoff-on-keyword.sh"
printf '%s\n' '# stale context hook' > "$c/home/.claude/hooks/context-budget-nudge.sh"
printf '%s\n' '{"statusLine":{"type":"command","command":"bash ~/.claude/statusline-command.sh"},"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"foreign-user-hook"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/handoff-on-keyword.sh"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/handoff-on-keyword.sh"}]}],"Stop":[{"hooks":[{"type":"command","command":"foreign-stop-hook"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/context-budget-nudge.sh"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/context-budget-nudge.sh"}]}]}}' > "$c/home/.claude/settings.json"
HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" bash "$ROOT/setup.sh" --platform claude --doctor > "$c/doctor-before" 2>&1
assert "doctor reports a stale Claude handoff script before repair" grep -q 'Claude keyword handoff hook stale or locally modified' "$c/doctor-before"
run "$c" --platform claude --profile general-admin --target "$c/project" --with-handoff-hooks --no-rtk
assert "stale Claude keyword hook is refreshed" cmp -s "$ROOT/hooks/handoff-on-keyword.sh" "$c/home/.claude/hooks/handoff-on-keyword.sh"
assert "stale Claude context hook is refreshed" cmp -s "$ROOT/hooks/context-budget-nudge.sh" "$c/home/.claude/hooks/context-budget-nudge.sh"
assert "existing custom Claude statusline is byte-identical" cmp -s "$c/custom-statusline.before" "$c/home/.claude/statusline-command.sh"
assert "unrelated Claude UserPromptSubmit hook survives" test "$(jq '[.hooks.UserPromptSubmit[].hooks[] | select(.command == "foreign-user-hook")] | length' "$c/home/.claude/settings.json")" -eq 1
assert "unrelated Claude Stop hook survives" test "$(jq '[.hooks.Stop[].hooks[] | select(.command == "foreign-stop-hook")] | length' "$c/home/.claude/settings.json")" -eq 1
assert "pre-existing duplicate Claude keyword hooks collapse" test "$(jq '[.hooks.UserPromptSubmit[].hooks[] | select(.command == "bash ~/.claude/hooks/handoff-on-keyword.sh")] | length' "$c/home/.claude/settings.json")" -eq 1
assert "pre-existing duplicate Claude context hooks collapse" test "$(jq '[.hooks.Stop[].hooks[] | select(.command == "bash ~/.claude/hooks/context-budget-nudge.sh")] | length' "$c/home/.claude/settings.json")" -eq 1
run "$c" --platform claude --profile general-admin --target "$c/project" --with-handoff-hooks --no-rtk
assert "Claude keyword hook remains duplicate-free" test "$(jq '[.hooks.UserPromptSubmit[].hooks[] | select(.command == "bash ~/.claude/hooks/handoff-on-keyword.sh")] | length' "$c/home/.claude/settings.json")" -eq 1
assert "Claude context hook remains duplicate-free" test "$(jq '[.hooks.Stop[].hooks[] | select(.command == "bash ~/.claude/hooks/context-budget-nudge.sh")] | length' "$c/home/.claude/settings.json")" -eq 1
assert "custom Claude statusline survives re-run byte-identically" cmp -s "$c/custom-statusline.before" "$c/home/.claude/statusline-command.sh"
HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" bash "$ROOT/setup.sh" --platform claude --doctor > "$c/doctor" 2>&1
assert "doctor reports current refreshed Claude scripts" grep -q 'Claude keyword handoff hook current' "$c/doctor"
assert "doctor reports custom statusline without a signal writer" grep -q 'statusline has no context signal writer' "$c/doctor"

c_missing="$(new_case handoff-doctor-missing)"
mkdir -p "$c_missing/home/.claude"
printf '%s\n' '{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"echo handoff-on-keyword.sh"}]}],"Stop":[{"hooks":[{"type":"command","command":"echo context-budget-nudge.sh"}]}]}}' > "$c_missing/home/.claude/settings.json"
printf '%s\n' '{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"echo handoff-on-keyword.sh"}]}]}}' > "$c_missing/Orca Account/codex home/hooks.json"
HOME="$c_missing/home" CODEX_HOME="$c_missing/Orca Account/codex home" bash "$ROOT/setup.sh" --platform both --doctor > "$c_missing/doctor" 2>&1
assert "doctor reports missing Claude handoff script" grep -q 'Claude keyword handoff hook missing' "$c_missing/doctor"
assert "doctor reports missing Codex handoff script" grep -q 'Codex keyword handoff hook missing' "$c_missing/doctor"
assert "doctor rejects a Claude command that only names the hook" grep -q 'Claude keyword handoff hook not wired' "$c_missing/doctor"
assert "doctor rejects a Codex command that only names the hook" grep -q 'Codex keyword handoff hook not wired' "$c_missing/doctor"

c="$(new_case both-full)"
mkdir -p "$c/bin"
printf '#!/usr/bin/env bash\nexit 0\n' > "$c/bin/claude"; chmod +x "$c/bin/claude"
PATH="$c/bin:$PATH" HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" \
  bash "$ROOT/setup.sh" --platform both --profile general-admin --target "$c/project" --with-skills \
  --with-mcp context7 --with-handoff-hooks --with-ui-design-hook --no-rtk >"$c/out" 2>&1
assert "both full install writes equivalent project rules" cmp -s "$c/project/CLAUDE.md" "$c/project/AGENTS.md"
assert "both full install writes Claude user config" test -f "$c/home/.claude/settings.json"
assert "both full install writes Codex user config" test -f "$c/Orca Account/codex home/config.toml"
assert "both full install copies Claude skills" test -f "$c/project/.claude/skills/handoff/SKILL.md"
assert "both full install copies Codex skills independently" test -f "$c/project/.agents/skills/handoff/SKILL.md"
assert "both full install writes Claude MCP" test -f "$c/project/.mcp.json"
assert "both full install writes Codex MCP" test -f "$c/project/.codex/config.toml"
assert "both installs Claude context nudge only in Claude home" test -f "$c/home/.claude/hooks/context-budget-nudge.sh"
assert "both does not put context nudge in Codex home" test ! -e "$c/Orca Account/codex home/hooks/context-budget-nudge.sh"
assert "fresh Claude handoff install supplies the managed statusline" cmp -s "$ROOT/config/statusline-command.sh" "$c/home/.claude/statusline-command.sh"
assert "fresh Claude handoff install wires one keyword hook" test "$(jq '[.hooks.UserPromptSubmit[].hooks[] | select(.command == "bash ~/.claude/hooks/handoff-on-keyword.sh")] | length' "$c/home/.claude/settings.json")" -eq 1
assert "fresh Claude handoff install wires one context hook" test "$(jq '[.hooks.Stop[].hooks[] | select(.command == "bash ~/.claude/hooks/context-budget-nudge.sh")] | length' "$c/home/.claude/settings.json")" -eq 1
HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" bash "$ROOT/setup.sh" --platform both --doctor > "$c/doctor" 2>&1
assert "doctor recognizes a healthy Claude context signal writer" grep -q 'statusline contains the per-session context signal writer' "$c/doctor"
assert "doctor recognizes current Codex handoff script" grep -q 'Codex keyword handoff hook current' "$c/doctor"

echo "platform-install — global paths, safety mapping, legacy flag, and uninstall"
c="$(new_case claude-global)"
mkdir -p "$c/bin"; printf '#!/usr/bin/env bash\nexit 0\n' > "$c/bin/claude"; chmod +x "$c/bin/claude"
PATH="$c/bin:$PATH" HOME="$c/home" CODEX_HOME="$c/Orca Account/codex home" \
  bash "$ROOT/setup.sh" --platform claude --global --no-rtk >"$c/out" 2>&1
assert "Claude global full install still writes settings" test -f "$c/home/.claude/settings.json"
assert "Claude global full install writes no Codex config" test ! -e "$c/Orca Account/codex home/config.toml"

c="$(new_case trusted-global)"
run "$c" --platform codex --global --safety trusted --with-skills
assert "Codex global rules use CODEX_HOME" test -f "$c/Orca Account/codex home/AGENTS.md"
assert "Codex global install creates no Claude home" test ! -e "$c/home/.claude"
assert "Codex global skills use ~/.agents/skills" test -f "$c/home/.agents/skills/handoff/SKILL.md"
assert "trusted approval mapping" grep -Eq '^approval_policy = "never"$' "$c/Orca Account/codex home/config.toml"
assert "trusted sandbox mapping" grep -Eq '^sandbox_mode = "danger-full-access"$' "$c/Orca Account/codex home/config.toml"

c="$(new_case both-global)"
run "$c" --platform both --global --assemble-only
assert "both global writes Claude destination" test -f "$c/home/.claude/CLAUDE.md"
assert "both global writes Codex destination" test -f "$c/Orca Account/codex home/AGENTS.md"
assert "both global rules are equivalent" cmp -s "$c/home/.claude/CLAUDE.md" "$c/Orca Account/codex home/AGENTS.md"
run "$c" --platform both --global --uninstall
assert "both global uninstall removes Claude managed-only file" test ! -e "$c/home/.claude/CLAUDE.md"
assert "both global uninstall removes Codex managed-only file" test ! -e "$c/Orca Account/codex home/AGENTS.md"

c="$(new_case legacy)"
run "$c" --platform claude --profile general-admin --assemble-only --also-agents-md --target "$c/project"
assert "legacy flag still writes AGENTS.md" test -f "$c/project/AGENTS.md"
assert "legacy instruction copy equals CLAUDE.md" cmp -s "$c/project/CLAUDE.md" "$c/project/AGENTS.md"
assert "legacy flag prints deprecation guidance" grep -Eq 'deprecated.*--platform both' "$c/out"
run "$c" --platform codex --profile general-admin --assemble-only --uninstall --target "$c/project"
assert "Codex project uninstall removes AGENTS managed file" test ! -e "$c/project/AGENTS.md"
assert "Codex project uninstall leaves Claude rule" test -f "$c/project/CLAUDE.md"

c="$(new_case org-policy)"
if run "$c" --platform codex --org-policy; then bad "Codex org policy is rejected"; else ok "Codex org policy is rejected"; fi
assert "org-policy rejection explains scope" grep -Eq 'Codex organization-policy.*not supported' "$c/out"

echo
printf 'platform-install: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
