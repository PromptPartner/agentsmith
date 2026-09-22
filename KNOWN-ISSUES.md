# Known issues

This file records open defects and fixes found during verification. No external tracker write has
been authorized, so the entries are kept here.

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
  traceback paths or output. Keep this issue open until the original failure is reproduced.
- [ ] 2026-09-21 — PR run `35641860248` exposed a macOS false negative in the new Git
  text-conversion regression: `git status` sometimes trusted cached index metadata immediately
  after the test changed `core.autocrlf`, so it reported a clean worktree even though the
  controller would hash different bytes. The regression now compares the filtered worktree
  blob with the committed blob directly; native confirmation remains pending.
- [ ] 2026-09-21 — The same PR run failed a Windows graph stop fixture because it waited for
  any of two parallel makers to log a start but then required `repo-a` to exist. Maker `b` can
  start first, so a stop before `a` creates its worktree is valid. The fixture now checks
  retention for every maker that actually logged a start; native confirmation remains pending.
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
  diagnostic and passes after. No post-fix Windows child interruption has been reproduced yet,
  so the controller cause remains open pending native evidence.
- [ ] 2026-09-21 — A stop request arriving after a fake maker has committed but before its receipt
  is reconciled can leave an interrupted run whose resume replays the maker, producing a clean
  worktree with nothing new to commit. A local graph stop/resume test exposed this under heavy
  concurrent verification. The fixture now holds the maker before commit to test a deterministic
  mid-maker stop; the late-stop reconciliation path still needs a bounded controller fix.
## Resolved during W2-06

- [x] 2026-09-21 — Windows AppContainer ACL grants initially left inherited ACE drift after
  cleanup. Runs `35614813369`, `35616698843`, `35617685307`, and `35618648705` isolated the
  failure to ACL propagation, including `icacls /restore`. Per-file DACL restoration passed
  the worktree, Python, and Git ACL comparisons plus file/network denials in hosted run
  `35621523631`. The launcher returns 126 if setup or cleanup fails. See
  `docs/research/windows-verifier-sandbox.md` for the full progression.
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
