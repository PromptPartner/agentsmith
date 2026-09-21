# Work-graph security review — W2-06

Reviewed 2026-09-21 against `cd531eeddcdae674863fa43dbf354495ee4ad219` plus the local
W2-06 diff. This review names the mechanism and check for every required category. The native
aggregate remains unproven until the final committed tree has three passing host reports.

| Category | Boundary and evidence | Limit |
|---|---|---|
| Command injection | Graph CLI builds child and Git processes with argument arrays; `test-work-graph-status.py` rejects unsafe manifest paths. | The verifier shell command is trusted, accepted manifest content. |
| Path traversal | `work_graph.py` validates graph, manifest, state, and cleanup paths; `test-work-graph-contracts.py` and `test-work-graph-status.py` reject traversal. | Review is for graph-owned paths. |
| Symlink escape | Graph state and stop paths reject symlinks; `test-work-graph-status.py` exercises an outside target. | Windows symlink availability varies; a skipped native check cannot satisfy the aggregate. |
| Plan/state tampering | Pinned graph and manifest hashes plus contract commit are rechecked on resume; `test-autonomous-graph-base.py` and `test-work-graph-dispatch.py` change them and observe refusal. | Manual recovery remains necessary after ambiguous partial state. |
| Ref mutation | Child metadata snapshots and checker/writer leases constrain protected refs; `test-autonomous-state.py` checks the lease and peer cases. | Local cooperating processes share one Git common directory. |
| Config/hook mutation | `git_metadata` compares protected Git configuration and hooks around child roles; `test-autonomous-run.sh` checks mutation refusal. | POSIX guardrail test; Windows native lifecycle remains open. |
| Generated Git server-info cache | A syntactically valid `.git/info/refs` is treated as a derived, non-authoritative cache during concurrent commits; malformed content still fails the protected metadata check. A linked-worktree regression proves both cases. | A repository served by dumb HTTP should regenerate its cache before publication. |
| Object-store mutation | Existing object hashes and new object paths are checked; `test-autonomous-state.py` covers transient lock handling and `test-autonomous-run.sh` covers tampering. | Git maintenance can require bounded waiting. |
| Secret redaction | Native reports store only output hashes, counts, command names, and Git identifiers; `test-secret-scan.py` is in the full repository gate. | Local child logs can contain model output and need normal access controls. |
| Foreign-file preservation | Cleanup previews ownership and refuses dirty paths; `test-work-graph-dispatch.py` retains a foreign research note. | Explicit cleanup only removes verified graph-owned checkpoint worktrees. |
| Cross-worktree interference | Scope/resource collisions wait, and Git phases serialize checker/writer operations; `test-work-graph-status.py` and `test-autonomous-state.py` exercise both. | Scope keys are cooperation, not operating-system isolation. |
| Source retention | Conflict and failed integration keep source branches and worktrees; `test-work-graph-dispatch.py` checks both. | Operator must still preserve research during later manual Git operations. |
| Authority boundary | Integration creates a local candidate and receipt with `external_write_used: false`; the fixture checks there is no remote. | Push, PR, merge, and release require separate human authority. |

**Named result:** the local mechanisms and regression checks above were inspected. The
Windows AppContainer passed its native file, network, and exact ACL cleanup test on `3b44ae4`.
The cross-platform release security claim requires a passing same-commit/tree native aggregate;
the compatibility boundary test alone does not establish it. The recorder rejects failed, dirty,
partial, skipped, or mismatched reports; synthetic aggregate tests establish those rules, not
native portability. In the aggregate, `security_coverage` names this review's categories and
`external_write_used: false` is a declaration supported by the no-remote fixture check; neither
field is independent network or filesystem telemetry. The full workflow gates and the manual
review remain necessary for a release decision.
