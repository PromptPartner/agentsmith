# Parallel work graphs

A work graph coordinates several **accepted finite coding runs in one Git repository**. It is a
local scheduler, not a second coding agent or a permission to publish. Use it when independent
tickets can run together and a later ticket must inherit accepted predecessor code.

The reviewed graph is one committed JSON file. Each node points to one committed finite-run
manifest by path and SHA-256. The manifest keeps authority over its ticket, runtime, model, scope,
verifier, budget, and external-write policy. The graph adds only dependency edges, a deterministic
integration order, and a maximum of one or two simultaneous runs. An accepted Wayfinder spec and
separate implementation tickets remain prerequisites; the agent cannot accept its own spec.

```text
committed graph + pinned manifests
              |
       validate / status  (read-only)
              |
             start
       /                  \
   child A             child B       (existing finite-run controller)
       \                  /
      verified dependency checkpoint
                  |
               child C
                  |
         integrate: local candidate + full verify receipt
                  |
          human delivery decision (outside this command)
```

## Inspect before execution

From a clean repository containing the graph:

```sh
agentsmith graph validate --graph .harness/work-graph.json --json
agentsmith graph status --graph .harness/work-graph.json --json
```

Both accept `--target <repository>` and make no branch, worktree, state, or external write. An
unknown schema, changed committed byte, unsafe path, scope collision, cycle, or unverified child
lineage stops closed. `status` reports each node's reason and one safe next action. Run IDs must be
unique; `integration_order` must name each exactly once. A graph change requires a new graph ID,
not an in-place migration of a running graph.

## Run and recover

`agentsmith graph start --graph .harness/work-graph.json` explicitly authorizes **local** work.
The graph dispatches ready, non-conflicting roots through the normal maker → verifier → checker
controller. Each child retains its own branch, worktree, receipt, attempt cap, original deadline,
and accumulated usage. The graph records only its own dispatch and checkpoint facts under the
repository's Git common directory. It does not edit child state. Independent makers may run
concurrently; Git metadata checks still reject unverified changes to refs, hooks, config, objects,
or other worktrees.

A dependent run starts only after every transitive predecessor is accepted. The graph verifies
their exact commits and checker receipts, merges them in declared order into a graph-owned local
checkpoint, and passes that exact checkpoint OID to the child. A merge conflict retains the
checkpoint worktree and all source branches; it never guesses a base or rewrites a source. Failed
or rejected children block descendants, while unrelated ready nodes may finish.
If a child exits unexpectedly before writing a terminal reason, its graph failure event records
the exit code, last child phase, exception class, and controller source line. It does not copy
raw child output into graph audit state.

To interrupt, use `agentsmith graph stop --graph .harness/work-graph.json`; repeated requests are
safe. It asks active child controllers to stop and retains state, logs, receipts, branches, and
worktrees. `agentsmith graph resume --graph .harness/work-graph.json` checks the pinned graph,
base/checkpoint OIDs, child ownership, liveness, and worktree state before continuing. It refuses
a second live graph controller or a dirty/moved child. Stop/resume never renews a deadline or
attempt/usage allowance. If a process dies between dispatch recording and child-state creation,
resume fails closed for manual reconciliation rather than launching a duplicate run.

## Integrate locally, then decide on delivery

`agentsmith graph integrate --graph .harness/work-graph.json --json` requires all children to have
accepted evidence. It creates a disposable candidate branch/worktree from the pinned contract
commit, incorporates exact source commits in `integration_order`, and runs every phase in the
candidate's `.harness/verify.conf`. The verification receipt and candidate lineage stay in graph
state. A conflict, changed source ref, dirty source, missing receipt, or failing combined check
keeps the candidate and sources for inspection; a retry uses a new candidate name. Success is
still **local**. Push, PR, protected-branch merge, release, deployment, and external tracker
writes each require their own operator authority.

`agentsmith graph cleanup --preview --graph .harness/work-graph.json --json` is read-only and
shows exact retained and eligible paths. `cleanup --apply` is a separate explicit action after
every child is accepted. It removes only verified, clean, graph-owned checkpoint worktrees;
accepted child worktrees and branches, checkpoint refs, graph audit state, candidate evidence,
and foreign/research files stay. A dirty or ambiguous checkpoint blocks cleanup.

## Model advice at agent-assisted setup

Model choice is advice, not a scheduler rule. When an agent helps set up AgentSmith, it may check
the installed Codex or Claude Code runtime and current **official** vendor guidance if online
access is already available. It should name the date and quality-versus-usage trade-off, then
recommend the least resource-intensive option that has met this project's quality bar. Offline,
it should label any suggestion unverified and use the runtime's known local/default choices.
The installer and graph never require network access to choose a model, never auto-escalate to a
costlier one, and never change the model or budget in an accepted manifest. A floating model
alias is not a pinned model version.

## Evidence and limits

`bash scripts/verify.sh` includes these local checks:

| Claim | Evidence | Boundary |
|---|---|---|
| Committed graph inspection makes no execution write | `test-work-graph-status.py` | A clean committed checkout is required. |
| Parallel roots and inherited predecessor code work | `test-work-graph-dispatch.py` | Fake native clients exercise real Git worktrees; no paid model run is implied. |
| Stop/resume keeps limits and refuses drift | `test-work-graph-dispatch.py`, `test-autonomous-graph-base.py` | An interrupted child with missing state needs manual reconciliation. |
| Local integration verifies the combined tree | `test-work-graph-dispatch.py` | Candidate verification does not authorize delivery. |
| Existing finite-run guards still hold | `test-autonomous-state.py`, `test-autonomous-run.sh` | Scope keys coordinate cooperating runs, not untrusted processes. |
| Three native reports describe the same commit and tree | `work-graph-release-evidence.py aggregate`, `test-work-graph-release-evidence.py` | A generated aggregate is required; fixture JSON is illustrative only. |

This is local test evidence, not a claim that arbitrary mutually untrusted makers are isolated:
worktrees share Git metadata and local resources, and declared scope keys coordinate cooperating
runs rather than binding operating-system ports or services. Cross-platform native proof and a
release aggregate must be collected before a Wave 2 portability claim.

## Reproduce the lifecycle fixture

The fixture in `scripts/test-work-graph-dispatch.py` creates a temporary repository with an
accepted spec and three separate manifests. Tickets A and B write different files concurrently.
Ticket C depends on both and checks that their files are present in its starting worktree. The
test calls the shipped `agentsmith graph` CLI for inspection, start, stop, resume, integration,
and cleanup preview. It also checks a conflicting pair, a dirty source, a failed combined
verification, and retention of foreign notes. The fake clients exercise real Git processes and
worktrees without model calls or a remote.

```sh
python3 scripts/test-work-graph-dispatch.py
```

On a committed clean checkout, the native recorder runs the graph contracts, read-only status,
base lineage, CLI surface, coordination and secret-scanner checks, and ten lifecycle tests. It
writes one JSON report outside the repo.
The manual `verify` workflow runs this on macOS, Linux, and Windows, uploads each report even
when a phase fails, then accepts an aggregate only when all three reports passed on the exact
workflow commit and Git tree. Output hashes and test counts are recorded; raw process output is
not uploaded. A failed phase prints only bounded unittest names or a skip marker to CI logs.
The Linux native job and Ubuntu guardrail job install `bubblewrap` and enable unprivileged user
namespaces if AppArmor restricts them. The native job probes the verifier policy before recording
evidence; the guardrail runs the verifier escape test with the sandbox active. This follows
[Bubblewrap's own hosted CI setup](https://github.com/containers/bubblewrap/blob/main/ci/enable-userns.sh).

The native aggregate is an evidence gate, not a delivery command. A successful local
`integrate` leaves a candidate branch, its source commits, and a verification receipt under
`.git/agentsmith-graphs/<graph_id>/`. A human then reviews the candidate and separately decides
whether to push, open a PR, or merge. Observe the result after delivery and file a feedback
entry if an invariant fails; the graph does not do either step automatically.

### One feature through the fixture

The fixture's concrete feature is a composed change set with three independently reviewed
source files. Its accepted temporary spec names decision `DEC-1`. Separate manifests name
`IMP-a`, `IMP-b`, and `IMP-c`; the committed graph gives A and B parallel slots and makes C
depend on both. A writes `src/a/change.txt`, B writes `src/b/change.txt`, and C checks both
inherited files before writing `src/c/change.txt`. The combined verifier requires all three.

The test first calls `graph validate` and `graph status`, then `graph start`. It observes two
overlapping maker starts, a dependency checkpoint, and C's inherited files. `graph integrate`
creates a local candidate from the declared A → B → C order and a passing combined receipt. A
separate test interrupts and resumes the same graph without resetting its limits. Another
retains both accepted sources when integration conflicts. The fixture ends at the local
candidate: a human delivery decision, downstream observation, and any feedback entry are
explicit handoff steps, not events the fixture pretends happened.

### Troubleshooting and release handoff

| Observation | Safe next step |
|---|---|
| `status` says `conflicting` | Inspect the named overlapping path or resource; revise and recommit a new graph ID before starting. |
| Child is `interrupted` or `resume` refuses drift | Read the child state and receipt under the Git common directory; retain worktrees and reconcile the exact missing or moved state. |
| Candidate integration conflicts | Inspect the retained candidate worktree and both source refs; resolve in a new reviewed attempt. |
| Candidate full verification fails | Read `verification-<attempt>/receipt.json`; keep the failed candidate as evidence and fix the source under a separate run. |
| Native report is failed or absent | Inspect the report phase counts and exit code; do not create a release aggregate from partial evidence. |

For release review, hand over the branch commit and tree OIDs, the three native JSON reports,
their SHA-256 values in the aggregate, the full workflow result at that SHA, the local candidate
receipt, and the named security review. The reviewer checks that all match, then requests a
separate delivery decision. After an authorized delivery, observe the real downstream result
and record any defect in the project tracker; that observation cannot be inferred from the
fixture or aggregate.

### Current release boundary

The Windows finite-run verifier now has a classic AppContainer launcher with temporary package-SID
ACL grants and no network capability. The native Windows file, network, and ACL cleanup boundary
passed in the compatibility matrix on `3b44ae4`. A full lifecycle report from each host and a
same-tree aggregate are separate release gates; current results are recorded in PR #36. The
Windows launcher serializes verifier calls while their shared Python and Git ACL grants are
active; parallel makers and graph dispatch remain available. The
work-graph evidence job is manual-only. The macOS fixture uses
`sandbox-exec`; Linux needs `bubblewrap` and permission to create its
namespaces. A missing sandbox is a failing report, never a skipped test or a portability claim.
See [the security review](24-parallel-work-graphs-security.md) for the named threat checks.
