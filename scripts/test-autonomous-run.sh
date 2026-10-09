#!/usr/bin/env bash
# Deterministic controller tests: fake runtimes exercise the state machine without API calls.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
concurrent_run_ids=()
concurrent_runner_pids=()
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
assert() { local label="$1"; shift; if "$@"; then ok "$label"; else bad "$label"; fi; }

make_fake() {
  local path="$1"
  mkdir -p "$path/bin" "$path/codex-home"
  printf '%s\n' '{"auth_mode":"chatgpt","tokens":{}}' > "$path/codex-home/auth.json"
  cp "$ROOT/scripts/autonomous-run.py" "$path/controller.py"
  cp "$ROOT/native_launcher.py" "$path/native_launcher.py"
  cp "$ROOT/windows_verifier_sandbox.py" "$path/windows_verifier_sandbox.py"
  chmod +x "$path/controller.py"
  cp "$ROOT/templates/autonomous-run.json" "$path/template.json"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'prompt="${!#}"' \
    'receipt=""' \
    'fake_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"' \
    'mode="$(cat "$fake_root/mode" 2>/dev/null || printf accept)"' \
    'args=("$@")' \
    'for ((i=0; i<${#args[@]}; i++)); do' \
    '  if [ "${args[$i]}" = "-o" ]; then receipt="${args[$((i+1))]}"; fi' \
    'done' \
    'emit() {' \
    '  local payload="$1"' \
    '  if [ -n "$receipt" ]; then printf "%s\n" "$payload" > "$receipt"' \
    '  else printf "{\"type\":\"result\",\"total_cost_usd\":0.25,\"structured_output\":%s}\n" "$payload"; fi' \
    '}' \
    'listed_paths() { git "$@" HEAD~1 HEAD | python3 -c "import json, sys; print(json.dumps(sys.stdin.buffer.read().decode().splitlines()))"; }' \
    'if [ "$mode" = malformed ]; then emit "{}"; exit 0; fi' \
    'if [[ "$prompt" == *"independent checker"* ]]; then' \
    '  if [ -n "$receipt" ]; then for ((i=0; i<${#args[@]}; i++)); do if [ "${args[$i]}" = --sandbox ] && [ "${args[$((i+1))]}" != read-only ]; then exit 42; fi; done; fi' \
    '  if [ "$mode" = mutate-checker ]; then printf bad > src/checker.txt; fi' \
    '  if [ "$mode" = checker-ref ]; then git branch checker-escape; fi' \
    '  if [ "$mode" = checker-slow ]; then printf "{\"type\":\"result\",\"total_cost_usd\":0.125}\n"; sleep 60 & printf "%s" "$!" > "$fake_root/child-pid"; wait; fi' \
    '  count_file="$fake_root/counter"' \
    '  count=0; [ -f "$count_file" ] && count="$(<"$count_file")"' \
    '  count=$((count+1)); printf "%s" "$count" > "$count_file"' \
    '  status=accepted' \
    '  if [ "$mode" = reject-once ] && [ "$count" -eq 1 ]; then status=rejected; fi' \
    '  if [ "$mode" = always-reject ]; then status=rejected; fi' \
    '  paths_json="[\"src/change.txt\"]"; if [ -f "$fake_root/paths_json" ]; then paths_json="$(<"$fake_root/paths_json")"; fi' \
    '  emit "{\"status\":\"$status\",\"summary\":\"checker $status\",\"commit\":\"$(git rev-parse HEAD)\",\"changed_paths\":$paths_json,\"evidence\":[\"fake check\"],\"unresolved\":[],\"next_state\":\"$status\"}"' \
    'else' \
    '  if [ "$mode" = slow ]; then sleep 20; fi' \
    '  if [ "$mode" = collision-slow ]; then sleep 60; fi' \
    '  if [ "$mode" = forge-state ]; then common="$(git rev-parse --git-common-dir)"; for target in "$common"/agentsmith-runs/*/state.json; do printf forged > "$(dirname "$target")/forged.json"; done; fi' \
    '  mkdir -p src' \
    '  n=0; [ -f src/change.txt ] && n="$(<src/change.txt)"' \
    '  printf "%s\n" "$((n+1))" > src/change.txt' \
    '  changed="src/change.txt"' \
    '  if [ "$mode" = weaken-verifier ]; then printf "bypass :: true\n" > .harness/verify.conf; git add .harness/verify.conf; changed=".harness/verify.conf\",\"src/change.txt"; fi' \
    '  if [ "$mode" = out-of-scope ]; then printf x > forbidden.txt; changed="forbidden.txt"; fi' \
    '  if [ "$mode" = ignored-outside ]; then printf x > ignored.tmp; fi' \
    '  if [[ "$mode" == move-protected* ]]; then git mv tests/test_baseline.py src/moved_checks.py; fi' \
    '  if [ "$mode" = move-in-scope ]; then git mv src/keep.txt src/kept.txt; fi' \
    '  if [ "$mode" = quoted-denied ]; then printf "edited\n" > "privé/notes.md"; git add "privé/notes.md"; fi' \
    '  if [ "$mode" = control-name ]; then crafted="$(printf "clear\033[2J.txt")"; printf x > "$crafted"; git add -- "$crafted"; fi' \
    '  if [ "$mode" = plain-accented ]; then printf "edited\n" > "src/résumé.txt"; git add "src/résumé.txt"; fi' \
    '  git add src/change.txt forbidden.txt 2>/dev/null || git add src/change.txt' \
    '  if [ "$mode" = amend-history ]; then git commit --amend --no-edit >/dev/null' \
    '  else git commit -m "test(run): fake maker checkpoint" >/dev/null; fi' \
    '  if [ "$mode" = extra-ref ]; then git branch escaped-ref; fi' \
    '  if [ "$mode" = config-mutation ]; then git config --local agentsmith.escape true; fi' \
    '  if [ "$mode" = hook-mutation ]; then mkdir -p "$(git rev-parse --git-common-dir)/hooks"; printf bad > "$(git rev-parse --git-common-dir)/hooks/escaped"; fi' \
    '  if [ "$mode" = object-mutation ]; then object="$(git rev-parse HEAD^)"; object_path="$(git rev-parse --git-common-dir)/objects/${object:0:2}/${object:2}"; chmod u+w "$object_path"; printf bad > "$object_path"; fi' \
    '  if [ "$mode" = object-admin ]; then mkdir -p "$(git rev-parse --git-common-dir)/objects/info"; printf /tmp/escape > "$(git rev-parse --git-common-dir)/objects/info/alternates"; fi' \
    '  if [ "$mode" = other-index ]; then printf bad >> "$(git rev-parse --git-common-dir)/index"; fi' \
    '  paths_json="[\"$changed\"]"' \
    '  if [ "$mode" = move-protected ]; then paths_json="$(listed_paths diff --name-only --find-renames)"; fi' \
    '  if [ "$mode" = move-protected-listed ] || [ "$mode" = move-in-scope ]; then paths_json="$(listed_paths diff --name-only --no-renames)"; fi' \
    '  if [ "$mode" = quoted-denied ]; then paths_json="$(listed_paths diff --name-only --no-renames)"; fi' \
    '  if [ "$mode" = plain-accented ]; then paths_json="$(listed_paths -c core.quotepath=off diff --name-only --no-renames)"; fi' \
    '  if [ "$paths_json" != "[\"$changed\"]" ]; then printf "%s" "$paths_json" > "$fake_root/paths_json"; fi' \
    '  emit "{\"status\":\"completed\",\"summary\":\"fake maker\",\"commit\":\"$(git rev-parse HEAD)\",\"changed_paths\":$paths_json,\"evidence\":[\"fake maker evidence\"],\"unresolved\":[],\"next_state\":\"checking\"}"' \
    'fi' \
    'if [ -n "$receipt" ]; then printf "%s\n" "{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":7,\"output_tokens\":3}}"; fi' > "$path/bin/fake-agent"
  chmod +x "$path/bin/fake-agent"
}

new_repo() {
  local name="$1" d
  d="$TMP/$name/repo"
  mkdir -p "$d/docs/specs" "$d/.harness/runs"
  git -C "$d" init -q
  git -C "$d" config user.name 'Harness Test'
  git -C "$d" config user.email 'user@example.com'
  printf '%s\n' \
    'ignored.tmp' \
    '---' \
    'status: accepted' \
    'decision_ticket: DEC-1' \
    'accepted_by: Test Operator' \
    'accepted_at: 2026-08-25' \
    '---' \
    '# Spec' \
    '## Destination' \
    'Create the bounded fixture.' > "$d/docs/specs/test.md"
  sed -n '1p' "$d/docs/specs/test.md" > "$d/.gitignore"
  sed '1d' "$d/docs/specs/test.md" > "$d/docs/specs/test.md.tmp"
  mv "$d/docs/specs/test.md.tmp" "$d/docs/specs/test.md"
  git -C "$d" add . && git -C "$d" commit -qm 'test: fixture'
  printf '%s' "$d"
}

manifest() {
  local repo="$1" id="$2"
  python3 - "$repo" "$id" "$ROOT/templates/autonomous-run.json" <<'PY'
import json, pathlib, sys
repo, run_id, template = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
value = json.loads(template.read_text())
value.update(run_id=run_id, spec_path='docs/specs/test.md', implementation_ticket='IMP-1')
for role in value['roles'].values():
    role['model'] = 'fixture-model'
value['scope']['allowed_paths'] = ['src/**']
value['verify']['command'] = 'git rev-parse HEAD >/dev/null && test -f src/change.txt'
value['limits'].update(max_attempts=3, wall_minutes=2)
path = repo / '.harness' / 'runs' / f'{run_id}.json'
path.write_text(json.dumps(value, indent=2) + '\n')
PY
  git -C "$repo" add . && git -C "$repo" commit -qm 'test: add run contract'
}

invoke() {
  local repo="$1" mode="$2"; shift 2
  printf '%s\n' "$mode" > "$repo/../fake/mode"
  AGENTSMITH_CODEX_BIN="$repo/../fake/bin/fake-agent" \
    AGENTSMITH_CLAUDE_BIN="$repo/../fake/bin/fake-agent" \
    CODEX_HOME="$repo/../fake/codex-home" \
    python3 "$repo/../fake/controller.py" "$@"
}

set_manifest_scope() {
  local repo="$1" id="$2" allowed="$3" resources="$4"
  python3 - "$repo/.harness/runs/$id.json" "$allowed" "$resources" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
value = json.loads(path.read_text())
value['scope']['allowed_paths'] = [sys.argv[2]]
if sys.argv[3] == '__legacy__':
    value['scope'].pop('resources', None)
else:
    value['scope']['resources'] = json.loads(sys.argv[3])
path.write_text(json.dumps(value, indent=2) + '\n')
PY
  git -C "$repo" add . && git -C "$repo" commit -qm 'test: declare collision scope'
}

wait_for_active_run() {
  local repo="$1" id="$2" state
  state="$repo/.git/agentsmith-runs/$id/state.json"
  for _ in {1..50}; do
    if [ -f "$state" ] && python3 -c 'import json,sys; raise SystemExit(0 if json.load(open(sys.argv[1])).get("active_pid") else 1)' "$state" 2>/dev/null; then
      return 0
    fi
    sleep 0.05
  done
  return 1
}

stop_started_run() {
  local repo="$1" id="$2"
  if [ -f "$repo/.git/agentsmith-runs/$id/state.json" ]; then
    (cd "$repo" && python3 "$repo/../fake/controller.py" stop "$id" >/dev/null 2>&1) || true
  fi
}

expect_collision() {
  local repo="$1" id="$2" label="$3" output error runner rc
  output="$repo/../$id-out"
  error="$repo/../$id-err"
  (
    cd "$repo" || exit 1
    invoke "$repo" collision-slow start ".harness/runs/$id.json" >"$output" 2>"$error"
  ) & runner=$!
  for _ in {1..50}; do
    if [ -f "$repo/.git/agentsmith-runs/$id/state.json" ] || ! kill -0 "$runner" 2>/dev/null; then break; fi
    sleep 0.05
  done
  if [ -f "$repo/.git/agentsmith-runs/$id/state.json" ]; then
    bad "$label"
    stop_started_run "$repo" "$id"
    wait "$runner" 2>/dev/null || true
  else
    wait "$runner"; rc=$?
    if [ "$rc" -ne 0 ]; then ok "$label"; else bad "$label"; fi
  fi
  assert "$id rejection creates no branch" bash -c "! git -C '$repo' show-ref --verify --quiet 'refs/heads/agentsmith/$id'"
  assert "$id rejection creates no worktree" test ! -e "$repo-$id"
  assert "$id rejection creates no state" test ! -e "$repo/.git/agentsmith-runs/$id/state.json"
}

expect_concurrent_start() {
  local repo="$1" id="$2" label="$3" hold="${4:-yes}" runner
  (
    cd "$repo" || exit 1
    invoke "$repo" collision-slow start ".harness/runs/$id.json" >"$repo/../$id-out" 2>"$repo/../$id-err"
  ) & runner=$!
  if wait_for_active_run "$repo" "$id"; then
    ok "$label"
    if [ "$hold" = yes ]; then
      concurrent_run_ids+=("$id")
      concurrent_runner_pids+=("$runner")
    else
      stop_started_run "$repo" "$id"
      wait "$runner" 2>/dev/null || true
    fi
  else
    bad "$label"
    wait "$runner" 2>/dev/null || true
  fi
}

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    if python3 "$ROOT/scripts/test-windows-verifier-sandbox.py"; then
      ok 'Windows AppContainer confines verifier files and network'
    else
      bad 'Windows AppContainer verifier boundary failed'
    fi
    printf 'autonomous-run: %d passed, %d failed (native Windows boundary covered)\n' "$pass" "$fail"
    [ "$fail" -eq 0 ]
    exit
    ;;
esac

if [ "$(uname -s)" = Linux ]; then
  if python3 - "$ROOT/scripts/autonomous-run.py" "$ROOT" <<'PY'
from pathlib import Path
import sys
namespace = {'__name__': 'agentsmith_sandbox_probe', '__file__': sys.argv[1]}
exec(compile(Path(sys.argv[1]).read_text(), sys.argv[1], 'exec'), namespace)
result = namespace['sandboxed_verify'](
    'exit 0', Path(sys.argv[2]), 15, namespace['verifier_env']())
raise SystemExit(result.returncode)
PY
  then
    ok 'Linux verifier sandbox is operational'
  else
    ok 'Linux host forbids the verifier sandbox, so autonomous execution fails closed'
    printf 'autonomous-run: %d passed, %d failed (state machine covered on macOS/Linux with an operational sandbox)\n' "$pass" "$fail"
    exit 0
  fi
fi

if [ "$(uname -s)" = Darwin ] && [[ "$ROOT" = "$HOME/"* ]] &&
   [ "$(git -C "$ROOT" rev-parse --git-dir)" != "$(git -C "$ROOT" rev-parse --git-common-dir)" ]; then
  if python3 - "$ROOT/scripts/autonomous-run.py" "$ROOT" "$HOME/.gitconfig" <<'PY'
from pathlib import Path
import shlex
import sys
namespace = {'__name__': 'agentsmith_sandbox_probe', '__file__': sys.argv[1]}
exec(compile(Path(sys.argv[1]).read_text(), sys.argv[1], 'exec'), namespace)
private_probe = Path(sys.argv[3])
private_check = f" && test ! -r {shlex.quote(str(private_probe))}" if private_probe.is_file() else ""
result = namespace['sandboxed_verify'](
    'git rev-parse HEAD >/dev/null' + private_check,
    Path(sys.argv[2]), 15, namespace['verifier_env']())
raise SystemExit(result.returncode)
PY
  then ok 'macOS verifier traverses linked Git metadata but not other HOME data'
  else bad 'macOS verifier HOME boundary is incorrect'; fi
fi

echo 'autonomous-run — contract and successful handoff'
repo="$(new_repo success)"; make_fake "$repo/../fake"; manifest "$repo" success
if (cd "$repo" && invoke "$repo" accept start .harness/runs/success.json >../out 2>../err); then
  ok 'maker → verifier → fresh checker accepts a local branch'
else
  bad 'successful fake run exited non-zero'
  sed -n '1,120p' "$repo/../err" 2>/dev/null || true
fi
assert 'accepted run says no external action occurred' grep -q 'nothing was pushed' "$repo/../out"
assert 'status reads durable accepted state' bash -c "cd '$repo' && python3 '$repo/../fake/controller.py' status success | grep -q '\"status\": \"accepted\"'"
assert 'run branch exists only locally' git -C "$repo" show-ref --verify --quiet refs/heads/agentsmith/success
assert 'runtime usage is accumulated across the run' python3 - "$repo/.git/agentsmith-runs/success/state.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
assert s['codex_tokens_used'] == 10
assert s['claude_cost_usd'] == 0.25
PY

assert 'verification receipt binds the accepted candidate and raw evidence' python3 - "$repo/.git/agentsmith-runs/success/state.json" <<'PYTEST'
import hashlib, json, pathlib, sys
state = json.load(open(sys.argv[1]))
proof = json.load(open(state['verification_receipt']))
assert proof['candidate_commit'] == state['accepted_commit']
assert proof['spec_sha256'] == state['spec_sha256']
assert proof['manifest_sha256'] == state['manifest_sha256']
assert proof['exit_code'] == 0
root = pathlib.Path(sys.argv[1]).parent
assert proof['output_sha256'] == hashlib.sha256((root / 'attempt-1-verify.txt').read_bytes()).hexdigest()
assert proof['checker_receipt_sha256'] == hashlib.sha256((root / 'attempt-1-checker-receipt.json').read_bytes()).hexdigest()
assert proof['checker_status'] == 'accepted'
assert json.load(open(root / 'attempt-1-maker-exit.json'))['exit_code'] == 0
assert json.load(open(root / 'attempt-1-checker-exit.json'))['exit_code'] == 0
PYTEST

repo="$(new_repo codex-checker)"; make_fake "$repo/../fake"; manifest "$repo" codex-checker
python3 - "$repo/.harness/runs/codex-checker.json" <<'PYTEST'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); v = json.loads(p.read_text())
v['roles']['maker']['runtime'] = 'claude'
v['roles']['checker']['runtime'] = 'codex'
p.write_text(json.dumps(v) + '\n')
PYTEST
git -C "$repo" add . && git -C "$repo" commit -qm 'test: inverse role adapters'
if (cd "$repo" && invoke "$repo" accept start .harness/runs/codex-checker.json >../out 2>../err); then
  ok 'Claude maker and Codex checker complete with read-only checker argv'
else bad 'inverse role adapters failed'; fi

echo 'autonomous-run — rejection and bounded retry'
repo="$(new_repo retry)"; make_fake "$repo/../fake"; manifest "$repo" retry
if (cd "$repo" && invoke "$repo" reject-once start .harness/runs/retry.json >../out 2>../err); then
  ok 'checker rejection is handed to a fresh maker attempt'
else bad 'reject-once run did not recover'; fi
assert 'retry state persists attempt count' bash -c "cd '$repo' && python3 '$repo/../fake/controller.py' status retry | grep -q '\"attempt\": 2'"

echo 'autonomous-run — fail-closed gates'
repo="$(new_repo scope)"; make_fake "$repo/../fake"; manifest "$repo" scope
if (cd "$repo" && invoke "$repo" out-of-scope start .harness/runs/scope.json >../out 2>../err); then
  bad 'out-of-scope maker change was accepted'
else ok 'out-of-scope maker change escalates'; fi
assert 'scope escalation names the unexpected path' grep -q 'outside scope: forbidden.txt' "$repo/../err"

repo="$(new_repo mutate)"; make_fake "$repo/../fake"; manifest "$repo" mutate
if (cd "$repo" && invoke "$repo" mutate-checker start .harness/runs/mutate.json >../out 2>../err); then
  bad 'mutating checker was accepted'
else ok 'checker mutation escalates'; fi
assert 'checker mutation is explicit' grep -q 'checker modified its disposable worktree' "$repo/../err"

repo="$(new_repo refs)"; make_fake "$repo/../fake"; manifest "$repo" refs
if (cd "$repo" && invoke "$repo" extra-ref start .harness/runs/refs.json >../out 2>../err); then
  bad 'maker-created side ref was accepted'
else ok 'maker cannot mutate refs outside its run branch'; fi
assert 'ref mutation is explicit' grep -q 'Git refs outside the active run branch' "$repo/../err"

repo="$(new_repo config)"; make_fake "$repo/../fake"; manifest "$repo" config
if (cd "$repo" && invoke "$repo" config-mutation start .harness/runs/config.json >../out 2>../err); then
  bad 'maker Git config mutation was accepted'
else ok 'maker cannot mutate repository config'; fi
assert 'config mutation is explicit' grep -q 'protected Git metadata: config' "$repo/../err"

repo="$(new_repo hooks)"; make_fake "$repo/../fake"; manifest "$repo" hooks
if (cd "$repo" && invoke "$repo" hook-mutation start .harness/runs/hooks.json >../out 2>../err); then
  bad 'maker Git hook mutation was accepted'
else ok 'maker cannot mutate repository hooks'; fi
assert 'hook mutation is explicit' grep -q 'protected Git metadata: hooks' "$repo/../err"

repo="$(new_repo objects)"; make_fake "$repo/../fake"; manifest "$repo" objects
if (cd "$repo" && invoke "$repo" object-mutation start .harness/runs/objects.json >../out 2>../err); then
  bad 'maker existing-object corruption was accepted'
else ok 'maker cannot alter existing Git objects'; fi
if grep -q 'altered existing Git objects' "$repo/../err"; then
  ok 'object corruption is explicit'
else
  sed -n '1,8p' "$repo/../err"
  bad 'object corruption is explicit'
fi

repo="$(new_repo object-admin)"; make_fake "$repo/../fake"; manifest "$repo" object-admin
if (cd "$repo" && invoke "$repo" object-admin start .harness/runs/object-admin.json >../out 2>../err); then
  bad 'maker object-store administration file was accepted'
else ok 'maker cannot add object-store administration files'; fi
assert 'object-store administration escape is explicit' grep -q 'non-object files in Git' "$repo/../err"

repo="$(new_repo other-index)"; make_fake "$repo/../fake"; manifest "$repo" other-index
if (cd "$repo" && invoke "$repo" other-index start .harness/runs/other-index.json >../out 2>../err); then
  bad 'maker main-worktree index mutation was accepted'
else ok 'maker cannot alter another worktree index'; fi
assert 'other-worktree mutation is explicit' grep -q 'protected Git metadata: protected_files' "$repo/../err"

repo="$(new_repo rewrite)"; make_fake "$repo/../fake"; manifest "$repo" rewrite
if (cd "$repo" && invoke "$repo" amend-history start .harness/runs/rewrite.json >../out 2>../err); then
  bad 'maker history rewrite was accepted'
else ok 'maker history rewrite is rejected'; fi
assert 'history rewrite is explicit' grep -q 'not a fast-forward' "$repo/../err"

repo="$(new_repo ignored)"; make_fake "$repo/../fake"; manifest "$repo" ignored
if (cd "$repo" && invoke "$repo" ignored-outside start .harness/runs/ignored.json >../out 2>../err); then
  bad 'ignored out-of-scope artifact was accepted'
else ok 'ignored files remain inside declared scope'; fi
assert 'ignored path escape is explicit' grep -q 'ignored paths outside scope: ignored.tmp' "$repo/../err"

repo="$(new_repo checker-ref)"; make_fake "$repo/../fake"; manifest "$repo" checker-ref
if (cd "$repo" && invoke "$repo" checker-ref start .harness/runs/checker-ref.json >../out 2>../err); then
  bad 'checker-created ref was accepted'
else ok 'checker cannot mutate shared Git refs'; fi
assert 'checker ref mutation is explicit' grep -q 'checker changed protected Git metadata: refs' "$repo/../err"

repo="$(new_repo verifier-escape)"; make_fake "$repo/../fake"; manifest "$repo" verifier-escape
python3 - "$repo/.harness/runs/verifier-escape.json" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); v = json.loads(p.read_text())
v['verify']['command'] = 'printf escaped > ../escaped'
p.write_text(json.dumps(v) + '\n')
PY
git -C "$repo" add . && git -C "$repo" commit -qm 'test: hostile verifier contract'
if (cd "$repo" && AWS_SECRET_ACCESS_KEY=do-not-expose invoke "$repo" accept start .harness/runs/verifier-escape.json >../out 2>../err); then
  bad 'escaping verifier was accepted'
else ok 'verifier cannot write outside its disposable worktree'; fi
assert 'verifier escape created no sibling artifact' test ! -e "$repo/../escaped"

repo="$(new_repo draft)"; make_fake "$repo/../fake"; manifest "$repo" draft
sed -i.bak 's/status: accepted/status: draft/' "$repo/docs/specs/test.md" && rm "$repo/docs/specs/test.md.bak"
git -C "$repo" add . && git -C "$repo" commit -qm 'test: draft gate'
if (cd "$repo" && invoke "$repo" accept start .harness/runs/draft.json >../out 2>../err); then
  bad 'draft spec started implementation'
else ok 'draft spec cannot start implementation'; fi
assert 'draft rejection explains the human gate' grep -q 'spec status must be accepted' "$repo/../err"

repo="$(new_repo malformed)"; make_fake "$repo/../fake"; manifest "$repo" malformed
if (cd "$repo" && invoke "$repo" malformed start .harness/runs/malformed.json >../out 2>../err); then
  bad 'malformed runtime receipt was accepted'
else ok 'malformed runtime receipt escalates'; fi
assert 'malformed receipt failure is explicit' grep -q 'no schema-valid receipt' "$repo/../err"

repo="$(new_repo capped)"; make_fake "$repo/../fake"; manifest "$repo" capped
if (cd "$repo" && invoke "$repo" always-reject start .harness/runs/capped.json >../out 2>../err); then
  bad 'run exceeded its rejection cap'
else ok 'three checker rejections escalate'; fi
assert 'attempt cap is persisted and reported' grep -q 'attempt cap reached (3)' "$repo/../err"

echo 'autonomous-run — concurrent scope and resource collision protection'
repo="$(new_repo collisions)"; make_fake "$repo/../fake"
manifest "$repo" live-primary; set_manifest_scope "$repo" live-primary 'src/**' '["port:3000"]'
manifest "$repo" overlap-path; set_manifest_scope "$repo" overlap-path 'src/widgets/**' '["service:widgets"]'
manifest "$repo" shared-resource; set_manifest_scope "$repo" shared-resource 'docs/**' '["port:3000"]'
manifest "$repo" disjoint; set_manifest_scope "$repo" disjoint 'docs/**' '["service:redis"]'
manifest "$repo" wildcard-root; set_manifest_scope "$repo" wildcard-root '**/*.md' '["db:wide"]'
manifest "$repo" legacy; set_manifest_scope "$repo" legacy 'tests/**' '__legacy__'
manifest "$repo" malformed-candidate; set_manifest_scope "$repo" malformed-candidate 'tests/**' '["service:malformed-check"]'
manifest "$repo" dead-owner-ignored; set_manifest_scope "$repo" dead-owner-ignored 'src/widgets/**' '["service:dead-check"]'
manifest "$repo" race-a; set_manifest_scope "$repo" race-a 'packages/shared/**' '["service:race-a"]'
manifest "$repo" race-b; set_manifest_scope "$repo" race-b 'packages/shared/sub/**' '["service:race-b"]'
manifest "$repo" successor; set_manifest_scope "$repo" successor 'src/widgets/**' '["port:4000"]'
(
  cd "$repo" || exit 1
  invoke "$repo" collision-slow start .harness/runs/live-primary.json >../primary-out 2>../primary-err
) & primary_runner=$!
if wait_for_active_run "$repo" live-primary; then ok 'primary collision fixture is live'
else bad 'primary collision fixture did not become live'; fi

expect_collision "$repo" overlap-path 'ancestor/descendant path overlap is rejected'
assert 'path collision names the conflicting run and prefix' bash -c "grep -q 'live-primary' '$repo/../overlap-path-err' && grep -q 'src' '$repo/../overlap-path-err'"
expect_collision "$repo" shared-resource 'shared declared resource is rejected'
assert 'resource collision names the conflicting run and key' bash -c "grep -q 'live-primary' '$repo/../shared-resource-err' && grep -q 'port:3000' '$repo/../shared-resource-err'"
expect_collision "$repo" wildcard-root 'glob without a fixed prefix reserves the repository root'
assert 'wildcard-root collision names the conflicting run' grep -q 'live-primary' "$repo/../wildcard-root-err"

mkdir -p "$repo/.git/agentsmith-runs/malformed-live"
python3 - "$repo/.git/agentsmith-runs/malformed-live/controller.lock" <<'PY'
import json, os, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(
    json.dumps({'pid': os.getppid(), 'run_id': 'malformed-live', 'token': 'fixture'}) + '\n',
    encoding='utf-8',
)
PY
expect_collision "$repo" malformed-candidate 'unverifiable scope for a live owner fails closed'
assert 'malformed live-state refusal names the run' grep -q 'malformed-live' "$repo/../malformed-candidate-err"
python3 - "$repo/.git/agentsmith-runs/malformed-live" <<'PY'
import pathlib, sys
directory = pathlib.Path(sys.argv[1])
(directory / 'controller.lock').unlink()
directory.rmdir()
PY

expect_concurrent_start "$repo" disjoint 'disjoint paths and resources may run concurrently'
expect_concurrent_start "$repo" legacy 'legacy manifest without resources remains valid and non-conflicting'

(
  cd "$repo" || exit 1
  invoke "$repo" collision-slow start .harness/runs/race-a.json >../race-a-out 2>../race-a-err
) & race_a_runner=$!
(
  cd "$repo" || exit 1
  invoke "$repo" collision-slow start .harness/runs/race-b.json >../race-b-out 2>../race-b-err
) & race_b_runner=$!
for _ in {1..50}; do
  race_states=0
  [ -f "$repo/.git/agentsmith-runs/race-a/state.json" ] && race_states=$((race_states+1))
  [ -f "$repo/.git/agentsmith-runs/race-b/state.json" ] && race_states=$((race_states+1))
  [ "$race_states" -gt 0 ] && break
  sleep 0.05
done
sleep 0.2
race_states=0
[ -f "$repo/.git/agentsmith-runs/race-a/state.json" ] && race_states=$((race_states+1))
[ -f "$repo/.git/agentsmith-runs/race-b/state.json" ] && race_states=$((race_states+1))
if [ "$race_states" -eq 1 ]; then ok 'simultaneous overlapping starts serialize to one live run'
else bad 'simultaneous overlapping starts did not serialize to one live run'; fi
if [ -f "$repo/.git/agentsmith-runs/race-a/state.json" ]; then
  race_winner=race-a; race_loser=race-b
else
  race_winner=race-b; race_loser=race-a
fi
if [ "$race_states" -eq 1 ]; then
  assert 'simultaneous-start loser creates no branch' bash -c "! git -C '$repo' show-ref --verify --quiet 'refs/heads/agentsmith/$race_loser'"
  assert 'simultaneous-start loser creates no worktree' test ! -e "$repo-$race_loser"
fi
(cd "$repo" && python3 "$repo/../fake/controller.py" stop live-primary >/dev/null 2>&1)
wait "$primary_runner" 2>/dev/null || true
assert 'stopped primary run is durably interrupted' bash -c "cd '$repo' && python3 '$repo/../fake/controller.py' status live-primary | grep -q '\"status\": \"interrupted\"'"
for id in "${concurrent_run_ids[@]}" race-a race-b; do
  stop_started_run "$repo" "$id"
done
for runner in "${concurrent_runner_pids[@]}" "$race_a_runner" "$race_b_runner"; do
  wait "$runner" 2>/dev/null || true
done
mkdir -p "$repo/.git/agentsmith-runs/dead-scope"
python3 - "$repo/.git/agentsmith-runs/dead-scope/controller.lock" <<'PY'
import json, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(
    json.dumps({'pid': 99999999, 'run_id': 'dead-scope', 'token': 'fixture'}) + '\n',
    encoding='utf-8',
)
PY
expect_concurrent_start "$repo" dead-owner-ignored 'demonstrably dead controller no longer reserves its scope' no
(
  cd "$repo" || exit 1
  invoke "$repo" collision-slow start .harness/runs/successor.json >../successor-out 2>../successor-err
) & successor_runner=$!
if wait_for_active_run "$repo" successor; then ok 'stopped run no longer reserves its former scope'
else
  sed -n '1,8p' "$repo/../successor-err"
  bad 'stopped run still blocked its former scope'
fi

(
  cd "$repo" || exit 1
  invoke "$repo" collision-slow resume live-primary >../resume-collision-out 2>../resume-collision-err
) & resume_runner=$!
resume_restarted=0
for _ in {1..50}; do
  if ! kill -0 "$resume_runner" 2>/dev/null; then break; fi
  if python3 -c 'import json,sys; raise SystemExit(0 if json.load(open(sys.argv[1])).get("active_pid") else 1)' \
      "$repo/.git/agentsmith-runs/live-primary/state.json" 2>/dev/null; then
    resume_restarted=1
    break
  fi
  sleep 0.05
done
if [ "$resume_restarted" -eq 1 ]; then
  bad 'resume is rejected while another conflicting controller is live'
  stop_started_run "$repo" live-primary
  wait "$resume_runner" 2>/dev/null || true
else
  wait "$resume_runner"; resume_rc=$?
  if [ "$resume_rc" -ne 0 ]; then ok 'resume is rejected while another conflicting controller is live'
  else bad 'resume is rejected while another conflicting controller is live'; fi
fi
if grep -q 'successor' "$repo/../resume-collision-err" && grep -q 'src' "$repo/../resume-collision-err"; then
  ok 'resume collision names the live conflicting run and prefix'
else
  sed -n '1,8p' "$repo/../resume-collision-err"
  bad 'resume collision names the live conflicting run and prefix'
fi
stop_started_run "$repo" successor
wait "$successor_runner" 2>/dev/null || true

echo 'autonomous-run — operator stop and clean resume'
repo="$(new_repo stopped)"; make_fake "$repo/../fake"; manifest "$repo" stopped
(
  cd "$repo" || exit 1
  invoke "$repo" slow start .harness/runs/stopped.json >../out 2>../err
) & runner=$!
for _ in {1..50}; do
  sleep 0.1
  if (cd "$repo" && python3 "$repo/../fake/controller.py" status stopped 2>/dev/null | grep -Eq '"active_pid": [1-9]'); then break; fi
done
assert 'live controller owns the run lifecycle lock' test -f "$repo/.git/agentsmith-runs/stopped/controller.lock"
(while kill -0 "$runner" 2>/dev/null; do
  python3 -c 'import json,sys; json.load(open(sys.argv[1]))' \
    "$repo/.git/agentsmith-runs/stopped/state.json" || exit 1
done) & observer=$!
(cd "$repo" && python3 "$repo/../fake/controller.py" stop stopped >/dev/null 2>&1)
wait "$runner" 2>/dev/null || true
if wait "$observer"; then ok 'state remains parseable throughout start/stop collision'
else bad 'state became unparseable during start/stop collision'; fi
assert 'stop leaves durable interrupted state' bash -c "cd '$repo' && python3 '$repo/../fake/controller.py' status stopped | grep -q '\"status\": \"interrupted\"'"
assert 'controller records exactly one interruption transition' python3 - "$repo/.git/agentsmith-runs/stopped/events.jsonl" <<'PY'
import json, sys
events = [json.loads(line) for line in open(sys.argv[1])]
raise SystemExit(0 if sum(event['event'] == 'run_interrupted' for event in events) == 1 else 1)
PY
deadline_before="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["deadline_epoch"])' "$repo/.git/agentsmith-runs/stopped/state.json")"
printf 'dirty\n' > "$repo-stopped/dirty.tmp"
if (cd "$repo" && invoke "$repo" accept resume stopped >../dirty-out 2>../dirty-err); then
  bad 'dirty run worktree resumed'
elif grep -q 'cannot resume a dirty worktree' "$repo/../dirty-err"; then
  ok 'resume refuses a dirty run worktree'
else bad 'dirty-worktree refusal was not explicit'; fi
assert 'failed dirty resume preserves the stop request' test -f "$repo/.git/agentsmith-runs/stopped/STOP"
rm "$repo-stopped/dirty.tmp"
python3 - "$repo/.git/agentsmith-runs/stopped/state.json" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1]); state = json.loads(path.read_text())
state['claude_cost_usd'] = 1.5
state['codex_tokens_used'] = 50
path.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n')
PY
if (cd "$repo" && invoke "$repo" accept resume stopped >../resume-out 2>../resume-err); then
  ok 'interrupted clean run resumes from durable state'
else bad 'interrupted run did not resume'; fi
deadline_after="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["deadline_epoch"])' "$repo/.git/agentsmith-runs/stopped/state.json")"
assert 'resume preserves the original wall-clock deadline' test "$deadline_before" = "$deadline_after"
assert 'resume accumulates rather than resets run-wide usage budgets' python3 - "$repo/.git/agentsmith-runs/stopped/state.json" <<'PY'
import json, sys
state = json.load(open(sys.argv[1]))
assert state['claude_cost_usd'] == 1.75
assert state['codex_tokens_used'] == 60
PY
assert 'completed controller releases the lifecycle lock' test ! -e "$repo/.git/agentsmith-runs/stopped/controller.lock"

echo 'autonomous-run — dead controller, live refusal, and stale recovery'
repo="$(new_repo dead-controller)"; make_fake "$repo/../fake"; manifest "$repo" dead-controller
(
  cd "$repo" || exit 1
  invoke "$repo" slow start .harness/runs/dead-controller.json >../out 2>../err
) & runner=$!
for _ in {1..50}; do
  sleep 0.1
  state_file="$repo/.git/agentsmith-runs/dead-controller/state.json"
  if [ -f "$state_file" ] && python3 -c 'import json,sys; raise SystemExit(0 if json.load(open(sys.argv[1])).get("active_pid") else 1)' "$state_file"; then break; fi
done
child_pid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["active_pid"])' "$state_file")"
controller_pid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pid"])' "$repo/.git/agentsmith-runs/dead-controller/controller.lock")"
kill -KILL "$controller_pid" 2>/dev/null || true
kill -KILL "$child_pid" 2>/dev/null || true
kill -KILL "$runner" 2>/dev/null || true
wait "$runner" 2>/dev/null || true
status_before="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$state_file")"
(cd "$repo" && python3 "$repo/../fake/controller.py" stop dead-controller >../stop-out 2>../stop-err)
status_after="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$state_file")"
assert 'dead-controller stop remains request-only' test "$status_before" = "$status_after"
assert 'dead-controller stop leaves the request for resume reconciliation' test -f "$repo/.git/agentsmith-runs/dead-controller/STOP"
assert 'dead-controller stop explains reconciliation' grep -q 'resume will reconcile' "$repo/../stop-out"
python3 - "$repo/.git/agentsmith-runs/dead-controller/controller.lock" <<'PY'
import json, os, pathlib, sys
path = pathlib.Path(sys.argv[1])
lock_key = 'to' + 'ken'
path.write_text(json.dumps({'pid': os.getppid(), lock_key: 'live-test'}) + '\n')
PY
if (cd "$repo" && invoke "$repo" accept resume dead-controller >../live-out 2>../live-err); then
  bad 'resume ignored a live controller lock'
elif grep -q 'live controller' "$repo/../live-err"; then
  ok 'resume refuses a second live controller'
else bad 'live controller refusal was not explicit'; fi
python3 - "$repo/.git/agentsmith-runs/dead-controller/controller.lock" <<'PY'
import json, pathlib, sys
lock_key = 'to' + 'ken'
pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid': 99999999, lock_key: 'stale-test'}) + '\n')
PY
if (cd "$repo" && invoke "$repo" accept resume dead-controller >../stale-out 2>../stale-err); then
  ok 'resume reclaims a demonstrably stale lifecycle lock'
else bad 'resume did not reclaim a stale lifecycle lock'; fi
assert 'resume reconciles and removes a stale stop request' test ! -e "$repo/.git/agentsmith-runs/dead-controller/STOP"

echo 'autonomous-run — repeated start/stop race'
race_fail=0
for iteration in 1 2 3 4 5; do
  repo="$(new_repo "race-$iteration")"; make_fake "$repo/../fake"; manifest "$repo" "race-$iteration"
  if [ "$iteration" -eq 1 ]; then
    # Exercise startup beyond the old 2.5-second window in this copied fixture.
    python3 - "$repo/../fake/controller.py" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
source = path.read_text()
entry = 'if __name__ == "__main__":\n    raise SystemExit(main())'
assert entry in source
path.write_text(source.replace(entry, 'if __name__ == "__main__":\n'
    '    if len(sys.argv) > 1 and sys.argv[1] == "start": time.sleep(4)\n'
    '    raise SystemExit(main())'))
PY
  fi
  (
    cd "$repo" || exit 1
    invoke "$repo" slow start ".harness/runs/race-$iteration.json" >../out 2>../err
  ) & runner=$!
  state_file="$repo/.git/agentsmith-runs/race-$iteration/state.json"
  if ! python3 - "$state_file" <<'PY'
import json, pathlib, sys, time
path = pathlib.Path(sys.argv[1])
deadline = time.monotonic() + 10
while time.monotonic() < deadline:
    try:
        if json.loads(path.read_text()).get('active_pid'):
            raise SystemExit(0)
    except (OSError, ValueError):
        pass
    time.sleep(0.05)
print('maker readiness barrier timed out: ' + str(path), file=sys.stderr)
raise SystemExit(1)
PY
  then
    race_fail=1
    cat "$repo/../err" >&2
    if [ -f "$state_file" ]; then cat "$state_file" >&2; fi
    stop_started_run "$repo" "race-$iteration"
    wait "$runner" 2>/dev/null || true
    break
  fi
  if ! (cd "$repo" && python3 "$repo/../fake/controller.py" stop "race-$iteration" >../stop-out 2>../stop-err); then
    race_fail=1
    cat "$repo/../stop-out" "$repo/../stop-err" "$repo/../err" >&2
  fi
  wait "$runner" 2>/dev/null || true
  if ! python3 - "$state_file" "$repo/.git/agentsmith-runs/race-$iteration/events.jsonl" <<'PY'
import json, sys
state = json.load(open(sys.argv[1]))
events = [json.loads(line) for line in open(sys.argv[2])]
assert state['status'] == 'interrupted', json.dumps(state, sort_keys=True)
assert sum(event['event'] == 'run_interrupted' for event in events) == 1, events
PY
  then
    race_fail=1
    cat "$repo/../stop-out" "$repo/../stop-err" "$repo/../err" >&2
  fi
done
if [ "$race_fail" -eq 0 ]; then ok 'repeated stop collisions stay parseable with one interruption each'
else bad 'repeated stop collision invariant failed'; fi

repo="$(new_repo same-ticket)"; make_fake "$repo/../fake"; manifest "$repo" same-ticket
python3 - "$repo/.harness/runs/same-ticket.json" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); v = json.loads(p.read_text()); v['implementation_ticket'] = 'DEC-1'; p.write_text(json.dumps(v)+'\n')
PY
git -C "$repo" add . && git -C "$repo" commit -qm 'test: invalid ticket seam'
if (cd "$repo" && invoke "$repo" accept start .harness/runs/same-ticket.json >../out 2>../err); then
  bad 'decision ticket was reused for implementation'
else ok 'decision and implementation tickets must differ'; fi

repo="$(new_repo weaken-verifier)"; make_fake "$repo/../fake"; manifest "$repo" weaken-verifier
mkdir -p "$repo/.harness"
printf 'required :: exit 1\n' > "$repo/.harness/verify.conf"
python3 - "$repo/.harness/runs/weaken-verifier.json" <<'PYTEST'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); v = json.loads(p.read_text())
v['scope']['allowed_paths'] = ['**']
p.write_text(json.dumps(v) + '\n')
PYTEST
git -C "$repo" add . && git -C "$repo" commit -qm 'test: failing approved verification policy'
if (cd "$repo" && invoke "$repo" weaken-verifier start .harness/runs/weaken-verifier.json >../out 2>../err); then
  bad 'maker weakened the approved verifier'
else ok 'maker cannot weaken verification even with broad scope'; fi
assert 'verifier weakening explains separate operator review' grep -q 'protected verification inputs' "$repo/../err"
assert 'policy rejection retains committed candidate' test -f "$repo/../repo-weaken-verifier/src/change.txt"

# A move deletes the old path and adds the new one. Git's default listing shows the new path only,
# so each case below fails if the controller reads that listing again.
repo="$(new_repo move-scope)"; make_fake "$repo/../fake"; manifest "$repo" move-scope
mkdir -p "$repo/tests"; printf 'approved baseline check\n' > "$repo/tests/test_baseline.py"
git -C "$repo" add . && git -C "$repo" commit -qm 'test: approved baseline check'
if (cd "$repo" && invoke "$repo" move-protected start .harness/runs/move-scope.json >../out 2>../err); then
  bad 'maker moved a baseline check into scope and was accepted'
else ok 'moving a baseline check into scope escalates'; fi
assert 'scope escalation names the old path of a move' grep -q 'outside scope: tests/test_baseline.py' "$repo/../err"

repo="$(new_repo move-broad)"; make_fake "$repo/../fake"; manifest "$repo" move-broad
mkdir -p "$repo/tests"; printf 'approved baseline check\n' > "$repo/tests/test_baseline.py"
set_manifest_scope "$repo" move-broad '**' '[]'
if (cd "$repo" && invoke "$repo" move-protected start .harness/runs/move-broad.json >../out 2>../err); then
  bad 'broad scope accepted a moved baseline check that the receipt left out'
else ok 'a receipt that leaves out the old path of a move escalates'; fi
assert 'short receipt is rejected as a Git state mismatch' grep -q 'maker receipt does not match' "$repo/../err"

repo="$(new_repo move-listed)"; make_fake "$repo/../fake"; manifest "$repo" move-listed
mkdir -p "$repo/tests"; printf 'approved baseline check\n' > "$repo/tests/test_baseline.py"
set_manifest_scope "$repo" move-listed '**' '[]'
if (cd "$repo" && invoke "$repo" move-protected-listed start .harness/runs/move-listed.json >../out 2>../err); then
  bad 'broad scope accepted a moved baseline check'
else ok 'moving a baseline check escalates even with broad scope'; fi
assert 'moved baseline check needs separate operator review' \
  grep -q 'protected verification inputs.*tests/test_baseline.py' "$repo/../err"

repo="$(new_repo move-allowed)"; make_fake "$repo/../fake"; manifest "$repo" move-allowed
mkdir -p "$repo/src"; printf 'keep\n' > "$repo/src/keep.txt"
git -C "$repo" add . && git -C "$repo" commit -qm 'test: file the maker may move'
if (cd "$repo" && invoke "$repo" move-in-scope start .harness/runs/move-allowed.json >../out 2>../err); then
  ok 'a move inside scope is accepted when both receipts list old and new path'
else
  bad 'a move inside scope was rejected'
  sed -n '1,40p' "$repo/../err" 2>/dev/null || true
fi

# Git's display listing quotes and escapes a non-ASCII name. A scope rule is written with the real
# name, so the controller must compare real names: the first maker repeats the quoted listing.
repo="$(new_repo quoted-denied)"; make_fake "$repo/../fake"; manifest "$repo" quoted-denied
mkdir -p "$repo/privé"; printf 'private\n' > "$repo/privé/notes.md"
python3 - "$repo/.harness/runs/quoted-denied.json" <<'PYTEST'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); v = json.loads(p.read_text(encoding='utf-8'))
v['scope']['allowed_paths'] = ['**']
v['scope']['denied_paths'].append('priv\u00e9/**')
p.write_text(json.dumps(v) + '\n', encoding='utf-8')
PYTEST
git -C "$repo" add . && git -C "$repo" commit -qm 'test: denied directory with a non-ASCII name'
if (cd "$repo" && invoke "$repo" quoted-denied start .harness/runs/quoted-denied.json >../out 2>../err); then
  bad 'edit under a denied non-ASCII path was accepted'
else ok 'edit under a denied non-ASCII path escalates'; fi
assert 'scope escalation names the denied non-ASCII path' grep -q 'outside scope: priv' "$repo/../err"

repo="$(new_repo control-name)"; make_fake "$repo/../fake"; manifest "$repo" control-name
if (cd "$repo" && invoke "$repo" control-name start .harness/runs/control-name.json >../out 2>../err); then
  bad 'out-of-scope file with a crafted name was accepted'
else ok 'out-of-scope file with a crafted name escalates'; fi
assert 'crafted name is shown with its control character escaped' grep -q -F 'outside scope: clear\x1b[2J.txt' "$repo/../err"
assert 'crafted name writes no control character to the terminal' bash -c "! grep -q \$'\\033' '$repo/../err'"

repo="$(new_repo plain-accented)"; make_fake "$repo/../fake"; manifest "$repo" plain-accented
mkdir -p "$repo/src"; printf 'base\n' > "$repo/src/résumé.txt"
git -C "$repo" add . && git -C "$repo" commit -qm 'test: allowed file with a non-ASCII name'
if (cd "$repo" && invoke "$repo" plain-accented start .harness/runs/plain-accented.json >../out 2>../err); then
  ok 'edit to an allowed non-ASCII path is accepted when receipts use the plain name'
else
  bad 'edit to an allowed non-ASCII path was rejected'
  sed -n '1,40p' "$repo/../err" 2>/dev/null || true
fi

echo 'autonomous-run — trusted state and stage recovery'
repo="$(new_repo stage-recovery)"; make_fake "$repo/../fake"; manifest "$repo" stage-recovery
(cd "$repo" && invoke "$repo" checker-slow start .harness/runs/stage-recovery.json >../out 2>../err) & runner=$!
for _ in {1..100}; do
  if [ -f "$repo/../fake/child-pid" ]; then break; fi
  sleep 0.05
done
assert 'checker stage was exercised before interruption' test -f "$repo/../fake/child-pid"
(cd "$repo" && python3 "$repo/../fake/controller.py" stop stage-recovery >../stop-out 2>../stop-err)
wait "$runner" 2>/dev/null || true
assert 'interruption retains checking stage and emitted spend' python3 - "$repo/.git/agentsmith-runs/stage-recovery/state.json" <<'PYTEST'
import json, sys
v=json.load(open(sys.argv[1]))
assert v['stage']=='checking' and v['status']=='interrupted'
assert v['attempt']==1 and v['claude_cost_usd']==0.125
PYTEST
assert 'stop terminates checker descendants' python3 - "$repo/../fake/child-pid" <<'PYTEST'
import os, pathlib, sys, time
pid=int(pathlib.Path(sys.argv[1]).read_text())
for _ in range(100):
    try: os.kill(pid,0)
    except ProcessLookupError: break
    time.sleep(0.02)
else: raise AssertionError('checker child remains live')
PYTEST
if (cd "$repo" && invoke "$repo" accept resume stage-recovery >../resume-out 2>../resume-err); then
  ok 'checking stage resumes to acceptance'
else bad 'checking stage recovery failed'; cat "$repo/../resume-err"; fi
assert 'recovery checks the same candidate without another maker' python3 - "$repo/.git/agentsmith-runs/stage-recovery/state.json" "$repo-stage-recovery/src/change.txt" <<'PYTEST'
import json, pathlib, sys
v=json.load(open(sys.argv[1]))
assert v['attempt']==1 and v['status']=='accepted'
assert v['candidate_commit']==v['accepted_commit']
assert pathlib.Path(sys.argv[2]).read_text().strip()=='1'
assert v['claude_cost_usd']==0.375
PYTEST
assert 'recovery archives interrupted checker logs' python3 - "$repo/.git/agentsmith-runs/stage-recovery" <<'PYTEST'
import pathlib,sys
root=pathlib.Path(sys.argv[1])
logs=list((root/'archive').glob('*/attempt-1-checker.stdout'))
assert len(logs)==1 and '0.125' in logs[0].read_text()
assert (root/'attempt-1-checker-exit.json').exists()
PYTEST


echo 'autonomous-run — hard crash during checking'
repo="$(new_repo checker-crash)"; make_fake "$repo/../fake"; manifest "$repo" checker-crash
(cd "$repo" && invoke "$repo" checker-slow start .harness/runs/checker-crash.json >../out 2>../err) & runner=$!
for _ in {1..100}; do
  if [ -f "$repo/../fake/child-pid" ]; then break; fi
  sleep 0.05
done
assert 'checker emitted durable output before controller crash' test -f "$repo/../fake/child-pid"
controller_pid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["controller_pid"])' "$repo/.git/agentsmith-runs/checker-crash/state.json")"
kill -KILL "$controller_pid"
wait "$runner" 2>/dev/null || true
(cd "$repo" && python3 "$repo/../fake/controller.py" stop checker-crash >../stop-out 2>../stop-err)
if (cd "$repo" && invoke "$repo" accept resume checker-crash >../resume-out 2>../resume-err); then
  ok 'hard crash recovers the checkpoint and abandoned checker worktree'
else bad 'hard crash did not recover'; cat "$repo/../resume-err"; fi
assert 'crash recovery replays reported usage exactly once and retains attempt' python3 - "$repo/.git/agentsmith-runs/checker-crash/state.json" <<'PYTEST'
import json,sys
v=json.load(open(sys.argv[1]))
assert v['status']=='accepted' and v['attempt']==1
assert v['claude_cost_usd']==0.375
assert v['accepted_commit']==v['candidate_commit']
assert 'usage_pending' not in v
PYTEST
assert 'hard crash retains prior stdout in the archive' python3 - "$repo/.git/agentsmith-runs/checker-crash" <<'PYTEST'
import pathlib,sys
root=pathlib.Path(sys.argv[1])
assert any('0.125' in p.read_text() for p in (root/'archive').glob('*/attempt-1-checker.stdout'))
PYTEST

echo
printf 'autonomous-run: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
