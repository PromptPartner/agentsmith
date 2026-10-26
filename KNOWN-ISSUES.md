# Known issues

This file records open defects and fixes found during verification. No external tracker write has
been authorized, so the entries are kept here.

- [ ] 2026-10-20 — Native Windows `test_deleted_git_lock_does_not_fail_acl_cleanup` failed once
  with `verifier did not start` in verify run `39429936983`, attempt 1, job
  `compatibility (windows-latest)`, on master `d56a0d5`. Attempt 2 on the same commit passed, and
  v0.4.0 was released from that commit. The test waits 30 seconds for the sandboxed verifier's
  start marker but never reads the verifier's own result, so the log shows no cause. Candidates:
  the AppContainer setup took longer than the 30-second wait on a loaded runner (the verifier's
  own timeout is also 30 seconds), or the verifier exited early with an error. The failure message
  now says which: still running after the wait, or the exit code and stderr (or the exception) of
  a verifier that ended. The next native failure will name the cause.
- [ ] 2026-10-19 — The native Windows work-graph lifecycle failed intermittently in three different
  tests on trees whose push runs passed. Pull-request run `38178585204` on `23e5889`, attempt 1:
  graph `start` read a child `state.json` while the child replaced it atomically and got
  `PermissionError` (Errno 13). Attempt 2: a child verifier's sandbox failed `GetFileSecurityW`
  with Windows error 5 on `.git/agentsmith-runs/coordination.lock` while the parallel child removed
  it, and the run escalated. PR #44 changed neither path. Master run `38182506232` on `0901316`:
  `test_stop_then_resume_preserves_partial_work_and_limits` failed because child `a` refused to
  resume (`exit=2 in making; exception=error`). Graph evidence kept no refusal text, so the cause
  is unknown. Fixed now, each with a test that failed first: `_child_state` retries Windows sharing
  denials within the controller's 5-second bound. The sandbox's DACL snapshot and restore re-check
  error 5 for the same bound, skip a file that is then gone, and still fail closed on a lasting
  denial; the 2026-09-21 fix below covered only errors 2 and 3. The sandbox tests replay Windows
  error codes, so they run on every operating system. A graph failure event now names a known
  controller refusal with a fixed code, such as `refusal=previous-role-live`,
  `refusal=dirty-worktree` or `refusal=scope-conflict`, and never copies the refusal text. Still
  open: the stop-then-resume refusal. Candidates are a role still live after `stop` (Windows ends
  the controller with `TerminateProcess`, so no handler records the interruption), a scope
  conflict with the sibling resumed in parallel, and a dirty worktree. The next native failure
  will report its refusal code. Native Windows confirmation of all three fixes is pending.
  An independent review of this fix found an older leak in the same function: any
  identifier-shaped word that started the child's last stderr line, such as
  `ghp_attackerSecret123: …`, became the `exception=` label in graph evidence. The 2026-09-22
  crafted-label hardening covered only a test helper. Fixed: the label is now a Python exception
  name or one of the controller's own prefixes, and anything else is `unknown`.
- [ ] 2026-10-02 — German, Spanish, French, and Simplified Chinese manual-setup instructions
  describe signed installers, while the English README states macOS and Windows standalone builds
  are unsigned. `INSTALL.md` and `AGENT-INSTALL.md` also promised signed downloads checked against
  `SHA256SUMS`, but no GitHub release had any assets. On 2026-10-19 the setup text in every
  language and the standalone update message were corrected: builds are unsigned, and users check
  `SHA256SUMS` and the build attestation. The standalone workflow now drafts a release with five
  archives and `SHA256SUMS` for each `v*` tag (`RELEASING.md`). Downloads appear with the next
  tagged release. macOS and Windows platform code signing remains open.

- [ ] Project-scoped install writes Claude's user-global `permissions.defaultMode` through
  `install_native_config()`; the default `--safety cautious` therefore changes the user's global
  mode to `acceptEdits` from a project operation.
- [ ] Project install appends a generated block to an existing unmarked `CLAUDE.md` and also adds
  `AGENTS.md`, leaving two authoritative instruction rulebooks in one repository.
- [ ] A contained symlink added inside an AgentSmith-owned `.claude/skills` adapter is detected by
  strict Doctor and repaired by ordinary reinstall, but staged update fails closed because plan
  receipts cannot yet authenticate deletion and exact rollback restoration of symlink metadata.
- [ ] `agentsmith verify discover --help` and `verify apply --help` currently show the shared
  verification parser's execution-only options; incompatible combinations fail clearly, but the
  subcommand help should expose only each operation's valid flags.
- [ ] 2026-09-22 — A local macOS `agentsmith verify` run failed at the parallel work-graph
  lifecycle fixture when a child snapshot classified transient `packed-refs.lock` as protected
  Git metadata. Both child worktrees were clean afterward. The focused fixture and the full
  31-phase gate passed on rerun. The exact writer and safe snapshot exclusion need diagnosis.
- [ ] 2026-09-21 — Hosted macOS native lifecycle intermittently failed its cleanup-preview test
  in run `35607452415`, although the same suite passed in that run's compatibility job and in
  five local targeted attempts. Run `35605909782` had passed both paths. The exact failing
  assertion is not yet known. A later docs-only push run `35610061317` failed in the macOS
  compatibility copy when graph `start` returned a failed state inside a different cleanup test;
  its pull-request copy passed. Run `35616698843` failed the stop/resume test because a maker
  reported changed existing Git objects. The test now prints child reasons and graph events, and
  the controller will include changed object paths in the next native failure for diagnosis.
  Eight repeated local stop/resume runs passed after that diagnostic change; the macOS
  compatibility lifecycle also passed on `4b42582` and again in both push and PR CI on `2cca50e`.
  Manual run `35646692896` passed both macOS paths on `b331612`, but the original
  failure artifact records only the test name and output hash, so its assertion and root cause
  remain unknown. Push run `35651017175` later failed the macOS stop/resume fixture: both
  child controllers saw the same eight previously loose Git objects disappear while their
  maker snapshots were active. Git can repack loose objects during automatic maintenance;
  the role environment now disables both `gc.auto` and `maintenance.auto` without changing
  repository config. A passing same-tree native rerun is the release gate for this mitigation;
  the original cleanup-preview assertion remains unknown. On 2026-09-22, eight bounded
  cleanup-preview reruns under the native recorder's stripped environment passed on macOS.
  The recorder now retains only the failing test name, phase, source line, and exception type
  in a failed report, so the next native failure can identify the assertion without leaking
  traceback paths or output. Manual workflow run `35697924409` passed the macOS native and
  compatibility lifecycle on commit `13bfb84`; its hosted aggregate accepted all three native
  reports from tree `a9e84ec`. The original failure did not recur, so keep this issue open
  until its failing assertion is captured.
- [ ] 2026-09-21 — PR run `35641860248` exposed a macOS false negative in the new Git
  text-conversion regression: `git status` sometimes trusted cached index metadata immediately
  after the test changed `core.autocrlf`, so it reported a clean worktree even though the
  controller would hash different bytes. The regression now compares the filtered worktree
  blob with the committed blob directly; native confirmation remains pending.
- [ ] 2026-09-21 — The same PR run failed a Windows graph stop fixture because it waited for
  any of two parallel makers to log a start but then required `repo-a` to exist. Maker `b` can
  start first, so a stop before `a` creates its worktree is valid. The fixture now checks
  retention for every maker that actually logged a start; native confirmation remains pending.
- [x] 2026-10-19 — Pull-request run `39275474565` (PR #56, attempt 2) failed native Windows
  `test_parallel_roots_and_dependent_checkpoint` with `1411.665 not less than 1411.569`: the
  two root children never overlapped. The fake maker slept a default 1 s, shorter than the gap
  between dispatching the two roots on a loaded Windows runner. A 0.01 s maker reproduced the
  same assertion on macOS. Fixed: the test gives each maker 4 s, as its sibling tests do. The
  product dispatch was not at fault.
- [ ] 2026-09-21 — Final-tree manual run `35623269366` passed Linux and macOS native work-graph
  lifecycle but failed eight of ten Windows dispatch tests. The Windows report binds commit
  `00461bf`, tree `8d0c00f`, and records a clean checkout; its lifecycle phase exited 1.
  Compatibility previously tested the Windows boundary but did not expose dispatch test errors.
  The diagnostic run `35624368777` showed `graph differs from committed contract bytes` before
  any child started. The fixture wrote graph JSON as platform text, so Windows CRLF bytes differed
  from Git's normalized LF commit. It now writes exact LF bytes and asserts the working and
  committed contract match. Push run `35625206301` reached the Windows lifecycle and exposed a
  60-second fixture timeout, a stale-PID probe that called `os.kill` on Windows, another CRLF
  contract write in the integration-conflict case, and two maker retries after verifier rejection.
  The fixture now allows a bounded 180-second graph call, uses an out-of-range stale PID, writes
  the conflict graph as LF bytes, and prints verifier receipts on failure. Push run
  `35627080730` reduced the suite to
  three failures: a child controller disappeared before state reconciliation, a failed-node test
  observed the same interruption, and one graph timed out on a live coordination owner. One
  verifier receipt also showed Python executable-resolution stderr during parallel roots. Shared
  Python/Git toolchain ACL grants are now serialized with a Windows named mutex; a concurrent
  negative test passed in compatibility on `6cc0833`. Manual run `35628932249` passed Linux and
  macOS native reports, but Windows failed its lifecycle phase. Its compatibility traceback
  identified transient `.git/agentsmith-runs/coordination.lock` removal during the sandbox's
  per-file DACL snapshot/restore as the verifier exit-126 cause. The sandbox now skips only
  disappeared paths on Windows errors 2 and 3, and a native test deletes the lock mid-verifier.
  Manual run `35630897623` passed that native negative test and all ten compatibility graph
  cases, but its separate Windows native report still failed eight graph cases on the same clean
  tree. The release recorder runs with a stripped Git/Python environment; a raw Windows case under
  that exact environment in push run `35633073987` reproduced a live repository coordination
  owner outlasting the ten-second wait during parallel graph start. A simulated 11-second live
  owner failed before the timeout change and passed with a bounded 60-second wait. Manual run
  `35634260887` reached maker validation but reported both fake maker worktrees dirty under the
  release environment. Push run `35635281371` identified `src/a/change.txt` and
  `src/b/change.txt` as the modified files. The recorder isolates Git configuration, while the
  native role's environment allowlist had dropped that isolation. Git for Windows then normalized
  the makers' CRLF files to LF on commit, and the controller's isolated clean check saw the CRLF
  worktree bytes as modifications. A local Git regression reproduced the mismatch and now passes
  when the role receives the controller's effective `core.autocrlf` value. Manual run
  `35636764367` passed all three native reports on commit `56db8eb` and tree `d42ed99`, including
  the Windows lifecycle and negative AppContainer boundary. A local strict aggregate accepted
  those exact reports, but the hosted aggregate skipped because the separate Windows compatibility
  job reached its 20-minute job timeout while recording First Verified Loop evidence after its
  graph checks had passed. The compatibility budget now allows 30 minutes on Windows; the next
  same-tree manual run must pass before this issue can close. Run `35639654255` passed all three
  native reports on commit `f41c4cf`, tree `dd4f9f3`, but its separate Windows compatibility
  lifecycle intermittently left two child controllers at `checking` after a verifier exit of 0.
  The graph had rendered their failure reason as the string `None`, hiding the child process
  error. Failure events now retain a bounded, secret-free exit/exception/source-line signature.
  Manual run `35645070119` on `b331612` passed all three native reports, but its Windows
  compatibility copy again observed a child controller gone before terminal state: node `b`
  was `interrupted`, independent node `a` completed, and dependent `c` stayed blocked. The
  expected-nonzero test path did not print its graph event or child stderr, so the exit cause
  remains unknown. Same-commit rerun `35646692896` passed all nine jobs, including Windows
  compatibility and the hosted strict aggregate. This remains an open reliability defect.
  Push run `35651017175` repeated the Windows failure in another fixture: node `a` exhausted
  the 60-second coordination wait on live process `3484`, while `b` exited at `prepared` without
  a terminal reason. A simulated Windows sharing denial on coordination-lock release failed
  before a bounded unlink retry and passed after it; the exact hosted exception was not
  captured. Push run `35652909610` then identified `PermissionError` at the exclusive
  coordination-lock creation call in a different Windows fixture. Bounded Windows sharing
  retries now cover acquisition and release; targeted tests fail before each fix and pass
  after. A same-tree native rerun is the release gate. Failed runs do not produce a passing
  aggregate. On 2026-09-22, the expected failed-node fixture gained bounded graph-event and
  child-exit signatures in its assertion; a synthetic redaction check fails before that
  diagnostic and passes after. Manual workflow run `35697924409` passed both Windows native
  and compatibility lifecycle paths on commit `13bfb84`, and its hosted aggregate bound all
  three native reports to tree `a9e84ec`. No post-fix Windows child interruption recurred;
  the controller cause remains open pending a captured failure and red regression.
- [ ] 2026-09-21 — A stop request arriving after a fake maker has committed but before its receipt
  is reconciled can leave an interrupted run whose resume replays the maker, producing a clean
  worktree with nothing new to commit. A local graph stop/resume test exposed this under heavy
  concurrent verification. The fixture now holds the maker before commit to test a deterministic
  mid-maker stop; the late-stop reconciliation path still needs a bounded controller fix.
  Re-checked 2026-10-26: resume no longer replays the maker. It refuses with "unfinished maker
  advanced HEAD without a validated receipt; operator review required" and keeps the commit;
  `test-autonomous-run.sh` "stop after the maker committed but before its receipt" pins this.
  Automatic recovery was not added: the stop ended the maker before it wrote a receipt, so the
  controller cannot tell finished work from half-done work, and accepting or discarding the
  commit on its own would not be safe. Open until an operator-facing recovery path is designed.
## Resolved during W2-06

- [x] 2026-09-21 — Windows AppContainer ACL grants initially left inherited ACE drift after
  cleanup. Runs `35614813369`, `35616698843`, `35617685307`, and `35618648705` isolated the
  failure to ACL propagation, including `icacls /restore`. Per-file DACL restoration passed
  the worktree, Python, and Git ACL comparisons plus file/network denials in hosted run
  `35621523631`. The launcher returns 126 if setup or cleanup fails. The detailed investigation
  is retained in the private project archive.
- [x] 2026-09-21 — A Linux verifier mount fixture patched `sys.platform` while the controller
  selected Windows with `os.name`; native run `35619728991` failed the fixture after passing
  the AppContainer boundary. Platform routing now uses `sys.platform`, and Windows run
  `35621523631` passed that fixture.
- [x] 2026-09-21 — A Windows graph status fixture wrote platform line endings, so its working
  graph bytes differed from the committed contract on run `35613620432`. It now writes exact
  UTF-8 bytes with LF, as the manifest fixture already did; run `35614813369` passed the graph
  contract step on native Windows.
- [x] 2026-09-21 — Hosted macOS graph dispatch sometimes treated a change to Git's
  `.git/info/refs` dumb-transport cache as an unauthorized maker metadata write during parallel
  work. The docs-only push run `35610061317` exposed the exact path. A linked-worktree
  regression failed before the change and passed after; malformed cache content still fails
  the protected metadata check.
- [x] 2026-09-21 — The Ubuntu guardrail previously skipped the active sandbox and missed a
  verifier command that accepted a sibling write inside isolated `/tmp`. The job now installs
  Bubblewrap and the controller remounts isolated `/tmp` and home read-only before binding the
  worktree. Run `35608202281` passed all 87 guardrail checks and all seven Linux native phases
  on commit `0ec6c8a`, tree `2363ad5`.
- [x] 2026-09-21 — Hosted Linux hid graph fixture worktrees under a late `/tmp` tmpfs mount,
  causing eight verifier-dependent lifecycle failures. The controller now mounts `/tmp` before
  creating and binding those worktree paths. Run `35605909782` passed the actual verifier probe
  and all seven native phases on commit `819d56b`, tree `176e14d`.
- [x] 2026-09-21 — Windows checkout converted work-graph fixture JSON from LF to CRLF, invalidating
  the committed manifest and graph hashes. Git attributes now pin that fixture tree to LF; the
  contract suite failed in a simulated Windows checkout before the fix and passed after.
- [x] 2026-09-21 — Hosted Linux coordination read the empty lock between exclusive creation and
  owner-record flush. A bounded publication retry passed its red/green test and the next Linux
  native report passed all 24 coordination tests.
- [x] 2026-09-21 — The Windows native report stopped at a POSIX-only secret-scanner test reported
  as skipped. A native Windows CRLF scanner test now fills that slot; the next report passed all
  ten secret-scanner tests and reached the lifecycle phase.
- [x] 2026-09-21 — Failure reports retained only output hashes, hiding which coordination test
  failed on Linux. The recorder now emits bounded unittest names or a skip marker to CI logs,
  with a regression proving exception text stays out of those labels.

## Resolved during FVL-02

- [x] 2026-09-18 — The FVL-01 handoff described six discovery/apply capability contracts, but the
  frozen suite contained five (plus the separate fixture/fingerprint contract). FVL-02 now reports
  the executable count explicitly and adds its own adversarial coverage without changing the five.
- [x] 2026-09-18 — The installed-Python discovery fixture uses correct `all(...)` logic even though
  the FVL-02 acceptance text requires a configured gate to catch the named `any` defect. The
  disposable end-to-end test now injects that defect before discovery and proves the applied phase
  catches it; the frozen fixture remains unchanged.
- [x] 2026-09-18 — First-hour documentation said the generated `unwired` phase merely echoed and
  could pass vacuously. The implementation deliberately exits non-zero; the verification guides
  now describe that behavior and the discovery/apply path accurately.
- [x] 2026-09-18 — Initial FVL-02 dispatch assumed every `cmd_verify()` caller came through the CLI
  parser. Receipt tests construct a minimal `argparse.Namespace` directly and exposed an
  `AttributeError`; discovery-only attributes now use guarded access, preserving the internal call
  contract.
- [x] 2026-09-18 — Verification apply reused a backup helper that followed a dangling timestamped
  backup symlink. FVL apply now creates backups with exclusive no-follow semantics, and a whole-root
  regression test proves no outside file appears.
- [x] 2026-09-18 — A single nested stack produced target-root commands such as `npm test`, which
  would run in the wrong directory. FVL-02 now treats every non-root software stack as unresolved
  monorepo ambiguity instead of proposing a command with false scope.
- [x] 2026-09-18 — A plan could repeat one trusted proposal and write duplicate phases. Closed-plan
  validation now requires unique proposed labels before rendering or backup creation.
- [x] 2026-09-18 — Coverage classified phase text with substring matching, so `latest :: echo
  release` appeared to configure tests. Classification now uses conservative label tokens and
  recognized command forms.
- [x] 2026-09-18 — Applied phases whose executable was absent from `PATH` appeared configured. The
  coverage map now keeps their allow-listed recommendation visible, reports `tool-unavailable`, and
  never marks that cell configured.
- [x] 2026-09-18 — FVL discovery/apply contracts initially ran only in the local superset gate. A
  green-only `--fvl02` suite is now compiled and executed in the native Linux/macOS/Windows matrix;
  the full local suite retains later slices as intentional red contracts.
## Resolved during FVL-03

- [x] 2026-09-18 — The first profile-switch implementation reused the generic backup helper, whose
  existence check did not detect a dangling timestamped symlink. Instruction and verification
  backups now share exclusive no-follow creation, with adversarial tests proving no outside write.
- [x] 2026-09-18 — Profile switching trusted loosely typed manifest fields; a string `"false"` for
  `include_core` was truthy and could render the wrong ownership model. The shared installation
  validator now checks scope, booleans, agent/profile lists, mappings, and managed-file shape before
  the first switch write.
- [x] 2026-09-18 — Status initially counted full-core files across different client runtimes as
  duplicates and summarized only project capabilities in a layered install. Duplicate detection is
  now per runtime, instruction order is global → project → nested → generated adapter, and effective
  capabilities merge both installation layers.
- [x] 2026-09-18 — Profile-switch preflight originally allowed malformed managed markers to update
  the installation manifest without updating instructions. FVL-03 now refuses malformed markers
  before any write, and its focused cross-platform selector covers topology, ownership, foreign
  content, and budget boundaries.
- [x] 2026-09-18 — A file containing two complete managed instruction blocks was treated as valid,
  so switching could update only the first block and leave a stale duplicate. Shared instruction
  reconciliation now rejects duplicate managed blocks before creating backups or changing state.
- [x] 2026-09-18 — Shared installer dry runs returned before instruction-marker validation, so a
  preview could claim reconciliation would succeed when the real install would refuse it. Dry runs
  now execute the same byte-preserving validation/render step while remaining write-free.
- [x] 2026-09-18 — Profile guidance named a historically lean two-profile stack using a stale line
  count, but the evolved core pushed it over the token budget. Guidance now avoids fixed size claims,
  and `profiles switch` measures both limits before its first write.
- [x] 2026-09-18 — Discovery plan fingerprints intentionally exclude source files that affect only
  coverage prose, which let those facts drift before apply. Apply now replays and compares every
  semantic discovery field as well as the write-relevant hashes and trusted proposals.
- [x] 2026-09-18 — Labels such as `tests :: true`, `tests :: echo TODO`, and compound stub chains
  claimed configured test coverage without executing a check. Discovery now reports no-op phases
  and excludes them from configured coverage.
- [x] 2026-09-18 — Existing verification labels and commands were copied verbatim into discovery
  plans and full-context dry-run diffs, so an inline credential could reach stdout or a saved plan.
  Both review surfaces now redact secret-shaped values while the fingerprint and applied config
  retain the exact original bytes.
- [x] 2026-09-18 — Discovery skipped symlinked directories during its walk but its explicit
  `.harness/verify.conf` lookup could still read through a symlinked parent. Component-level path
  validation now rejects that route before opening the outside file.

## Resolved during FVL-04–06

- [x] 2026-09-18 — The frozen first-loop demo used `python` in its verification config even though
  AgentSmith's supported macOS path may expose only `python3`. The real FVL-06 exercise caught the
  failure before tests could run; the production and contract templates now use the repository's
  established cross-platform `python3` command convention.
- [x] 2026-09-18 — Resume compared an unresolved explicit `/var/...` path with its resolved
  `/private/var/...` target on macOS and misclassified that spelling difference as a symbolic-link
  escape. It now checks symlinks at the target-owned handoff boundary, then performs containment on
  resolved paths.
- [x] 2026-09-18 — The strict self-update conformance fixture copied the runtime, rules, profiles,
  and registry but omitted the newly runtime-owned demo template. Its staged checkout could no
  longer represent a complete release. The fixture now carries `templates/`, matching the existing
  updater fixture and production release shape.
- [x] 2026-09-18 — Resume initially treated a present recovery section as complete even when a
  required field was absent, and its human output hid the missing names behind a generic warning.
  Every recovery field is now required and both human and JSON output name each gap.
- [x] 2026-09-18 — Read-only Git observation used ordinary `git status`, which may refresh index
  metadata. Every resume Git subprocess now sets `GIT_OPTIONAL_LOCKS=0` and disables terminal
  prompts; a mocked subprocess contract asserts the environment on every call.
- [x] 2026-09-18 — A handoff could label a destructive shell command or kickoff as “read-only” and
  have resume return it as paste-ready. Resume now accepts a narrow read-only command vocabulary,
  never emits handoff-supplied kickoff prose, and synthesizes a safe prompt from validated fields
  without echoing the untrusted content.
- [x] 2026-09-18 — Explicit handoff selection checked candidate existence before proving target
  containment and reopened the file after symlink validation. Selection now proves lexical and
  resolved direct-child containment first, rejects linked paths, and on POSIX opens every directory
  component plus the regular file through pinned no-follow descriptors.
- [x] 2026-09-18 — Resume's first recovery-command allowlist still admitted environment-prefix
  assignments, arbitrary paths ending in `agentsmith.py`, and Git flags that invoke external diff
  helpers. Recovery is now limited to the literal installed `agentsmith`/`agentsmith.cmd` entry
  point, operation `status`, and only `--target`/`--json` options; any supplied target must match the
  resumed project, and emitted commands are synthesized rather than copied from the handoff.
- [x] 2026-09-18 — Placeholder details and filesystem errors could reproduce secret-shaped strings
  from an untrusted handoff or target path. Placeholder output is now categorical, and every path
  and operating-system error returned by resume passes through secret redaction.
- [x] 2026-09-18 — FVL-06 asserted a receipt but skipped status/coverage and replaced its generated
  handoff with an unrelated fixture. The value trace now checks configured coverage, creates a local
  Git checkpoint, fills the actual generated note with its branch/commit/receipt evidence, and
  resumes it with zero drift.
- [x] 2026-09-18 — The document named “Your first loop” described only unattended automation, so
  newcomers could skip the attended evidence loop that makes later autonomy defensible. It now runs
  the complete bounded First Verified Loop first and preserves the unattended-loop guide as part two.
- [x] 2026-09-18 — Product docs described proof mechanisms but had no reproducible public artifact
  chain. FVL-07 now regenerates a sanitized bundle from a temporary clean Git source copy and
  byte-compares red/green, real-path, receipt, handoff/resume, lifecycle, and compatibility evidence.
- [x] 2026-09-18 — Receipt phase durations made two otherwise identical public proof generations
  differ byte-for-byte. The public sanitization contract now normalizes duration values while
  retaining exit codes, test names, phase labels, output hashes, and pass/fail results.
- [x] 2026-09-18 — The first lifecycle proof interpreted project uninstall as removal of native
  client safety configuration. The fixture now checks the actual ownership boundary: managed project
  instructions are removed, scaffolding and selected client safety remain, and foreign content is
  preserved. The limitation is documented publicly.
- [x] 2026-09-18 — The first proof generator inherited the caller's HOME, client configuration, and
  global Git settings. That made clean-room status depend on operator state and could activate an
  opted-in update check. Every proof subprocess now uses isolated temporary homes and client paths,
  ignores global/system Git config, and a sentinel contract proves caller state neither enters the
  artifacts nor changes.
- [x] 2026-09-18 — macOS canonicalized temporary `/var` paths to `/private/var` after the sanitizer
  map was built, producing malformed `/private$DEMO` evidence. Both lexical and resolved clean-room
  paths are now normalized, with a regression assertion against partial-prefix leakage.
- [x] 2026-09-18 — FVL-07 initially checked Markdown links and fences without producing rendered
  evidence. The gate now renders Markdown to HTML when the optional local renderer is available,
  parses the standalone SVG diagram as XML on every platform, and the final SVG was rendered in a
  real headless browser and visually inspected.
- [x] 2026-09-18 — Existing-config lifecycle preservation was asserted by substring membership.
  The fixture now requires the post-uninstall project bytes to equal the original exactly and the
  client bytes remaining after removal of the documented managed safety block to equal exactly.
- [x] 2026-09-18 — The isolated FVL-07 subprocess environment still inherited `PYTHON*` and
  arbitrary `GIT_*` variables, so caller module injection or command-scoped Git config could alter
  the proof run. The generator now removes both namespaces before adding its bounded Git settings;
  the clean-copy contract injects both attack classes and proves the public bundle is unchanged.
- [x] 2026-09-18 — The FVL-07 HTML-render contract skipped when the optional local Python Markdown
  renderer was unavailable. It now renders on every runner through a deterministic standard-library
  structural fallback while still using Python Markdown when installed; the fallback has explicit
  heading, link, table, and fenced-code regressions, and the full local render remains inspected.
- [x] 2026-09-18 — Native CI logs were transient and could not prove that Linux, macOS, and Windows
  tested the same source. FVL-08 now records a closed-schema report per clean native checkout and
  aggregates only the exact three platforms when commit, Git tree, phases, and security categories
  match. Actual hosted reports remain pending separate Git and workflow authorization.
- [x] 2026-09-18 — Local verification receipts were written under `.harness/evidence/` but that
  machine-specific directory was not ignored, so an ordinary broad stage could publish absolute
  operator paths. The directory is now excluded from source control, with an FVL-08 regression
  assertion that exercises Git's actual ignore rules.
- [x] 2026-09-18 — The first hosted run exposed that First Verified Loop fixture hashes depended on
  the checkout platform: Windows converted LF to CRLF, then correctly rejected its own clean fixture
  as stale. A second run exposed the matching production template as another byte-level consumer.
  Git attributes now pin both complete trees to LF, and the contract asserts both effective
  attributes before checking hashes, template parity, or CRLF-preservation behavior.
- [x] 2026-09-18 — Public-proof test repositories used reserved `.invalid` email addresses that were
  safe placeholders but did not match the leak gate's single accepted email convention. The fixtures
  now use `example.com`, so newly tracked proof sources pass the same release gate as all shipped files.
- [x] 2026-09-18 — Profile-switch dry-run contracts compared displayed paths using POSIX separators
  and the temporary directory's unreconciled Windows short spelling. The CLI correctly emitted native,
  resolved paths; the tests now require the same file identities through platform-native separators
  and resolved path spelling.
- [x] 2026-09-18 — The POSIX handoff security contract required the first `os.open()` call to target
  a directory descriptor even on Windows, where the production code intentionally uses its documented
  pinned-file fallback. The implementation-detail assertion is now POSIX-only; platform-neutral resume
  behavior and containment contracts still run on every host.
- [x] 2026-09-18 — Public-proof regeneration used platform-default text newlines while its contract
  compared exact bytes, allowing Windows to produce a different compatibility artifact. The generator
  now writes UTF-8 LF bytes, Git pins the complete published proof tree to LF, and a regression checks
  both the effective attribute and every published file.
- [x] 2026-09-18 — Windows public-proof artifacts retained native separators, drive-letter casing, and
  quoting after temporary paths became placeholders, while receipt hashes still bound unsanitized host
  output. Sanitization now canonicalizes those path forms and hashes the sanitized LF phase output,
  retaining outcomes and meaningful receipt integrity without making the public bundle host-dependent.
- [x] 2026-09-18 — A hosted Windows stress run exhausted the autonomous state reader's one-second
  sharing-violation retry budget while 200 atomic writers replaced the same file; a later run showed
  the runner can surface the same denial as `EACCES` without `winerror`. Reads and replaces now accept
  both Windows exception shapes within a bounded five-second window, with a simulated 150-denial
  regression proving the classifier and longer window without slowing the suite.
- [x] 2026-09-18 — The hosted workflow grouped seven native test commands in one PowerShell step, so
  an early non-zero process could be masked by later successful commands. Each fixture suite is now a
  separate fail-fast step, and the evidence recorder names bounded repository-relative dirty paths
  when its clean-checkout invariant rejects a run.
- [x] 2026-09-18 — The verification-receipt durability test polled through “not created yet” and
  partial JSON but treated Windows' transient atomic-replacement sharing denial as corruption. Its
  bounded partial-state polling loop now retries `PermissionError`; final receipt validation remains
  strict after the writer exits.
- [x] 2026-09-18 — Native evidence intentionally ignores global Git configuration, but Windows
  checkout conversion had relied on global `core.autocrlf=true`. The clean-checkout observation then
  misclassified every CRLF-populated text file as modified. Evidence Git reads now state the
  normalization explicitly, with a regression fixture that still detects real content changes.
- [x] 2026-09-18 — The Windows doctor fixture intentionally forced locale mode in its child process,
  but left child stdio locale-encoded. The release recorder's UTF-8 parent then decoded that output
  differently from the standalone fixture step. The fixture now keeps locale-mode behavior under test
  while pinning its subprocess stdio and parent decoding to UTF-8.
- [x] 2026-09-18 — A hosted macOS evaluation run hit a transient `ENOTEMPTY` race while Python 3.13
  removed an isolated Git fixture's object-pack directory. Evaluation cleanup now retries boundedly
  for transient filesystem activity and still raises if the temporary tree cannot be removed.
- [ ] 2026-09-18 — The frozen First Verified Loop specification still calls the repository gate a
  24-phase gate, while `.harness/verify.conf` now contains 25 phases. The protected specification was
  intentionally not edited during FVL-08; release-facing documentation uses the observed count.

## Resolved during public launch

- [x] 2026-09-22 — The planned history text replacement changed a proof privacy assertion into a
  check for a common word. The assertion now hashes candidate substrings against the historical
  identifier, preserving the check without keeping that identifier in public source.
- [x] 2026-09-23 — The first standalone install stopped copying a project-local Python runtime, but
  project scaffolding still relied on that copy to create `.agentsmith/` before writing its helper.
  A real frozen-binary install reproduced the missing-directory failure. Scaffolding now creates the
  owned directory explicitly, and every standalone CI target performs the same install and status run.

- [x] 2026-10-04 — Autonomous model tools could write controller state through the maker's shared
  Git grant. Native policies now carve trusted state/contracts/runtime folders out of that grant;
  a real Codex sandbox probe denies both writes and ancestor renames. The verifier also protects
  trusted contracts/runtime folders when a repository is under `/tmp`. Claude Bash and built-in
  file tools receive separate restrictions. This is tool containment, not hostile host isolation.
- [x] 2026-10-04 — Resume restarted makers after checking interruptions and replaced prior logs.
  Durable stage/candidate checkpoints now revalidate the same attempt; streaming logs, invocation
  archives and atomic reported-usage recovery retain evidence across stop and hard crashes.
- [ ] 2026-10-04 — Foundation qualification still needs Linux/native-client containment and
  crash/timeout pilots, checker budget reservation, and accounting for unreported crash spend.
  Process-group stopping does not contain detached daemons or hostile same-user processes.
  The [qualification contract](docs/26-native-qualification-contract.md) defines required cases;
  the earlier project-config override probe is inconclusive, and inference remains unqualified.
- [x] 2026-10-04 — Stopping the primary during peer inspection could swallow SIGTERM as an
  ordinary run error and falsely report the legitimate `disjoint` peer branch as tampering.
  Cancellation now bypasses invalid-peer handlers. Retained before/after fixtures and deterministic
  SIGTERM regression checks are in `scripts/test-autonomous-state.py`.
  The native-client qualification contract is accepted; actual inference remains unexecuted.
## Native qualification work (2026-10-05)

- [x] NQ-01/C07 — Generated Claude role policy omitted an explicit hook-disable setting.
  Maker/checker regression failed before adding `disableAllHooks: true` and passes afterward.
  Native hook/connector evaluation remains pending in NQ-03; offline policy assertions do not
  establish containment of actual native tools.
- [x] NQ-02 review — Initial recovery proof validation accepted fabricated pass records
  without case-specific state, timing/group or frozen source proof. Independent adversarial
  probes reproduced false acceptance for R01 and R04 and cross-variant relabeling. The recorder
  now requires case-bound frozen proof, strong receipts, separate timing/group evidence and
  accounting replay; regressions reject false passes. This is separate from the marketing gate.
- [x] NQ-02/R08 — Resume ignored edits to the original accepted spec and accepted a saved
  candidate. A real changed-spec fixture reproduced the acceptance. Resume now compares the
  original file with the committed contract before launching work; changed/missing/symlinked
  specs are refused and Git-normalized line endings remain valid. Unit red/green evidence and
  the real changed-spec refusal are retained with the qualification series.

- [x] 2026-10-05 — Refreshing the installed autonomous controller followed an existing destination
  symlink and could overwrite a file outside the project. Software-development scaffolding now
  rejects symbolic links in either autonomous payload path before runtime/template writes.
  Four real-install regression variants cover payload files and parent directories.
- [ ] 2026-10-05 — Other runtime payload copies in `copy_runtime()` still use `shutil.copy2`
  without checking every destination component. The new autonomous payload guard protects its
  own files and their parents; existing links at other individual runtime filenames need a
  separate installer containment fix.

- [x] 2026-10-05 — A child preflight refusal before run-state creation left the graph waiting
  indefinitely with a dispatched node still reported as ready. Graph dispatch now persists
  a terminal launch failure and safe exit signature; read-only status marks the failed roots
  and blocked descendants. A real CLI regression failed at its 10-second bound before the fix.
- [x] 2026-10-05 — Windows graph fixtures reached the new production native-role sandbox guard.
  Test-local controller wrappers substitute only that preflight for deterministic fake clients;
  the real Git and verifier boundary remain exercised. A simulated Windows check also proves
  the original production guard still refuses unsupported native role launches.
- [x] 2026-10-05 — Windows qualification fixtures serialized source paths with backslashes,
  then indexed forward-slash contract keys. Recovery evidence now serializes relative paths
  with portable forward slashes for sources, artifacts and typed proof. A simulated Windows
  path regression reproduces the mismatch before the fix and validates the bound evidence after.
- [x] 2026-10-05 — The repeated stop fixture continued after its 2.5-second startup wait
  expired, so it could request stop before durable state existed. A four-second startup probe
  reproduced the false status failure. The fixture now requires an observed active process
  within a bounded ten-second wait and prints state and child output on failure. The exact
  hosted failure lacked retained state and remains unattributed beyond this reproduced defect.
- [x] 2026-10-05 — A stop signal during the controller's terminal-head cleanup could raise
  `RunInterrupted` outside its handler and print a traceback with exit 1 after interruption
  was already persisted. Two of 25 retained stop probes reproduced this; durable state stayed
  interrupted. Fixed on 2026-10-09 with the interruption record; see "a second stop signal
  could cut short the interruption record" below.
- [x] 2026-10-05 — The installed autonomous controller decoded UTF-8 Git paths with the
  Windows locale. Preparing a manifest under a `ü` directory looked for a nonexistent `Ã¼`
  template path. A real Git repository with a simulated CP-1252 subprocess decoder reproduced
  the corruption; explicit UTF-8 Git transport preserves the original repository path.
- [x] 2026-10-05 — Controller receipt, captured-log and usage-replay file reads still use
  the locale default. A simulated CP-1252 read corrupts UTF-8 JSON text. These paths need
  explicit encoding and their own receipt/replay regressions; native Windows model-role
  execution remains unsupported, separately from the corrected prepare command.
  Fixed 2026-10-26: receipt reads, captured logs, usage replay, `events.jsonl` and the verifier
  log now name UTF-8. A simulated CP-1252 default failed on byte 0x81 before the fix and passes
  after; a source check fails if any text-mode file call in the controller omits its encoding.

### LOCAL-CAPABILITIES: shared hook groups lost foreign handlers (fixed)

Registration and uninstall previously removed an entire matcher group if one handler was AgentSmith-owned. A failing mixed-handler fixture reproduced foreign configuration loss. Reconciliation now filters only owned handlers and preserves group options and foreign siblings. Regression: scripts/test-capability-effects.py.

### LOCAL-CAPABILITIES: staged hook paths lost shell quoting (fixed)

A memory-enabled update fixture failed when a staged runtime path without spaces was translated into a live Unicode path with spaces. Owned hook argv is now translated before destination-shell quoting. The update/rollback fixture invokes the exact installed command and checks reference-only context, then restores every original byte.

### LOCAL-CAPABILITIES: Orca delivery remains unverified

No callable Orca native-session interface is available in this implementation session. Manual CLI recall and configured launcher fixtures are verified separately; native Claude/Codex startup and resume through Orca require attended observation. Record host/client versions and observed reference output; mark unsupported only if suppression is observed. No workaround is included.

### LOCAL-CAPABILITIES verification: autonomous fixture cleanup stalled (open)

One full verify run stalled after `stopped primary run is durably interrupted` in scripts/test-autonomous-run.sh. Its disposable `legacy` controller remained in `making` with `active_pid: null` and an exited/defunct child while the fixture waited for its runner. The preceding disclosure full suite passed the same unchanged controller. The stalled test tree was terminated; that run is not passing evidence. Controller/NQ-03 fixes remain separate; rerun the full suite and investigate if recurrence persists.

Probable cause, not confirmed (2026-10-11): the same signature as "a stop signal inside a Git call could hang the controller" below. A stop signal that lands inside `subprocess` can leave its wait lock taken, so the exited child is never reaped and the controller waits forever. That fix removes the mechanism. This entry stays open until repeated full gates show no stall.

### LOCAL-CAPABILITIES: ambiguous memory metadata and truncated references (fixed before release)

Review reproduced duplicate JSON status keys and a boolean metadata version bypassing archive exclusion. Metadata now requires integer version 1 and rejects duplicate keys. Long startup paths are displayed in full or omitted with a diagnostic; bounded warnings retain drift/incompleteness information. Regressions live in scripts/test-project-memory.py.

### LOCAL-CAPABILITIES: partial config inspection and credential forms (fixed before release)

Audit fixtures reproduced clean/incomplete misclassification for missing roots, malformed hook structure, unsupported hook types and deep JSON. Reports now distinguish these with error status 2. Contextual credential checks cover URL passwords and bearer literals while accepting environment references. Tests also cover CODEX_HOME, wildcard grants and output redaction in scripts/test-config-audit.py.

### LOCAL-CAPABILITIES: audit command text false positives (fixed before release)

Quoted `echo` and `printf` arguments containing download or package commands were
misclassified as executable launchers. Reproduced with safe fixtures; bounded
command-position recognition now separates arguments from commands. Regression
checks cover safe printed text and risky separators, wrappers and environment prefixes.

## Run controller path reading (2026-10-09)

### RUN-CONTROLLER: a moved file hid its old path from the scope and protection checks (fixed)

The controller listed a candidate's changes with Git's rename detection on, so a moved file
appeared under its new path only. A fixture run moved an approved baseline check from `tests/`
into the allowed scope and was accepted end to end, with narrow and with broad scope. At function
level, moving `.harness/verify.conf` passed the same two checks. Both lists now use
`--no-renames`: a move is the old path removed plus the new path added, so the old path is held
to the scope, the denied paths and the protected inputs. A role receipt must list both paths of a
move, and the role prompt now says so. Regressions: scripts/test-autonomous-state.py and the move
cases in scripts/test-autonomous-run.sh.

### RUN-CONTROLLER: quoted file names missed scope rules and blocked non-ASCII projects (fixed)

The scope check read Git's line listing, which wraps a name with a non-ASCII or special character
in quotes and escapes it. A rule written with the real name then did not match the listed one. A
fixture run with broad scope edited a file under a denied directory with a non-ASCII name and was
accepted end to end when the maker's receipt repeated the quoted listing. In the other direction,
an edit to an allowed file with a non-ASCII name was rejected as out of scope. The same reader
also trimmed leading whitespace from the first name. All four path lists now read NUL-separated
names, which Git neither quotes nor escapes, and receipts use plain names. Git no longer escapes
the names, so the scope escalation shows control characters in a name escaped. Regressions:
scripts/test-autonomous-state.py and the non-ASCII and crafted-name cases in
scripts/test-autonomous-run.sh.

### RUN-CONTROLLER: two escalations printed crafted file names unescaped (fixed)

The escalations for protected verification inputs and for ignored paths outside scope printed a
file name as stored. A maker chooses those names, so a name holding a terminal control sequence
reached the operator's terminal as is. A fixture run with such an ignored file reproduced it.
Both messages now show control characters escaped, as the scope escalation does. Regressions:
scripts/test-autonomous-state.py and the crafted ignored-name case in
scripts/test-autonomous-run.sh.

### RUN-CONTROLLER: a second stop signal could cut short the interruption record (fixed)

`stop` first terminates the active role's process tree and then signals the controller. The
controller usually learns of the stop from the role's exit, so its own signal often arrived after
it had already caught the stop, and the handler raised a second time. Two places were reproduced.
Inside the interruption write, the run state said `interrupted` but no `run_interrupted` event
was written: 1 of 30 repetitions of the stop case from scripts/test-autonomous-run.sh at
`b293c3a`, with a traceback that ends in `persist_interrupted`, `save_state`, `write_json` and the
signal handler. In the full gate this appeared as a failed `controller records exactly one
interruption transition`. In the terminal-head cleanup that follows, the record was complete but
the controller exited with a traceback and code 1 instead of 130: 10 of 150 repetitions at
`19afde4` on macOS. The handler now raises only until the controller has caught the stop. After
that the signal changes nothing, so the record and the cleanup finish. A stop that arrives while
the run still executes interrupts it as before. With the change, 300 of 300 repetitions of the
same stop case ended with one event, exit code 130 and no traceback. Regressions: the two
stop-signal cases in scripts/test-autonomous-state.py, beside the existing check that a signal
during execution still interrupts, and the traceback check in the stop case of
scripts/test-autonomous-run.sh.

### RUN-CONTROLLER: a stopped checker removal blocked every resume (fixed)

`git worktree remove` deletes the checker folder before its entry under `.git/worktrees`. A stop
between the two left the entry, and the state still named the checker. Resume compares Git
metadata with the snapshot taken before the maker, so the leftover entry escalated it with
`runtime changed protected Git metadata`, listing whichever entry files the removal had not
reached yet. Seen in 1 of 80 repetitions of the stop-during-checker case at `19afde4`, and in one
full gate run as a failed `checking stage recovery`. Resume now removes that entry when the folder
is gone, by the rule `git worktree prune` uses: unlocked, and its `gitdir` file is missing or
names the missing folder. An entry another worktree owns stays. A hard crash at the same point
leaves the same state and is covered too. Regressions: the three shapes in
scripts/test-autonomous-state.py, and the half-removed checker case in
scripts/test-autonomous-run.sh, which ended with the same six-file escalation before the change.

### RUN-CONTROLLER: a late stop could overturn a run's own result (fixed)

Reproduced with a controller-level fixture: `execute` is stubbed to reach one outcome, and the
stop signal is delivered at a chosen point. Inside the escalation record, the handler raised out
of the controller: a traceback and exit code 1 instead of 2, and no `run_escalated` event. After
the acceptance record, the controller recorded an interruption over the accepted run: the log
held `run_accepted` then `run_interrupted`, the exit code was 130, and resume, which refuses
accepted runs, would have started another attempt on top of the accepted commit. The terminal
cleanup of an accepted or escalated run raised the same way. The rule is now that a run that has
recorded `accepted` or `escalated` keeps it: the handler no longer raises once the status says
so, and `stop` reports the finished result instead of promising a reconciliation. Regressions:
the escalation, acceptance and finished-run stop cases in scripts/test-autonomous-state.py.

### RUN-CONTROLLER: a stop signal after the controller returned ended the process (fixed)

After the controller function returned, it restored the default signal action, so a stop signal
that arrived before the process ended killed it while it still released the lifecycle lock. The
exit status was the signal instead of 130, and the lock stayed for the next resume to replace.
The record itself was complete. Seen in 1 of 80 repetitions of the stop-during-checker case from
scripts/test-autonomous-run.sh at `19afde4`. A run that has recorded its result now keeps the
handler, which ignores a late stop, until the process ends. It is a Python handler, not an
ignored signal, so processes started afterwards still receive `stop` normally. Regression: the
after-return case in scripts/test-autonomous-state.py, which sends the signal from inside a real
child process and expects its own exit code.

### RUN-CONTROLLER: a stop signal inside a Git call could hang the controller (fixed)

The stop handler raised `RunInterrupted` wherever the controller happened to be. In 1 of 80
repetitions of the stop-during-checker case from scripts/test-autonomous-run.sh at `6c3b41e` on
macOS, it landed inside `subprocess.run` while the checker worktree was removed: after
`subprocess` had taken its private wait lock, and before it could release it. The cleanup of the
same call then waited on that lock. The controller stayed alive for 5 hours 6 minutes in state
`checking`, holding the lifecycle lock, and `stop` reported that the controller did not persist
the interruption. A Python stack read from outside the process showed `Popen._wait` blocked on
`self._waitpid_lock`, called from `Popen.__exit__`. The Python documentation warns against raising
from signal handlers for this reason. A second stop signal freed the controller. The window
fixes above did not cause it; the same path exists at `19afde4`.

The handler now never raises. It records the stop and ends the active role's process group.
The controller raises `RunInterrupted` at safe points:
- before each role or verifier process starts, and every half second while one runs, so a
  process that ignores SIGTERM is killed too;
- after a non-zero exit;
- at the `validating`, `verifying` and `checking` checkpoints, once they are saved;
- before the acceptance record and before the attempt-cap escalation;
- while it waits to acquire a Git phase or the coordination lock.

A release never acts on a stop. This replaces the rules in the entries above about when the
handler raises. Their outcomes stay: a run that has recorded `accepted` or `escalated` keeps it.

An independent review of the change found three more gaps. All three are fixed, each with a
test that failed first:
- A stop pending when the last attempt was rejected was recorded as the attempt-cap escalation.
- A stop while a new attempt waited for its Git phase left a `making` checkpoint whose start
  was still the previous attempt's commit. Resume rejected it. Each `making` checkpoint now
  carries its own start.
- A role that ignored SIGTERM ran on until its wall-clock limit.

Ending a role from the handler also exposed a cleanup error. On macOS, signalling a process
group that holds only an unreaped zombie fails with EPERM. The first signal in the cleanup now
treats that case as "already gone", as its second signal already did.

Regressions in scripts/test-autonomous-state.py:
- a real signal sent during a Git call, which failed before the change because the call never
  returned;
- a stop during a Git-phase wait and during a release;
- a stop that only the controller could see, for a role that accepts SIGTERM and one that
  ignores it;
- the review cases, driven through the real attempt loop with fake roles;
- the zombie-only group.

Probes on the final change, macOS, with every wait capped at 120 seconds:
- the stop-during-checker case with resume: 80 of 80 resumed cleanly, none hung;
- the stop case: 300 of 300 ended with one event, exit code 130 and no traceback.

Those counts alone cannot rule the hang out, because it was 1 in 80. The proof is the Git-call
test and the handler that no longer raises.

The first Windows run of these tests in CI (runs `38177003930` and `38177011951`) ended the test
process inside the fake-role harness. The harness sent its stop with `os.kill` to its own
process. On Windows, that terminates the process instead of calling the handler. This is the
second `os.kill` that behaved differently on Windows; the first was the stale-PID probe in the
lifecycle entry above. The harness now uses `signal.raise_signal`, as the other stop tests do.
A local shim that gives `os.kill` the Windows behaviour reproduced the failure before the change
and passed after it.

## OpenCode and Pi user-level rules (2026-10-19)

### GLOBAL-RULES: earlier global OpenCode installs recorded OpenCode but wrote nothing (open)

Up to `v0.3.1`, `install --global --agent opencode` recorded OpenCode in the installation manifest
and printed "installed for opencode", but wrote no rules file. Global destinations were hard-coded
for Claude and Codex. Install now writes `~/.config/opencode/AGENTS.md`, and doctor, update, and
uninstall manage it. Existing installations stay without the file until the operator acts. The
`v0.3.1` updater cannot repair them: on 2026-10-19 its `update apply` against a release with this
fix stopped with "Release attempted an update outside the managed surface:
home:.config/opencode/AGENTS.md" before any real file changed. Fix: rerun `agentsmith install
--global` with the same agents from the newer release.

### GLOBAL-RULES: OpenCode's `XDG_CONFIG_HOME` is not followed (open)

OpenCode reads `$XDG_CONFIG_HOME/opencode/AGENTS.md` when that variable is set. AgentSmith always
writes `~/.config/opencode/AGENTS.md`, so with a different `XDG_CONFIG_HOME` OpenCode never loads
the managed rules. Install warns and doctor reports `opencode-xdg-config-ignored`. Following the
variable would make the update surface depend on an environment value; that needs its own design.

### GLOBAL-RULES: a symlinked `~/.config` makes update refuse (open)

Dotfile managers often make `~/.config` a symbolic link. Install writes through it, but
`update plan --global` refuses any managed path with a symbolic-link component, so a global
OpenCode installation with a linked `~/.config` cannot use the staged updater. Rerun
`install --global` instead. A test pins the refusal.

### GLOBAL-RULES: Gemini CLI declares a global path that nothing writes (open)

The registry lists `~/.gemini/AGENTS.md` as a Gemini CLI global path, but no installer writes it.
`install --global` now warns for Gemini CLI, as for every agent without a managed user-level
file, and leaves it out of the "installed for" line. Either an adapter or a registry correction
is still needed.

### GLOBAL-RULES: OpenCode and Pi certification is pending (open)

Both entries rest on fixture evidence and on the clients' own documentation (OpenCode 1.19.3,
Pi 1.3.0). No real OpenCode or Pi run has confirmed that either client loads the managed rules or
skills. OpenCode's duplicate-skill choice is nondeterministic by inference from its source; doctor
reports it as `duplicate-skill-discovery`.

### GLOBAL-RULES: `--agent local` expanded to a different list than the registry (fixed)

The CLI expanded `local` to five agents while `config/agents.json` lists eight; Codex, Roo Code,
and Continue were missing. The code now matches the registry, and a registry test compares every
group.

### GLOBAL-RULES: safety was recorded for agents that have no safety setting (fixed)

Install recorded `native_safety` for every selected agent. A cautious rerun of a global OpenCode
install after a trusted one then warned that it was migrating Codex's `config.toml`. Only Claude
and Codex are recorded now, and stale records for other agents are dropped on the next install.

### GLOBAL-RULES: a relative `PI_CODING_AGENT_DIR` corrupted foreign text during updates (fixed)

Found in review on 2026-10-19 and reproduced: the updater translated root paths with the raw
configured values. With `PI_CODING_AGENT_DIR="."`, an update of a Codex-only global install turned
`v1.2.3` and `./docs` in the foreign part of `$CODEX_HOME/AGENTS.md` into paths and wrote them to the
live file. Translation now skips non-absolute roots, the Pi folder is an update root only for a
global install with Pi, and a global Pi install or update refuses a relative value.

### GLOBAL-RULES: update accepted two agents sharing one rules file (fixed)

Found in review on 2026-10-19 and reproduced: install refused Pi and Codex resolving to one
`AGENTS.md`, but `update plan` accepted it because each root has its own shadow folder. One
destination check now serves install, update plan, plan validation, and apply.

### GLOBAL-RULES: global Pi uninstall removed other installations' rules (fixed)

Found in review on 2026-10-19 and reproduced: with `PI_CODING_AGENT_DIR` set to `CODEX_HOME` or to a
project root, `install --global --agent pi --uninstall` removed Codex's managed rules or the
project's managed block, because ownership was inferred from markers alone. Install, update, and
uninstall now refuse a destination that is another agent's rules file or that lies in a project
installation's root. Uninstall leaves Pi's file in place when the global record does not list Pi.

### GLOBAL-RULES: each global install replaces the recorded agent list (open)

`record_installation_manifest()` stores only the agents of the latest global install. After
`install --global --agent pi` and then `install --global --agent codex`, the record lists only
Codex, so a later global uninstall leaves Pi's file in place and update no longer manages it. The
record cannot prove ownership of Claude, Codex, or OpenCode files for the same reason. Merging
global selections needs its own design because update replays the record.

## Run guards and development pipeline (2026-10-26)

- [x] 2026-10-26 — `prepare` wrote a manifest with blank role models and only warned; `start`
  refused it later, and `REPLACE-WITH...`/`TO-FILL` values passed both. `prepare` now refuses and
  names each field; a test that saw the draft written before the fix passes after.
- [x] 2026-10-26 — `start` checked only that a sandbox binary existed. On a host that forbids a
  nested sandbox it created the branch, worktree and state, then failed later. A per-role and
  verifier sandbox preflight now refuses first; run inside a nested Seatbelt sandbox, the old
  controller left all three artifacts and the new one leaves none.
- [x] 2026-10-26 — A maker that finished but crossed its token cap left no receipt and no
  candidate checkpoint, so resume stopped for operator review and the work was effectively lost.
  The candidate is now checkpointed before the escalation and resume accepts it; the fixture
  saw stage `making` and no receipt before the fix.
- [x] 2026-10-26 — After a resume, a Claude checker escalated on the Codex cap that only the
  maker had crossed, after spending checker money. Each cap is now checked after the roles that
  spend it; found while fixing the entry above, and covered by the same fixture.
- [x] 2026-10-26 — Independent review: `status --all-terminal` printed a traceback and exited 1
  when a run state, graph state or lock held invalid UTF-8. It now reports that state as
  undetermined (exit 2); a test with `\xff` in each of the four files errored before and passes.
