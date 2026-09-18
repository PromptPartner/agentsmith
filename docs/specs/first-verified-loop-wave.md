---
status: accepted
accepted_by: project lead
accepted_at: 2026-09-17
implementation_branch: docs/marketing-foundation
---

# Spec: First Verified Loop implementation wave

## Destination

Ship one coherent AgentSmith product wave that lets a person move from an unfamiliar repository to
an understandable, repeatable, and inspectable completion loop:

> **Understand the active setup → choose the work profile → configure relevant checks → complete one
> bounded change → prove the real result → save a clean continuation point.**

The wave ends with updated product documentation and one reproducible public proof demonstration.
It does not end when the local code merely appears to work.

This is the first implementation of the approved promise:

> **Your AI agent is capable. Prove the result.**  
> **Proof before done.**

The primary path serves a technically curious professional completing a first responsible coding
task. The experienced-developer path reaches the same controls with less explanation.

## Why this is one wave

Adaptive verification alone would still leave the user unsure which installation and profile are
active. A status command alone would describe a system without helping the user prove a result. A
sandbox without continuity would teach a one-session trick. Marketing any one piece separately
would repeat the problem AgentSmith is meant to solve: a correct layer with a broken end-to-end
chain.

The unit of value is therefore the complete verified loop, delivered through atomic slices.

## Approved strategic inputs

- [`../marketing/11-strategic-marketing-framework.md`](../marketing/11-strategic-marketing-framework.md)
  is the marketing source of truth.
- [`agentsmith-next-stage.md`](agentsmith-next-stage.md) remains the wider product roadmap. This
  focused spec defines the next releasable vertical slice.
- [`../03-verify-means-evidence.md`](../03-verify-means-evidence.md) defines the evidence model.
- [`../07-how-to-pick-a-profile.md`](../07-how-to-pick-a-profile.md) defines current profile
  semantics.
- [`../21-autonomous-runs.md`](../21-autonomous-runs.md) remains the boundary for finite unattended
  work. This wave does not replace its controller.
- [`../research/agentic-coding-user-struggles-2026.md`](../research/agentic-coding-user-struggles-2026.md)
  supports the beginner and verification problem framing.

## User-visible outcome

After this wave, a new user can answer six questions without reading AgentSmith's source code:

1. Which AgentSmith installation and instruction sources affect this project?
2. Which work profile is active, and why does it fit this task?
3. Which automated checks are configured, which are only suggested, and what remains uncovered?
4. What exact task is the agent allowed to change?
5. What evidence proves the visible result—not merely one internal layer—works?
6. How can a fresh session continue without reconstructing the old conversation?

An experienced user can obtain the same answers as structured JSON and move directly to the
relevant command.

## Release boundary

### In scope

- Read-only verification discovery and a coverage report.
- Explicit application of safe, inspectable verification recommendations.
- One active-state view derived from existing global and project state.
- Explainable profile listing, recommendation, and safe switching.
- A cross-platform, disposable first-loop sandbox.
- One obvious handoff-to-resume path.
- Beginner and experienced documentation routes.
- A reproducible public demonstration with evidence artifacts.
- Cross-platform fixtures, behavioral evaluation, migration guidance, and claim updates.

### Out of scope

- Typed multi-ticket work graphs, automatic parallel dispatch, or an integration train.
- Remote tracker synchronization, pull-request creation, pushing, merging, deployment, or release
  publication.
- Hosted coordination, a dashboard, a database, or a workflow language.
- A universal office-work verification detector. This wave detects common software stacks first;
  office recipes remain a subsequent slice.
- Automatic execution of commands copied from continuous-integration files, package scripts, or
  Makefiles during discovery.
- A claim that three observed beginners have validated the path. The product may call the sandbox
  “guided”; “beginner-proven” waits for the planned observations.
- The PromptPartner presentation itself. Its structure may be planned in parallel, but production
  follows the verified product and proof assets.
- A version-number decision. The wave receives a version only during release preparation.

## Product contracts

### 1. Existing state remains authoritative

`.agentsmith/state.json` remains AgentSmith's managed ownership and installation record. The wave
does **not** add `.agentsmith/project.json` or another overlapping state file.

Effective state is derived from:

- the project installation manifest;
- the global installation manifest, when present;
- actual instruction sources and their generated markers;
- active profiles recorded by the project installation;
- managed capability ownership;
- `.harness/verify.conf`; and
- observed drift or duplication.

Derived status is never written back merely because it was inspected.

### 2. Status is one read-only mental model

Add:

```text
agentsmith status [--target PATH] [--json]
```

Human output uses this order:

1. **Topology:** self-contained project, layered global core + project profile, global only,
   incomplete, legacy, or unmanaged.
2. **Active profiles:** names, source, and one-line purpose.
3. **Instruction chain:** global → project → generated adapters, including duplication or drift.
4. **Managed capabilities:** safety, skills, Model Context Protocol (MCP), hooks, runtime, and owned
   files summarized rather than dumped.
5. **Verification:** configured phases, detected coverage, and important gaps.
6. **Next action:** exactly one safest useful command, with the reason before it.

`--json` emits a versioned schema and absolute paths for tooling. Human output may use relative paths
when that is easier to read.

`doctor` remains the detailed diagnostic surface. `status` is not a second doctor; it composes the
existing facts into a beginner-readable explanation.

### 3. Profile operations reuse the installer

Add:

```text
agentsmith profiles list [--json]
agentsmith profiles recommend [--target PATH] [--json]
agentsmith profiles switch --target PATH --profile NAME[,NAME...] [--dry-run]
```

Rules:

- Recommendation is deterministic and explains the evidence used. It never calls a model.
- Ambiguous repositories may receive two ranked choices with trade-offs; they do not receive a
  fabricated certainty score.
- Switching reuses the existing installer, managed blocks, backups, ownership manifest, safety,
  selected agents, identity, tracker settings, and installed capabilities. There is one write path.
- `--dry-run` reports every managed file that would change and every foreign surface preserved.
- The default mutating command changes only AgentSmith-owned surfaces and writes the updated profile
  selection to the existing installation manifest.
- A switch never overwrites a hand-written verification configuration. It reruns coverage analysis
  and reports which new profile gates are unrepresented.
- Unsupported or over-budget profile stacks fail before the first write.

### 4. Verification discovery is read-only by default

Extend the existing command without breaking `agentsmith verify`:

```text
agentsmith verify discover [--target PATH] [--json] [--save PLAN]
agentsmith verify apply --plan PLAN [--target PATH] [--dry-run]
agentsmith verify                         # unchanged execution behavior
```

If argparse compatibility makes a nested command unsafe, implement equivalent explicit flags while
preserving these semantics. The public documentation must expose one form only.

Discovery:

- reads repository files but runs no project command;
- detects common Python, Node.js, Go, Rust, shell, and documentation signals;
- reads existing `.harness/verify.conf` and classifies configured phases;
- treats continuous-integration and task-runner commands as **evidence and hints**, never automatic
  executable recommendations;
- recommends only commands produced by allow-listed detectors with explicit source evidence;
- reports monorepo or mixed-stack ambiguity instead of silently choosing one root;
- distinguishes `configured`, `recommended`, `manual`, `missing`, and `not-applicable` coverage;
- separates automated checks from real-path exercise and judgment-based evaluation; and
- names what a proposed configuration would still not prove.

The versioned plan schema contains at least:

```json
{
  "schema_version": 1,
  "target": "absolute path",
  "generated_at": "UTC timestamp",
  "detected_stacks": [],
  "evidence": [],
  "existing_phases": [],
  "proposed_phases": [],
  "coverage": {},
  "unresolved": [],
  "warnings": []
}
```

Every proposed phase records its category, label, command, detector, source path, reason, confidence
class, and whether explicit review is required.

Apply:

- validates schema, target binding, and a hash of relevant discovery inputs;
- refuses a stale or cross-project plan;
- performs no command execution;
- shows the proposed `.harness/verify.conf` diff on `--dry-run`;
- backs up an existing file;
- replaces the untouched generated `unwired` placeholder automatically only after explicit apply;
- preserves existing user phases and comments;
- requires explicit conflict resolution when a proposed label collides with different content;
- never turns CI YAML, Makefile recipes, or arbitrary package-script bodies into trusted shell text;
  and
- writes enough provenance comments for a human to understand where each managed proposal came
  from without making the config unreadable.

### 5. Coverage has a stable vocabulary

Software discovery reports these cells even when empty:

| Coverage cell | Meaning |
|---|---|
| Build | The deliverable can be produced |
| Type check | Static contract checks where the stack supports them |
| Lint/static analysis | Code-quality or static defect checks |
| Unit/integration tests | Deterministic behavior inside and between code layers |
| Dependency risk | Known high/critical vulnerability check where available |
| Secret scan | Tracked or changed content receives secret detection |
| Real-path exercise | The changed behavior is invoked at the last user-visible or downstream layer |
| Judgment evaluation | A rubric, independent review, or human inspection covers non-binary quality |

The report says **uncovered**, not **failed**, when no check exists. It says **unverified**, not
**unsafe**, when evidence is absent.

### 6. The first-loop sandbox is disposable and understandable

Add a bundled template and initializer:

```text
agentsmith demo first-loop --target PATH
```

The command:

- requires a new or empty target directory;
- writes only below that explicit target;
- performs no network access and installs no dependency;
- creates a Git repository only when Git is available and the user explicitly accepts the
  documented command path;
- uses Python 3.11+ standard-library code, matching AgentSmith's own runtime requirement;
- prints the next three steps and the rollback/delete boundary; and
- can be recreated deterministically for repeated demonstrations.

The scenario is a small **launch-readiness checker** with an intentional, visible logic defect: it
reports a project as ready when only some required checks pass. The accepted task changes the logic
from “any check passes” to “all required checks pass.”

Why this scenario:

- a non-developer can understand the error immediately;
- it mirrors AgentSmith's evidence promise without requiring product-specific knowledge;
- the failing test, fix, command-line invocation, and final result are visible;
- it needs no package manager, browser driver, account, or external service; and
- it is safe to discard and repeat.

The template contains:

- a short `README.md` with the human goal;
- `readiness.py` with the intentional baseline defect;
- a small fixture representing passed and failed launch checks;
- a test that fails for the intended reason;
- a configured `.harness/verify.conf` covering syntax, tests, and the real command-line path;
- an accepted-task template with outcome, non-goals, affected scope, and acceptance checks; and
- a recovery exercise that demonstrates the Git checkpoint without asking the user to memorize Git
  internals.

The AgentSmith repository's own tests assert that the copied baseline fails for the named reason.
An intentionally broken example must never be mistaken for a repository regression.

### 7. Continuity has an obvious resume command

Keep `agentsmith handoff [item-id]` as the write path. Add:

```text
agentsmith resume [HANDOFF_FILE] [--target PATH] [--json]
```

With no file, it selects the newest handoff in `.harness/handoffs/`.

The command is read-only. It:

- validates that the note contains the required sections;
- warns when scaffold placeholders remain;
- compares recorded branch and commit with current state without changing either;
- reports uncommitted-state drift;
- prints the exact handoff path and next read-only recovery command;
- emits a paste-ready fresh-chat kickoff prompt; and
- never checks out, resets, stashes, commits, or edits the note.

The first-loop guide requires one stop and fresh-session resume so continuity is exercised rather
than merely described.

## Command journey

The beginner path is shown as decisions, not an unexplained command wall:

```text
agentsmith demo first-loop --target <new-directory>
agentsmith status --target <new-directory>
agentsmith profiles recommend --target <new-directory>
agentsmith verify discover --target <new-directory> --save <plan-path>
agentsmith verify apply --target <new-directory> --plan <plan-path> --dry-run
agentsmith verify apply --target <new-directory> --plan <plan-path>
agentsmith verify --target <new-directory>
agentsmith handoff first-verified-loop --target <new-directory>
agentsmith resume --target <new-directory>
```

The final documentation may shorten the path by preconfiguring the sandbox. It must still teach the
same mental model: inspect, choose, discover, review, apply, verify, hand off, resume.

The experienced path starts with `status --json`, `verify discover --json`, or the relevant dry run
and links directly to the schemas and ownership rules.

## Failure and recovery contract

| Situation | Required behavior |
|---|---|
| No stack detected | Preserve existing config; report manual coverage cells and one next action |
| Several stacks detected | Show each root and refuse automatic composition until reviewed |
| Existing custom verification | Preserve it; offer additive recommendations and surface collisions |
| Stale discovery plan | Refuse apply and name the changed input |
| Unsupported command or tool absent | Keep the recommendation visible but do not mark it configured or proven |
| Global/project duplication | Explain both sources, token duplication, and the exact safe migration path |
| Legacy install without manifest | Reconstruct only what current ownership logic can prove; label uncertainty |
| Profile switch conflicts with foreign content | Preserve foreign content and stop before partial writes |
| Sandbox target is non-empty | Refuse before writing |
| Sandbox baseline unexpectedly passes | Fail its fixture test; the teaching contract has regressed |
| Handoff is incomplete | Resume prints the missing fields and refuses to call it ready |
| Recorded branch or commit differs | Warn and explain; never change Git state automatically |

## Work graph

### FVL-01 — Freeze schemas and red tests

**Outcome:** Status, discovery-plan, coverage, profile, demo, and resume contracts are executable
tests before implementation.

**Primary files:** new focused tests plus JSON fixtures; minimal parser registration needed only to
demonstrate the expected red state.

**Acceptance:** every new capability has a test that fails for the right missing behavior; backward
compatibility tests prove existing `install`, `doctor`, and `verify` invocations remain unchanged.

### FVL-02 — Verification discovery and safe apply

**Depends on:** FVL-01.

**Outcome:** common software repositories receive an evidence-backed coverage map and reviewable
configuration proposal without executing project code.

**Acceptance:** Python, Node.js, Go, Rust, shell, mixed-stack, monorepo, custom-config, stale-plan,
malicious-hint, Unicode-path, and Windows-command fixtures pass. A real disposable fixture moves
from `unwired` to configured and fails on its intentional defect.

### FVL-03 — Active status and profile operations

**Depends on:** FVL-01; integrates FVL-02 coverage output.

**Outcome:** one command explains effective topology and profile state; profile recommendation and
switching are inspectable and reversible.

**Acceptance:** fresh, global-only, self-contained, layered, duplicate-core, legacy, drifted,
multi-profile, and foreign-content fixtures pass. A dry-run and actual switch produce the predicted
managed diff and preserve foreign bytes.

### FVL-04 — Disposable first-loop sandbox

**Depends on:** FVL-01. May run in parallel with FVL-02 because its template and tests do not share
the discovery implementation.

**Outcome:** one command creates the reproducible launch-readiness scenario and explains the next
step.

**Acceptance:** creation is deterministic; non-empty targets fail before writes; the baseline test
fails for the intentional `any` versus `all` defect; the corrected fixture passes automated and
real-path checks on macOS, Linux, and Windows test environments.

### FVL-05 — Handoff and resume continuity

**Depends on:** FVL-01. May run in parallel with FVL-04.

**Outcome:** a completed handoff becomes a validated, paste-ready continuation point.

**Acceptance:** latest selection, explicit-file selection, incomplete notes, branch drift, commit
drift, dirty worktree, Unicode path, no-Git directory, and Windows path fixtures pass. The command
performs no Git or file mutation.

### FVL-06 — Integrate the complete loop

**Depends on:** FVL-02 through FVL-05.

**Outcome:** a clean-room sandbox run follows the documented command journey from initialization to
fresh-session resume.

**Acceptance:** one concrete value—the failed readiness check—travels from fixture through status,
coverage, failing verification, bounded fix, passing verification, real CLI output, receipt,
handoff, and resume. Each transition retains its evidence.

### FVL-07 — Documentation and public proof

**Depends on:** FVL-06.

**Outcome:** README and docs match the shipped product, and a reader can inspect or repeat the
complete demonstration.

**Deliverables:**

- revised README opening and calls to action;
- separate guided and experienced quick paths;
- updated first-hour, first-loop, profile, verification, troubleshooting, built-in, and glossary
  documentation;
- one architecture/flow diagram;
- `docs/demos/first-verified-loop/` with the exact runbook, red/green outputs, receipt, real-path
  output, handoff/resume proof, and current limitations;
- installation lifecycle demonstration for a clean and existing-config fixture;
- compatibility evidence links; and
- an honest claim map showing which launch statements are now supported.

**Acceptance:** local links resolve, documentation renders, every command is run from a clean copy,
the public artifacts contain no secret or operator path, and an independent reviewer can reproduce
the loop from the runbook.

### FVL-08 — Release evidence and handoff

**Depends on:** FVL-07.

**Outcome:** the wave is ready for review as one atomic product promise.

**Acceptance:** full repository verification passes; native operating-system fixtures pass; new
dependency audit is not applicable because the implementation remains standard-library only;
security review names command-injection, path traversal, symlink escape, plan tampering, secret
redaction, foreign-file preservation, and Git-state safety; the final receipt and handoff are
written after the last change.

## Parallel execution plan

Parallelism is useful only where file ownership and contracts are stable.

| Lane | Work | Start | Shared-file rule |
|---|---|---|---|
| Contract lane | FVL-01 and public schemas | First | Owns parser/API decisions |
| Verification lane | FVL-02 | After FVL-01 | Owns verification implementation and focused tests |
| Sandbox lane | FVL-04 | After FVL-01 | Owns template/demo files and demo tests; no edits to verification core |
| Continuity lane | FVL-05 | After FVL-01 | Owns handoff/resume tests and helper code; coordinate parser edits once |
| Operability lane | FVL-03 | After discovery output stabilizes | Owns status/profile implementation; does not rewrite discovery schema |
| Documentation lane | FVL-07 outline early, final copy after FVL-06 | Parallel where commands are already frozen | Never documents an unverified command as shipped |

Because `agentsmith.py` is currently a monolith, two lanes must not edit it concurrently. Worktrees
are used for file isolation, not as permission to create merge conflicts. Core CLI changes are
sequenced or integrated through one owner; template, test-fixture, research, and documentation work
can run in parallel when their paths are disjoint.

## Commit and integration plan

Each FVL item is one or more atomic commits. The reason appears in the commit message. Suggested
boundaries:

1. test contracts;
2. verification discovery;
3. verification apply and security boundaries;
4. status/profile read model;
5. profile mutation path;
6. sandbox template;
7. resume helper;
8. integrated loop;
9. documentation and proof assets; and
10. release evidence.

Do not squash research or proof artifacts out of history. No lane pushes, merges, publishes, or
writes to a remote system without explicit authority.

## Security review requirements

- Discovery must never execute repository content.
- Plan application must bind the plan to the target and discovery inputs.
- Every target path must be explicit, resolved, inside its allowed root, and protected against
  symlink redirection.
- Shell commands written to verification config come only from reviewed detectors or explicit user
  content already present in that config.
- Foreign configuration and comments are preserved byte-for-byte where they are outside managed
  content.
- Human-readable and JSON output must not expose secrets, authentication state, or operator home
  paths in public evidence.
- `resume` is read-only and cannot become a hidden Git recovery command.
- Demo initialization refuses broad, unresolved, home, repository-root, or non-empty destructive
  targets.

## Verification ladder

1. **Red:** each behavior begins with a focused failing test.
2. **Green:** smallest implementation makes the focused test pass.
3. **Regression:** the full 24-phase repository gate passes after each atomic slice.
4. **Cross-platform:** existing macOS/Linux/Windows fixtures cover every filesystem and command
   boundary introduced by the slice.
5. **Real path:** run the installed CLI from a disposable project rather than importing internal
   functions only.
6. **Behavioral:** evaluate friendly collaborative tone, plain international English, reason before
   command, abbreviation expansion, and useful step order for the guided path.
7. **Independent review:** a fresh checker attempts to reject the complete loop against this spec.
8. **Public reproduction:** repeat the documented demonstration from a clean copy and record the
   evidence after the final change.

## Definition of done

The wave is complete only when all of the following are true:

- [ ] `agentsmith status` explains effective state and gives one safe next action.
- [ ] Profile recommendation and switching are explainable, dry-runnable, reversible, and preserve
      foreign content.
- [ ] Verification discovery produces a useful coverage map without executing repository code.
- [ ] Applying a reviewed plan safely configures the sandbox and preserves custom verification.
- [ ] The baseline sandbox fails for the intended reason and the corrected task passes the full
      configured gate.
- [ ] The visible readiness result is exercised through the real command-line path.
- [ ] A handoff is created and a fresh session can resume through the read-only helper.
- [ ] Guided and experienced documentation paths are accurate and rendered.
- [ ] The public demonstration contains reproducible evidence and explicit limits.
- [ ] Marketing claims are updated only where the new evidence supports them.
- [ ] Full verification and security review pass after the last change.
- [ ] No external publish, push, merge, or deployment occurred without explicit authorization.

## Deferred waves

### Wave 2 — Parallel development and integration

Resolve the orchestration contract, then add the typed work graph, scheduler over existing finite
runs, deterministic local integration train, and long-term agent-native development lifecycle.

### Wave 3 — Office and extension development paths

Ship the `agent-extension-dev` profile and tested office-work recipes after status/profile switching
and adaptive verification provide a clear base.

### Wave 4 — Presentation and launch production

Use the PromptPartner brand skill and the verified proof artifacts to produce the minimalist
presentation, diagrams, founder content, and channel-specific launch package. Planning may overlap
this wave; final claims and screenshots may not precede FVL-07 evidence.

### Wave 5 — AI Admin Panel bridge

Design and verify the future recommended hosting and operating path only after the local development
loop and its ownership boundaries are proven.

## Exact first implementation action

Create FVL-01 as focused failing tests and versioned fixture schemas. Do not implement commands in
the same commit. The first red suite must prove that current AgentSmith lacks:

- the read-only status schema;
- verification discovery and safe plan application;
- deterministic profile recommendation/switch behavior;
- sandbox initialization; and
- read-only handoff resume.

Only after those failures are observed for the intended reasons should implementation begin.

