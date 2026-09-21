---
status: accepted
decision_ticket: "paste-ready draft: Resolve the Wave 2 orchestration contract"
accepted_by: Lukas Hertig
accepted_at: 2026-09-21T10:20:31+02:00
---
# Spec: Parallel development and integration wave

## Destination

AgentSmith can coordinate several accepted implementation tickets inside one local Git repository
without introducing a second execution engine or a hosted control plane.

The observable end state is a typed, versioned work graph whose ready non-conflicting nodes can run
through the existing finite autonomous-run controller in isolated worktrees. The scheduler derives
state deterministically, survives interruption, and leaves auditable lineage. Successful task
branches can then be composed in a deterministic local integration train, verified together, and
presented to the operator as a local candidate plus a human-readable handoff. Nothing is pushed,
posted, merged into the protected branch, released, deployed, or written to an external system
without separate operator authorization.

The wave also documents one complete agent-native development lifecycle: accepted spec, separate
implementation tickets, parallel execution, composed verification, human approval, release, and
feedback into the harness. The lifecycle documentation describes ownership boundaries honestly;
it does not imply that AgentSmith owns the external tracker, continuous integration service, or
production environment.

## Existing foundation

- [`first-verified-loop-wave.md`](first-verified-loop-wave.md) completed the read-only status,
verification discovery, profile operations, disposable demonstration, continuity, and native
release-evidence foundation.
- [`../21-autonomous-runs.md`](../21-autonomous-runs.md) defines the existing single-ticket finite
controller: accepted spec plus separate ticket, isolated worktree and branch, maker/checker roles,
deterministic verifier, bounded attempts and budgets, path/resource collision checks, safe
stop/resume, durable local state, and no automatic remote writes.
- [`agentsmith-next-stage.md`](agentsmith-next-stage.md) sets the wider product boundary: local and
file-backed first, one repository, no hosted workflow platform, and no broad workflow language.
- `templates/autonomous-run.json` is the current immutable single-run contract. Wave 2 must extend
or reference it rather than silently creating incompatible role, scope, budget, or authority
semantics.

## Model advice at setup

Agent-assisted setup may offer a short, read-only model recommendation for the operator's installed
runtime (Codex or Claude Code). If online access is available, the setup agent checks current
official vendor guidance and local model availability, then names the source date and the
quality-versus-usage trade-off. If offline, it uses the runtime's known local/default choices and
labels the advice as unverified. Neither the installer nor the work-graph scheduler needs live web
access; setup must remain usable without it.

Prefer the least resource-intensive model that has met the project's quality bar. A stronger model
is an explicit operator choice, never an automatic retry or escalation. Keep model names out of
the graph schema and universal rules: the reviewed single-run manifest owns each role's runtime,
model, effort, and budget. Record the requested and effective model when the runtime exposes them;
do not claim a floating alias is a pinned model. A later recommendation cannot mutate an accepted
manifest or a running graph. New models can be recommended without changing the graph contract.

## Non-goals

- A hosted control plane, server, database, dashboard, or team synchronization service. Local files
and Git must prove the need before a hosted layer is considered.
- Cross-repository portfolios. The first graph coordinates exactly one Git common directory.
- Scheduling mutually untrusted makers in the same repository. Existing worktree coordination is
collision protection, not an adversarial isolation boundary.
- Replacing `scripts/autonomous-run.py` with a framework, daemon, queue service, or second maker /
checker state machine.
- Synchronizing priorities or status back to Linear, GitHub Issues, Jira, or another external
tracker.
- Automatic push, pull-request creation, merge into the protected branch, release, deployment, or
production mutation.
- A general workflow domain-specific language, visual builder, plugin marketplace, or catalog of
arbitrary automation recipes.
- A network-dependent install, live model-price scraper, universal model ranking, or automatic
switch to a more expensive model during a run.
- Solving recurring monitoring. Finite multi-ticket orchestration stops at one accepted local
candidate or one explicit escalation; recurring loops remain a separate operating mode.
- Adding the deferred office-work or extension-development profiles. Those remain separate waves.

## Decision map

### Resolved

- [x] **Orchestration state boundary** — A committed graph references committed single-run
  manifests by path and hash; each manifest remains the owner of its ticket, roles, scope, limits,
  verifier, and authority policy. The graph owns only dependency and integration ordering plus a
  concurrency ceiling. Mutable graph state lives in the Git common directory, separate from the
  existing child-run states; see the decision ticket below.
- [x] **Ready-set and dispatch semantics** — Derive a stable topological ready set from pinned
  contracts and child facts. Dispatch at most two non-conflicting nodes initially, subject to
  reviewed limits. Dependent runs inherit a pinned, verified local checkpoint containing accepted
  predecessor commits; see the decision ticket below.
- [x] **Failure, stop, resume, and cleanup semantics** — Failure blocks descendants only; stop and
  resume preserve child ownership, attempts, time, usage, and evidence. Cleanup previews exact
  AgentSmith-owned targets and requires an explicit operator action; see the decision ticket below.
- [x] **Integration order and authority gates** — Compose accepted commits in declared order in a
  disposable local worktree, verify the complete candidate, and retain source branches. Remote and
  protected-branch actions require separate authority; see the decision ticket below.
- [x] **Operator surface and release evidence** — Use a small `graph` CLI, versioned JSON and
  reasoned status, a real end-to-end fixture, security review, and native-platform evidence; see
  the decision ticket below.

### Frontier

- None.

### Blocked
- None.

### Fog

- None blocking this wave. The public noun is `work graph`; the initial concurrency ceiling is two
  and remains configurable downward. Release numbering is a later packaging decision.

## Decision index

- [`../21-autonomous-runs.md`](../21-autonomous-runs.md): reuse the shipped finite-run controller as
the only task execution engine — it already owns isolation, bounded retries, receipts, verification,
and safe resume.
- [`first-verified-loop-wave.md`](first-verified-loop-wave.md): begin Wave 2 only after the First
Verified Loop is proven across supported platforms — orchestration must build on observable state
and verified local operations.
- [`agentsmith-next-stage.md`](agentsmith-next-stage.md): keep the first orchestration release local,
file-backed, single-repository, and free of automatic remote writes — this is the smallest surface
that can prove the product claim.
- Operator direction for this draft: support both Codex and Claude Code, prefer proven quality at
lower usage, refresh model advice from official sources when possible, and never bake today's model
names into the orchestration contract.
- [Orchestration state boundary](#orchestration-state-boundary): reuse the committed manifest and
  child-run state as authorities; the graph adds only immutable relationships and local coordination.
- [Ready-set and dispatch semantics](#ready-set-and-dispatch-semantics): deterministic scheduling
  and pinned dependency checkpoints prevent downstream work from starting on stale code.
- [Failure, stop, resume, and cleanup semantics](#failure-stop-resume-and-cleanup-semantics):
  preserve child authority and evidence while containing failures and foreign-state risk.
- [Integration order and authority gates](#integration-order-and-authority-gates): local merge
  train and full verification produce a candidate, not a release.
- [Operator surface and release evidence](#operator-surface-and-release-evidence): a small CLI
  exposes reproducible status and evidence without adding a hosted control plane.

## Explicit deferrals

- **Hosted/team orchestration:** revisit only after local use demonstrates a synchronization problem
that repository files and Git cannot solve; future owner: post-Wave 2 roadmap decision.
- **Cross-repository graphs:** defer until one-repository dependency, recovery, and integration
semantics have real evidence; future owner: later orchestration version.
- **External tracker synchronization:** keep tickets as referenced contracts and require independent
tracker consent; future owner: integration-specific proposal.
- **Automatic remote delivery:** push, PR creation, merge, release, and deployment remain separate
operator-authorized actions; future owner: release/hosting wave.
- **Untrusted multi-tenant isolation:** do not imply that cooperative worktree collision protection
is a security boundary; future owner: hosted architecture, if ever justified.
- **Visual workflow building:** reconsider only if the versioned graph contract proves too difficult
to author and inspect through files and the CLI.

## Acceptance and evidence

- A committed, versioned graph fixture represents at least three implementation tickets with
dependencies, scoped paths, shared-resource keys, per-node budgets, expected verification, and a
deterministic integration order. Runtime mutation cannot alter the accepted graph bytes or hash.
- Invalid graphs fail before branch, worktree, run-state, or external writes. Coverage includes
unknown dependencies, dependency cycles, duplicate identifiers, unsafe path scopes, conflicting
resource declarations, invalid budgets, ambiguous integration order, and unsupported schema
versions.
- The same graph and local run facts always derive the same node states and ready set. Human-readable
  and JSON status explain why every non-ready node is waiting, conflicting, blocked, failed, or
  interrupted and name one safe next action.
- A dependent run starts from an exact, persisted checkpoint commit containing the accepted commits
  of all transitive predecessors. Contract and predecessor lineage are verified before dispatch;
  the existing single-run controller records the effective base without treating a moving ref as
  reviewed authority.
- Two independent tickets execute concurrently through the existing finite-run controller in
separate worktrees. A path- or resource-conflicting ticket waits. No second controller or
divergent maker/checker contract is introduced.
- A rejected or failed node blocks only its dependants; unrelated ready work may continue within the
concurrency and budget limits. The final graph result cannot be `completed` while any required
node is failed, blocked, interrupted, stale, or missing accepted evidence.
- Operator stop reaches active child runs, leaves parseable durable state, and cannot silently reset
deadlines, attempts, or reported usage. Resume rejects graph drift, base drift, dirty worktrees,
missing lineage, and live competing controllers before starting work.
- Every AgentSmith-owned branch, worktree, manifest, receipt, and evidence record has an explicit
retention and cleanup owner. Cleanup is previewable, refuses research/source deletion, and never
removes user-created or ambiguous state.
- The integration train consumes only accepted node commits with matching lineage. It uses a stable
declared order, creates a recoverable local candidate from the pinned base, and records the exact
source commit for every integrated node.
- Composition stops on dirty inputs, rewritten or missing ancestry, conflicts, verification
regressions, evidence mismatch, or protected-source loss. Compatible changes compose and pass the
full configured repository gate as one candidate, not only their individual checks.
- A failed integration attempt leaves the pinned base and every source branch recoverable. Retry or
rollback starts from durable state rather than an operator reconstructing hidden controller
memory.
- The successful terminal output and JSON identify the local candidate branch/commit, source
lineage, verification receipt, remaining human approval, and explicitly state that no push, PR,
protected-branch merge, release, deployment, or external write occurred.
- One end-to-end fixture exercises prepare, validate, status, parallel dispatch, conflict waiting,
stop/resume, deterministic integration, composed verification, and final handoff through the real
command-line path.
- Security review names command injection, path traversal, symlink escape, plan/state tampering,
ref/config/hook/object-store mutation, secret redaction, foreign-file preservation, cross-worktree
interference, source/research retention, and authority-boundary checks.
- The configured full repository gate passes locally. Native macOS, Linux, and Windows evidence
covers every new filesystem, process, locking, path, and Git boundary; platform reports bind to
the same commit and tree before an aggregate can pass.
- The lifecycle guide follows one concrete feature from accepted spec to separate tickets, graph,
autonomous runs, integration candidate, human delivery approval, observation, and harness
feedback. Every referenced command and artifact exists in the shipped product.
- Agent-assisted setup can explain a dated, runtime-specific model recommendation without changing
settings or running a model; offline setup still works. A reviewed run retains its chosen model
and budget, and no failed node silently escalates to another model.

## Decision-ticket drafts

### Orchestration state boundary

**Question:** What is the minimal versioned graph schema and split between committed immutable
contract data and local mutable execution state, including identifiers, hashes, ownership, state
transitions, run lineage, and migration rules?

**Blocked by:** none

**Resolution:** Use one committed, versioned graph file. It contains `schema_version`, a unique
`graph_id`, `max_parallel`, an explicit `integration_order` of run IDs, and node records with only
`run_id`, repository-relative `manifest_path`, SHA-256 of the committed manifest bytes, and
`depends_on` run IDs. The manifest's own `run_id` must match its graph node. The graph does not copy
the ticket, scope, resources, budget, model, verifier, or Git/external-write policy. No model name
is part of the graph schema. Validate the graph and referenced manifests from one clean committed
contract commit, then record that commit's exact ID in local graph state; putting its hash inside
the graph file would be self-referential. Each child-run controller remains responsible for pinning
its own effective base commit. A dependant may need accepted predecessor code, so its effective
base is not assumed equal to the graph contract commit; the exact derivation and validation of
dependent bases belongs to the next ready-set/dispatch decision.

| Existing single-run field group | Authority after graph introduction |
|---|---|
| Manifest: `schema_version`, `run_id`, `spec_path`, `implementation_ticket`, `base_ref` | Committed node manifest; graph pins its path, bytes, and run ID. |
| Manifest: `roles`, `scope`, `verify`, `limits`, `git`, `external_writes`, optional `worktree_path` | Committed node manifest only; graph derives collision and budget facts from it. |
| Run state: status, attempt, deadline, reported usage, accepted commit and receipts | Existing child-run controller and its state under `agentsmith-runs/<run_id>/`; graph reads, never rewrites it. |
| Run state: base/spec/manifest hashes, branch, worktree, process and lock identity | Existing child-run controller; graph validates lineage but does not duplicate lifecycle ownership. |
| Graph-only: graph hash, contract commit, dispatch/stop/integration lineage, candidate reference | New local graph state under the Git common directory, separate from child-run state and committed files. |

The graph controller owns its state, event log, lifecycle lock, and explicit stop request. A
snapshot is authoritative for recovery; events are an audit trail, not hidden conversational
memory. It may request child operations through the existing controller but never edit child
`state.json` directly. The child controller still owns its branches, worktrees, receipts, and
budgets. The graph owns only its own later integration artifacts. Reconcile persisted graph facts
against pinned graph/manifest hashes, the contract commit, and child-run facts before resume. Unknown
schema versions or changed accepted bytes fail closed; a changed contract requires a new graph ID,
not an in-place migration.

**Rationale:** `templates/autonomous-run.json` and `scripts/autonomous-run.py` already distinguish
the reviewed manifest from mutable state in the Git common directory. The controller validates an
accepted committed spec, commits-only Git policy, scope collisions, original deadline, cumulative
usage, and resume drift. Copying those fields into the graph would create two competing authorities
and permit accidental budget or model changes after approval.

### Ready-set and dispatch semantics

**Question:** Given an accepted graph and current finite-run facts, what exact deterministic rules
derive node state, readiness, conflicts, dispatch order, dependent-node base commits, concurrency,
and graph completion?

**Blocked by:** none

**Resolution:** The graph controller computes node state from the pinned graph, immutable manifest
bytes, child-run snapshots, and graph-owned checkpoint receipts. It never rewrites child state.
Unknown or inconsistent facts are `blocked`, not ready. A node is `ready` only if every dependency
has accepted evidence and its accepted commit is present in a verified checkpoint, its declared
path and resource scopes do not collide with running nodes, and graph/node limits allow launch.
Failed or rejected dependencies block descendants; unrelated ready nodes remain eligible. Stable
topological order, then declared `integration_order`, then `run_id` breaks ties. The initial
`max_parallel` ceiling is two and may be set lower in the reviewed graph; usage and deadline
limits from each manifest remain binding. Restart recomputes the same ready set from durable facts.

Root nodes use the pinned contract commit. For each dependent node, the graph composes all accepted
transitive predecessor commits in declared integration order into a graph-owned local checkpoint.
It verifies their receipts, manifest/spec hashes, ancestry, and exact source commit IDs, then pins
the checkpoint OID in graph and child state before launch. A narrow, reviewed effective-base
handoff to the existing single-run controller is required; a mutable `base_ref` alias or silent
manifest rewrite is not authority. Checkpoint conflicts or missing lineage block the node and
preserve all sources. This composition belongs to W2-03, before dependent dispatch.

**Rationale:** Parallel work is valuable only for independent nodes. Deterministic ordering makes
resume explainable; a pinned checkpoint ensures a dependent ticket actually sees its predecessors'
code rather than the original `HEAD` named in today's single-run template.

### Failure, stop, resume, and cleanup semantics

**Question:** What state transitions and ownership rules contain node failure, propagate dependency
blocks, preserve evidence and budgets across stop/resume, reclaim stale AgentSmith-owned state, and
fail closed around ambiguous or user-owned artifacts?

**Blocked by:** Ready-set and dispatch semantics

**Resolution:** Rejection, verifier failure, or exhausted child limits are terminal for that node
and block its descendants; unrelated nodes may continue. Unexpected controller death or ambiguous
Git/process state marks the node interrupted and requires reconciliation before retry. Operator
stop requests the existing child controller to stop each active run, retains all branches,
worktrees, receipts, logs, and graph state, and makes no new dispatch. Resume takes the graph
lock, verifies contract bytes, pinned base/checkpoint OIDs, child ownership and liveness, clean
worktrees, attempts, deadlines, and cumulative usage; it refuses drift and duplicate controllers.
Neither stop nor resume resets a limit. Cleanup first reports exact paths and refs with ownership
proof; only an explicit cleanup command may remove unambiguous graph-owned disposable artifacts.
Foreign or ambiguous files and research/source material are retained.

**Rationale:** The existing controller owns finite-run recovery and budgets. The graph may
coordinate its children, but cannot manufacture a fresh allowance or erase evidence.

### Integration order and authority gates

**Question:** What deterministic local composition strategy, ordering rule, recovery model, and
human approval gates produce a verified candidate without rewriting source branches or performing
an unauthorized remote/protected-branch action?

**Blocked by:** Ready-set and dispatch semantics, Failure, stop,
resume, and cleanup semantics

**Resolution:** Once every required node has accepted evidence, create a graph-owned candidate
branch and disposable worktree from the pinned contract commit. Incorporate accepted source commits
in `integration_order`, checking receipts, ancestry, cleanliness, and exact OIDs before each step.
Already-included ancestors are recorded, not merged twice. Conflicts, missing or rewritten source,
dirty input, receipt mismatch, or source/protected-branch loss stop locally without changing source
branches. Run the full configured repository verification on the composed candidate and record its
commit, tree, source lineage, and complete result. Retry uses durable lineage and a new disposable
candidate rather than guessing from a partial merge. A successful local candidate still requires
fresh operator authority for push, PR, protected-branch merge, release, deployment, or external
write. A child's `git.merge: false` remains a maker restriction, never a grant to the graph.

**Rationale:** Git worktrees isolate working files, but refs and object storage remain shared.
Exact OIDs and a disposable merge train make conflicts recoverable and prevent a successful child
test from being mistaken for verification of the combined change.

### Operator surface and release evidence

**Question:** What smallest CLI and JSON surface makes orchestration inspectable and recoverable,
how is optional runtime-specific model advice shown during agent-assisted setup without making
installation network-dependent or changing accepted runs, and which local, end-to-end, security,
and native-platform evidence closes Wave 2?

**Blocked by:** Ready-set and dispatch semantics, Failure, stop,
resume, and cleanup semantics, Integration order and authority gates

**Resolution:** Expose `agentsmith graph validate`, `status`, `start`, `stop`, `resume`, `integrate`,
and `cleanup --preview`; the cleanup mutation requires an explicit separate invocation. Commands
offer human output and versioned JSON. Status gives every node's derived state, reason, pinned
lineage, and one safe next action. `start` authorizes local execution only; `integrate` creates and
verifies a local candidate only. Setup-time model advice is read-only, dated, runtime-specific,
and offline-capable; accepted manifests keep their reviewed model and budget. Prove the command
path with a three-node fixture including parallel launch, dependent checkpoint, conflict wait,
stop/resume, candidate verification, and no remote writes. Add named security review and native
macOS, Linux, and Windows evidence for process, lock, path, and Git seams; aggregate reports must
bind to one commit and tree.

**Rationale:** A small CLI and inspectable JSON expose the scheduler's reasons without a second
execution engine. Cross-platform and end-to-end proof are necessary because a unit test cannot
establish worktree, process, and integration behavior on every supported host.

## Implementation-ticket drafts

> These are separate implementation items. Tracker writes remain unauthorized; these bodies are
> paste-ready drafts until the operator posts them.

### W2-01 — Pin orchestration contracts with failing fixtures

- **Outcome:** Versioned graph, local-state, status, event, integration-candidate, and aggregate
evidence schemas express the accepted orchestration decisions before runtime implementation.
- **In scope:** schema files, valid/invalid fixtures, schema/version invariants, plan hashing,
transition table, and focused tests that fail because orchestration commands do not exist.
- **Out of scope:** scheduling, worktree creation, task execution, or integration.
- **Depends on:** accepted terminal spec.
- **Acceptance/evidence:** every decision is represented in a fixture; invalid contracts fail for
the intended reason; existing finite-run suites remain unchanged and green.

### W2-02 — Add typed graph validation and read-only status

- **Outcome:** Operators can validate and inspect an accepted graph and see deterministic node state,
readiness, blockers, conflicts, lineage expectations, and one safe next action without executing
repository code.
- **In scope:** parser, schema/version validation, cycle/order checks, scope/resource normalization,
state derivation, human/JSON output, dry-run or prepare boundary, and migration refusal.
- **Out of scope:** starting finite runs or changing Git state.
- **Depends on:** W2-01.
- **Acceptance/evidence:** focused contracts plus a real CLI trace prove read-only operation and
zero branch/worktree/state/external writes on both valid and invalid inputs.

### W2-03 — Dispatch ready nodes through finite autonomous runs

- **Outcome:** Ready non-conflicting graph nodes execute concurrently through the existing
autonomous-run controller with bounded resources and auditable lineage.
- **In scope:** scheduler loop, reviewed effective-base handoff, graph-owned dependency checkpoint
  composition, concurrency cap, deterministic dispatch, repository coordination, graph event/state
  recording, status, and failure containment.
- **Out of scope:** final all-node candidate integration or any remote action.
- **Depends on:** W2-02.
- **Acceptance/evidence:** parallel, dependency-waiting, path/resource-conflicting, failed, and
budget-exhausted fixtures produce deterministic state with no duplicate controller or orphaned
AgentSmith-owned worktree.

### W2-04 — Make graph stop, resume, and cleanup recoverable

- **Outcome:** Interrupted orchestration resumes from durable facts without resetting contracts,
time, attempts, usage, or lineage, and bounded cleanup cannot remove ambiguous/user-owned data.
- **In scope:** graph lifecycle lock, stop propagation, stale-owner handling, drift checks, resume,
retention inventory, cleanup preview, and explicit escalation.
- **Out of scope:** integration or remote delivery.
- **Depends on:** W2-03.
- **Acceptance/evidence:** process-death, repeated stop, dirty worktree, changed graph, changed base,
stale lock, partial completion, and cleanup fixtures fail or recover exactly as specified.

### W2-05 — Compose a deterministic local integration candidate

- **Outcome:** Accepted node commits become one recoverable, fully verified local candidate with
source lineage and an explicit human delivery gate.
- **In scope:** integration ordering, ancestry/cleanliness validation, local candidate branch,
conflict and regression stops, full composed verification, evidence lineage, rollback/retry, and
prepared handoff text.
- **Out of scope:** push, PR creation, protected-branch merge, release, or deployment.
- **Depends on:** W2-04.
- **Acceptance/evidence:** compatible branches compose and pass; conflicting, rewritten, dirty,
evidence-mismatched, verification-regressing, and protected-source-loss cases stop with every
source branch and the pinned base recoverable.

### W2-06 — Prove and document the complete parallel lifecycle

- **Outcome:** The whole local parallel-development path is reproducible, security-reviewed,
cross-platform, and understandable by a fresh operator.
- **In scope:** real CLI demonstration, sanitized proof artifacts, native platform reports and
aggregate, lifecycle guide, architecture diagram, troubleshooting, limitations, claim map, and
release handoff.
- **Out of scope:** outward launch assets, hosted operation, or any automatic external delivery.
- **Depends on:** W2-05.
- **Acceptance/evidence:** every end-to-end and security item above is linked to reproducible
evidence; full configured verification and native aggregate pass at one commit/tree; an
independent checker cannot find an unsupported claim or hidden authority expansion.

## Acceptance checkpoint

- **Operator acceptance:** Lukas Hertig accepted the four remaining recommendations on
  2026-09-21; the dependency-checkpoint correction is included in W2-03.
- **Decision state:** five resolved, no blocking fog or frontier.
- **Implementation state:** W2-01 through W2-06 are separate local work items; no external tracker
  write is authorized by acceptance.
