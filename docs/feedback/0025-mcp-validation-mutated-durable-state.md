# Feedback 0025: MCP validation mutated durable state

> A harness post-incident. The point is to make this class of mistake less likely next time.
> Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-09-04
- **Status:** applied
- **Fixed release:** `v0.3.1`
- **Cost:** A Claude-to-Codex migration touched an operator browser profile and shared browser/index
  caches before the validation path was isolated; missing before-state evidence made restoration unsafe.

## 1. Evidence / symptom

The migration supplied these observations:

- A non-isolated Playwright MCP touched an existing persistent profile. There was no trustworthy
  before-snapshot, so restoration could have destroyed legitimate operator state.
- Installing Playwright 1.62.1 added a browser revision and garbage-collected an older shared-cache
  revision because the cache was neither isolated nor protected by `PLAYWRIGHT_SKIP_BROWSER_GC`.
- An unpinned `npx -y @vendor/package` launcher could resolve a different release later.
- Root Chromium needed `--no-sandbox`; it ran, but with weaker isolation.
- The MCP client auto-started configured servers without listing capabilities or invoking tools.
  Process existence therefore proved neither discovery nor a real call.
- A returned call did not prove server/browser cleanup. Exact launched process identities were
  required because broad name matching included unrelated processes.
- Generic MCP inventory exposed credential-bearing configuration for an unrelated integration.
  Inventory itself was therefore secret-bearing.
- OAuth availability in one client did not prove authorization in an isolated client. Granted
  scopes did not prove least privilege.
- An identity lookup returned more personal metadata than validation required.
- A successful GitHub read used an admin-capable credential; successful access and acceptance of
  excess privilege were distinct facts.
- A service-plan HTTP 403 did not show that the token needed broader scopes.
- A native CLI already supplied some required capabilities, making another MCP unnecessary.
- An independent synchronizer changed a shared Chroma/SQLite store during validation. Causality
  could not safely be assigned to the request, although retained corpus artifacts stayed byte-identical.
- A retrieval-named operation could rewrite its corpus during automatic re-priming; read intent did
  not make it read-only.
- One integration label hid distinct consumers and credential classes: Pages, Worker/D1, DNS,
  DNS-01, R2, deployment, and runtime secrets.

The incident supported none of these shortcuts: configured ⇒ authenticated; authenticated ⇒ least
privilege; started ⇒ tested; returned ⇒ cleaned up; read-named ⇒ read-only; changed store ⇒ request
caused it; one integration name ⇒ one authority boundary; returned field ⇒ appropriate evidence.

Later closeout supplied four related observations:

- Repeated process/session crashes were recoverable only because Git state, PR/run IDs, plans, and
  protected-file hashes were durable.
- A verifier baseline derived from a dirty operator file passed locally but failed in a clean checkout.
- Truncated search output was treated as complete and caused a false missing-document defect.
- One AAP runner had narrow standing repair authority, and its watchdog reported local liveness while
  repository jobs remained queued.

## 2. Failure mechanism

The old migration checklist covered scope, authentication, ownership, harmless validation, and
external-write consent. It did not make persistent local state, response minimization, privilege
acceptance, background writers, exact child lifecycle, evidence tree provenance, or durable
pre-gate recovery first-class fields.

## 3. Bounded edit

Add one conditional integration checkpoint template and one static JSON validator. Pin AgentSmith's
own executable MCP examples. The validator reads declarations only: it never installs, launches, or
infers semantic evidence. Extend the existing handoff artifact for pre-wait/gate recovery, record
verification tree class, and put the search-completeness check in the dynamic feedback skill.

## 4. Named surface

- Integration decision record: `templates/plan.md` → `templates/integration-checkpoint.md`.
- Static guard and command: `agentsmith.py`; safe shipped examples: `config/mcp.example.json` and
  `config/settings.json`.
- Fixture guard: `tests/fixtures/integration-validation/` and
  `scripts/test-integration-validation.py`.
- Recovery: `templates/handoff-memory.md`, `skills/handoff/SKILL.md`, `scripts/handoff.sh`, and the
  native scaffold in `agentsmith.py`; checked by `scripts/test-durable-checkpoints.py`.
- Clean/local separation: verification receipt `tree_class` in `agentsmith.py`, documented by
  `skills/verify/SKILL.md`, checked by `scripts/test-verify-receipts.py`.
- False absence: `skills/new-feedback/SKILL.md`, checked after native dual-adapter regeneration by
  `scripts/test-durable-checkpoints.py`.
- Project-specific standing authority: the bounded pattern in `docs/15-safety-model.md`, checked by
  `scripts/test-durable-checkpoints.py`; explicit operator instructions already outrank defaults.

The AAP runner permission and repair remain project-specific; the pattern does not grant universal
infrastructure authority. The reusable watchdog lesson already lives in `profiles/devops-setup.md`:
externally observed function, not local process existence, is the evidence. Adding either to
universal core would be duplicated always-loaded prose.

### Lesson-to-guard map

| Accepted lesson | Canonical source | Regression evidence |
|---|---|---|
| Discovery is separate from an exact executable pin | `templates/integration-checkpoint.md`; `agentsmith.py` | fixture cases `unpinned-package`, `exact-package-pin` |
| Playwright profile/cache isolation and bounded sandbox exceptions | `templates/integration-checkpoint.md`; `agentsmith.py` | `playwright-profile-missing`, `playwright-cache-missing`, both `no-sandbox-*` cases, `shared-cache-preserved` |
| Static validation must not mutate profiles/caches, install, launch, or disclose credentials | `agentsmith.py` | `test_cli_never_changes_existing_profile_or_browser_revisions`, `test_validator_does_not_install_or_launch_any_integration`, `test_credentials_never_appear_in_normal_error_or_debug_output` |
| Auto-start, listing, declared invocation, authentication, reads, and privilege acceptance are separate facts | `templates/integration-checkpoint.md`; `agentsmith.py` | `auto-start-is-not-invocation`, `capability-list-is-not-invocation`, `declared-call-not-observed`, `admin-read-not-accepted` |
| A plan-tier 403 is not evidence for wider scopes; an adequate native CLI avoids another MCP | `templates/integration-checkpoint.md`; `agentsmith.py` | both `plan-tier-403-*` cases and `adequate-native-cli` |
| Retained evidence contains only declared minimum response fields | `templates/integration-checkpoint.md`; `agentsmith.py` | both `identity-response-*` cases |
| Protected artifacts, background writers, drift causality, and automatic re-priming are explicit | `templates/integration-checkpoint.md`; `agentsmith.py` | `shared-store-ambiguous-causality`, `retrieval-can-reprime`, and the profile/cache byte snapshot test |
| Cleanup follows exact launched PIDs and ignores unrelated processes | `templates/integration-checkpoint.md`; `agentsmith.py` | `launched-pid-survives`, `unrelated-process-survives` |
| Long gates have a serialized recovery checkpoint | `templates/handoff-memory.md`; `skills/handoff/SKILL.md`; both handoff scaffold implementations | `test_handoff_scaffold_serializes_recovery_checkpoint_fields` |
| Clean-checkout validity and operator-local preservation are different evidence | `agentsmith.py`; `skills/verify/SKILL.md` | `test_record_requires_explicit_tree_class_and_clean_class_rejects_dirty_git` |
| Search absence needs complete evidence before creating a defect | `skills/new-feedback/SKILL.md` | `test_search_absence_gate_is_dynamic_and_generated_adapters_remain_outputs` |
| Standing operational authority stays project-scoped and guarded | `docs/15-safety-model.md` | `test_narrow_project_authority_has_a_bounded_pattern_not_a_universal_grant` |
| External function, not a local process, proves service health | existing `profiles/devops-setup.md` | `test_existing_devops_gate_checks_external_function_not_process_existence` |

The integration tests are fixture-driven through `tests/fixtures/integration-validation/cases.json`.
Disposable native assembly checks both Claude and Codex adapters while keeping the conditional
checkpoint out of always-loaded instructions. Existing conformance/update tests remain the guards
for foreign-file preservation and byte-exact install/update rollback.

## 5. Non-regression validation

Applied after all required gates passed on 2026-09-04:

- `python3 agentsmith.py verify --target .` passed all 22 canonical phases.
- Integration validation passed all six test methods and the 21-case fixture matrix without
  installing or launching an MCP package.
- Durable-checkpoint and verification-receipt suites passed 4 and 13 tests respectively.
- Disposable native assembly regenerated equivalent Claude and Codex managed adapters, installed
  the dynamic checkpoint/skill only at their intended surfaces, and added no project hook.
- Byte snapshots proved the existing browser profile, both cached browser revisions, and
  operator-local files unchanged. Agent conformance also preserved foreign project content.
- The 41-test updater suite proved plan/apply/rollback, including byte-exact restoration and
  foreign-content preservation from disposable installations.
- `python3 agentsmith.py secret-scan --all --target .`, the 35-case leak gate, and
  `git diff --cached --check` passed on the fully staged change.
