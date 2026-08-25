#!/usr/bin/env bash
# Deterministic controller tests: fake runtimes exercise the state machine without API calls.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
assert() { local label="$1"; shift; if "$@"; then ok "$label"; else bad "$label"; fi; }

make_fake() {
  local path="$1"
  mkdir -p "$path/bin"
  cp "$ROOT/scripts/autonomous-run.py" "$path/controller.py"
  chmod +x "$path/controller.py"
  cp "$ROOT/templates/autonomous-run.json" "$path/template.json"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'prompt="${!#}"' \
    'receipt=""' \
    'args=("$@")' \
    'for ((i=0; i<${#args[@]}; i++)); do' \
    '  if [ "${args[$i]}" = "-o" ]; then receipt="${args[$((i+1))]}"; fi' \
    'done' \
    'emit() {' \
    '  local payload="$1"' \
    '  if [ -n "$receipt" ]; then printf "%s\n" "$payload" > "$receipt"' \
    '  else printf "{\"type\":\"result\",\"total_cost_usd\":0.25,\"structured_output\":%s}\n" "$payload"; fi' \
    '}' \
    'if [ "${FAKE_MODE:-accept}" = malformed ]; then emit "{}"; exit 0; fi' \
    'if [[ "$prompt" == *"independent checker"* ]]; then' \
    '  if [ "${FAKE_MODE:-accept}" = mutate-checker ]; then printf bad > src/checker.txt; fi' \
    '  if [ "${FAKE_MODE:-accept}" = checker-ref ]; then git branch checker-escape; fi' \
    '  count_file="${FAKE_COUNTER:-/tmp/agentsmith-fake-counter}"' \
    '  count=0; [ -f "$count_file" ] && count="$(<"$count_file")"' \
    '  count=$((count+1)); printf "%s" "$count" > "$count_file"' \
    '  status=accepted' \
    '  if [ "${FAKE_MODE:-accept}" = reject-once ] && [ "$count" -eq 1 ]; then status=rejected; fi' \
    '  if [ "${FAKE_MODE:-accept}" = always-reject ]; then status=rejected; fi' \
    '  emit "{\"status\":\"$status\",\"summary\":\"checker $status\",\"commit\":\"$(git rev-parse HEAD)\",\"changed_paths\":[\"src/change.txt\"],\"evidence\":[\"fake check\"],\"unresolved\":[],\"next_state\":\"$status\"}"' \
    'else' \
    '  if [ "${FAKE_MODE:-accept}" = slow ]; then sleep 20; fi' \
    '  mkdir -p src' \
    '  n=0; [ -f src/change.txt ] && n="$(<src/change.txt)"' \
    '  printf "%s\n" "$((n+1))" > src/change.txt' \
    '  changed="src/change.txt"' \
    '  if [ "${FAKE_MODE:-accept}" = out-of-scope ]; then printf x > forbidden.txt; changed="forbidden.txt"; fi' \
    '  if [ "${FAKE_MODE:-accept}" = ignored-outside ]; then printf x > ignored.tmp; fi' \
    '  git add src/change.txt forbidden.txt 2>/dev/null || git add src/change.txt' \
    '  if [ "${FAKE_MODE:-accept}" = amend-history ]; then git commit --amend --no-edit >/dev/null' \
    '  else git commit -m "test(run): fake maker checkpoint" >/dev/null; fi' \
    '  if [ "${FAKE_MODE:-accept}" = extra-ref ]; then git branch escaped-ref; fi' \
    '  if [ "${FAKE_MODE:-accept}" = config-mutation ]; then git config --local agentsmith.escape true; fi' \
    '  if [ "${FAKE_MODE:-accept}" = hook-mutation ]; then mkdir -p "$(git rev-parse --git-common-dir)/hooks"; printf bad > "$(git rev-parse --git-common-dir)/hooks/escaped"; fi' \
    '  if [ "${FAKE_MODE:-accept}" = object-mutation ]; then object="$(git rev-parse HEAD^)"; object_path="$(git rev-parse --git-common-dir)/objects/${object:0:2}/${object:2}"; chmod u+w "$object_path"; printf bad > "$object_path"; fi' \
    '  if [ "${FAKE_MODE:-accept}" = object-admin ]; then mkdir -p "$(git rev-parse --git-common-dir)/objects/info"; printf /tmp/escape > "$(git rev-parse --git-common-dir)/objects/info/alternates"; fi' \
    '  if [ "${FAKE_MODE:-accept}" = other-index ]; then printf bad >> "$(git rev-parse --git-common-dir)/index"; fi' \
    '  emit "{\"status\":\"completed\",\"summary\":\"fake maker\",\"commit\":\"$(git rev-parse HEAD)\",\"changed_paths\":[\"$changed\"],\"evidence\":[\"fake maker evidence\"],\"unresolved\":[],\"next_state\":\"checking\"}"' \
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
  FAKE_MODE="$mode" FAKE_COUNTER="$repo/../counter" \
    AGENTSMITH_CODEX_BIN="$repo/../fake/bin/fake-agent" \
    AGENTSMITH_CLAUDE_BIN="$repo/../fake/bin/fake-agent" \
    python3 "$repo/../fake/controller.py" "$@"
}

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    if python3 - "$ROOT/scripts/autonomous-run.py" "$ROOT" <<'PY'
from pathlib import Path
import sys
namespace = {'__name__': 'agentsmith_sandbox_probe', '__file__': sys.argv[1]}
exec(compile(Path(sys.argv[1]).read_text(), sys.argv[1], 'exec'), namespace)
result = namespace['sandboxed_verify'](
    'exit 0', Path(sys.argv[2]), 15, namespace['verifier_env']())
raise SystemExit(0 if result.returncode == 126 else 1)
PY
    then ok 'unsupported Windows verifier fails closed instead of running unrestricted'
    else bad 'unsupported Windows verifier did not fail closed'; fi
    printf 'autonomous-run: %d passed, %d failed (state machine covered on macOS/Linux)\n' "$pass" "$fail"
    [ "$fail" -eq 0 ]
    exit
    ;;
esac

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
(cd "$repo" && python3 "$repo/../fake/controller.py" stop stopped >/dev/null 2>&1)
wait "$runner" 2>/dev/null || true
assert 'stop leaves durable interrupted state' bash -c "cd '$repo' && python3 '$repo/../fake/controller.py' status stopped | grep -q '\"status\": \"interrupted\"'"
deadline_before="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["deadline_epoch"])' "$repo/.git/agentsmith-runs/stopped/state.json")"
if (cd "$repo" && invoke "$repo" accept resume stopped >../resume-out 2>../resume-err); then
  ok 'interrupted clean run resumes from durable state'
else bad 'interrupted run did not resume'; fi
deadline_after="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["deadline_epoch"])' "$repo/.git/agentsmith-runs/stopped/state.json")"
assert 'resume preserves the original wall-clock deadline' test "$deadline_before" = "$deadline_after"

repo="$(new_repo same-ticket)"; make_fake "$repo/../fake"; manifest "$repo" same-ticket
python3 - "$repo/.harness/runs/same-ticket.json" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); v = json.loads(p.read_text()); v['implementation_ticket'] = 'DEC-1'; p.write_text(json.dumps(v)+'\n')
PY
git -C "$repo" add . && git -C "$repo" commit -qm 'test: invalid ticket seam'
if (cd "$repo" && invoke "$repo" accept start .harness/runs/same-ticket.json >../out 2>../err); then
  bad 'decision ticket was reused for implementation'
else ok 'decision and implementation tickets must differ'; fi

echo
printf 'autonomous-run: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
