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

This is local test evidence, not a claim that arbitrary mutually untrusted makers are isolated:
worktrees share Git metadata and local resources, and declared scope keys coordinate cooperating
runs rather than binding operating-system ports or services. Cross-platform native proof and a
release aggregate must be collected before a Wave 2 portability claim.
