# Michael Shimeles skills assessment

> Source material is retained under R9. If this note becomes obsolete, move it to
> `docs/research/_archive/`; do not delete it.

## Question / scope

Which ideas in `michaelshimeles/skills` can sharpen AgentSmith's deterministic verification and
finite autonomous-run isolation without importing an unlicensed implementation, adding network
coordination, or widening the harness's tool surface?

The assessment is pinned to commit
[`5d403ea66775c04df222a1e9b302ef64ae45c712`](https://github.com/michaelshimeles/skills/commit/5d403ea66775c04df222a1e9b302ef64ae45c712).

## Sources consulted

Opened on 2026-09-02:

- [`evidence-driven-testing/SKILL.md`](https://github.com/michaelshimeles/skills/blob/5d403ea66775c04df222a1e9b302ef64ae45c712/evidence-driven-testing/SKILL.md)
  — the evidence workflow, artifact manifest, revision/environment binding, redaction cautions,
  headless alternatives, and recorder test claim.
- [`new-feature/SKILL.md`](https://github.com/michaelshimeles/skills/blob/5d403ea66775c04df222a1e9b302ef64ae45c712/new-feature/SKILL.md)
  — worktree isolation, changed-file overlap checks, and the warning that ports, databases, and
  dependency lockfiles remain shared.
- [Pinned repository tree](https://github.com/michaelshimeles/skills/tree/5d403ea66775c04df222a1e9b302ef64ae45c712)
  — repository layout, root licensing files, and test surface.

## Findings

### Ideas adapted

**Durable evidence tied to the tested state.** The evidence skill produces a manifest and report
alongside its capture, names the exact commit/branch or deployment, and records the environment and
assertions. AgentSmith adapts that provenance principle into an opt-in `agentsmith verify` command
receipt: deterministic phase output, timestamps, exit codes, hashes, verification-config identity,
Git state, and runtime environment. Secret-shaped output is redacted before display or persistence.
The receipt does not claim to contain runtime or visual proof; screenshots, videos, manual
assertions, and publishing remain separately referenced evidence.

**Isolation must cover collisions outside a worktree.** The new-feature skill checks whether open
pull requests touch the same files and explicitly warns that worktrees do not isolate ports or
databases. AgentSmith adapts the collision model to finite local controllers: conservative fixed
prefixes derived from declared path globs plus explicit local resource keys are checked under a
repository-wide coordination lock. This is local coordination only, not operating-system-level
resource isolation.

### Components rejected

- The FFmpeg recorder, video encoding, screenshots, Playwright capture, annotations, and media
  upload workflow are outside deterministic command receipts and would add dependencies.
- Posting to pull requests or trackers is outside the local-only verification boundary and would
  require separate external-write authorization.
- `git fetch`, `gh pr list`, and `gh pr diff` make collision checks depend on network state and open
  pull requests. The controller instead checks live local controller state.
- The upstream branch naming, dependency installation, worktree cleanup, and force-deleting local
  branches are broader lifecycle policy than this change needs.

### Licensing and test caveats

The pinned repository root contains no `LICENSE`, `LICENSE.md`, or `COPYING` file. Folder-specific
licenses for vendored components do not establish a repository-wide license for these two skills.
For that reason, only concepts were studied and the implementation was written independently.

The pinned tree contains `tests/test_evidence.py`, described upstream as a synthetic-source smoke
test for the recorder. It does not validate real visual sessions, publishing, or the `new-feature`
worktree procedure; no tests for that procedure appear in the pinned tree. AgentSmith therefore
relies on its own cross-platform receipt suite and autonomous-controller integration/state tests.

## Open questions / what was not checked

- Later upstream commits were intentionally excluded; this assessment describes only the pinned
  snapshot.
- Real recorder behavior, display permissions, media uploads, and authenticated GitHub operations
  were not executed because none is part of the adaptation.
- The absence of a root license is an observation about the pinned tree, not legal advice or a
  claim about rights the author may grant elsewhere.
