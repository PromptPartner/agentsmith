# Troubleshooting — when it's behaving oddly

This is the operational FAQ: the agent is running but doing something you didn't expect. It's the
*runtime* companion to [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)
— that doc is for when a rule you wrote didn't take; this one is for symptoms you observe while
working. Find the symptom, understand the cause, apply the fix.

**"It asks permission for shell or higher-risk actions."** Working as intended — you're in
**cautious** safety mode (the omitted-flag and wizard default). Claude uses `acceptEdits`; Codex uses
`approval_policy = "on-request"` with `sandbox_mode = "workspace-write"`. If that's more
friction than you want *on a machine you own*, switch to trusted; if it's a shared or client box,
keep it. How to change it: [`15-safety-model.md` → Safety modes](15-safety-model.md#safety-modes).

**"It ran a command I didn't want it to."** The inverse — you're in **trusted**
(`bypassPermissions` in Claude; `approval_policy = "never"` and
`sandbox_mode = "danger-full-access"` in Codex), which runs most tool calls without asking. Dial
back to cautious the same way. If this happened on a shared/prod machine, that's the signal to lock
it from above with
`--org-policy` for Claude ([`15-safety-model.md`](15-safety-model.md)). Codex organization policy
is out of scope; the installer rejects platform `codex` or `both` with `--org-policy`.

**"`agentsmith` exits with code 2: the wizard needs an interactive terminal."** Its input is
not a terminal: a pipe, a CI job, or `docker exec` without `-t`. Nobody can answer the questions,
so it stops before changing anything. Run it in a terminal (`docker exec -it …`), or pass the
choices as flags: `agentsmith install --agent <id> --profile <name> --target <path>`.

**"Every Codex command fails inside Docker: `bwrap: No permissions to create a new namespace`."**
Cautious mode runs Codex in its workspace sandbox (bubblewrap), which needs unprivileged user
namespaces. A default Docker container blocks them, so nothing can run. Reinstall with
`--safety container`: approvals stay on and the container becomes the isolation boundary. If your
image already configures Codex, use `--assemble-only` instead and AgentSmith leaves its settings
alone. `agentsmith doctor` reports this case as `codex-cautious-in-container`.

**"An update says trusted safety will migrate to cautious."** The prior AgentSmith-managed config
used bypass/no-approval settings and the current command did not explicitly opt back into them.
That warning is the `0.2.0` safety correction, not loss of foreign config: the installer backs up
the file and changes only its safety setting. Run the same command with `--dry-run` to inspect the
paths without writing. Use `--safety trusted` only if preserving the larger blast radius is the
intended choice.

**"`update apply` says a file changed after planning."** The saved plan contains fingerprints of
every existing managed file it may touch. A person, tool, or background process changed one after
the plan was created, so applying the old plan could overwrite newer work. Do not force it. Inspect
the named file, keep the intended edit, and create a new plan. Planning and an offline `update
check` make no installation changes.

**"An update says its integrity key is missing."** Plans and rollback receipts are authenticated
with `~/.agentsmith/update-integrity.key`. They work only for the local account that created them.
Do not copy a plan from another machine or edit it. Create a new plan on this machine. Keep the key
with its receipts and backups while a rollback may still be needed.

**"Rollback refuses because a file changed after the update."** Rollback restores exact saved
bytes, so it checks the post-update hash before overwriting anything. Preserve or commit the newer
edit first, then decide whether to recreate it after rollback. Do not edit the receipt: its local
authentication, paths, and backup hashes are part of the safety boundary. Receipts and backups live under
`~/.agentsmith`, outside tracked project files.

**"The weekly update check reports that it is offline."** The requested command still runs. Weekly
checks are short, opportunistic, and report-only; they never install a release. Run `agentsmith
update check --from REMOTE` later to diagnose the remote, or disable the opt-in with `agentsmith
update configure --auto-check off`.

**"It keeps trying the same fix and won't stop."** The stop-rule in `core/40` says two identical
failures means re-diagnose, not retry — but a loop or a long run can slip it. The cause is usually
a wrong root-cause diagnosis (R1) or a flake treated as a regression. Interrupt it, and make it
state its hypothesis before the next attempt rather than firing a third blind try. In a loop, this
is exactly what the attempt cap (three, then escalate) is for — if it's not capping, the count
isn't persisting in the state file ([`06-your-first-loop.md`](06-your-first-loop.md)).

**"It said 'done' but the work wasn't actually verified."** Almost always a stub `verify.conf`. A
fresh install ships a deliberately failing `unwired` phase, so `agentsmith verify` stays red until
you wire real checks. Save a discovery plan with
`agentsmith verify discover --target . --save PLAN`, inspect it with
`agentsmith verify apply --plan PLAN --target . --dry-run`, and explicitly
apply the reviewed plan. If discovery cannot recommend the right command, replace `unwired`
manually with your build/test commands. That is what makes "done" mean something
([`03-verify-means-evidence.md`](03-verify-means-evidence.md)).

**"`status` says my instructions are drifted or duplicated."** `status` compares the existing
installation manifests with the managed metadata in the effective global, project, nested, and
generated instruction sources. Drift means those records disagree; duplication means more than one
active source carries the full core. Run `agentsmith doctor --target .` for fingerprints and exact
paths before changing anything. Do not automatically remove the project core: a self-contained copy
may be intentional for collaborators.

**"`profiles switch` refuses before changing anything."** This is fail-closed behavior. The switch
rejects a missing or malformed project manifest, invalid profile names, malformed managed markers,
symlinked write paths, unreadable verification evidence, and profile stacks above the static-context
budget. Fix the named preflight condition and rerun `--dry-run`. Do not bypass the check with a
broad reinstall: that can touch runtime capabilities the profile switch deliberately leaves alone.

**"`demo first-loop` refuses my target."** The demo is disposable only because its write boundary
is unambiguous. Choose a new or empty directory below an existing parent. AgentSmith rejects the
home directory, current directory, repository root, non-empty targets, and symbolic-link targets;
it does not clean or merge an occupied directory. Keep the named target and rerun the command. The
[public runbook](demos/first-verified-loop/RUNBOOK.md) shows the expected clean-room sequence.

**"My First Verified Loop output differs from the public proof."** First compare the named phase
and exit code, not elapsed time or temporary paths. Regenerate the sanitized bundle with the command
in the [runbook](demos/first-verified-loop/RUNBOOK.md). The file
[`sanitization.json`](demos/first-verified-loop/sanitization.json) lists every volatile field that is
normalized; test names, exits, phase labels, receipt status, and lifecycle preservation results are
not normalized.

**"`resume` says the handoff is incomplete or drifted."** Incomplete means a required section,
scaffold field, recovery command, or kickoff prompt is still blank; fill the note before treating it
as a continuation point. Only a bounded `agentsmith status` recovery command is accepted, and
handoff-supplied kickoff prose is never echoed; resume synthesizes its own prompt from validated
fields. Drift means the current branch, commit, or dirty/clean state differs from what the note
recorded. Inspect the difference and decide which state is authoritative. `resume` is diagnostic
only: it disables optional Git locks and never checks out, resets, commits, stashes, or rewrites the
handoff.

**"The explanation is too technical."** `--operator-role` tells the agent what you are responsible
for; it does not describe what you know. Put that detail in `--operator-bio`, because experience can
be different for Git, infrastructure, security, and application code. Re-running setup replaces the
marked AgentSmith rule block but preserves content outside it. Use one of the copy-ready bios in
[INSTALL.md](../INSTALL.md#3-set-responsibility-background-and-external-write-consent), or ask for a
specific level in the current session, such as *"Explain this for a newer developer and define each
Git term."* There is no `--explanation-level` option. An explicit request to answer in another
language also overrides the English default.

**"There is no status line."** AgentSmith adds Claude's default only when `statusLine` is absent;
an explicit empty/disabled/custom value is user-owned and survives re-runs. `disableAllHooks=true`
also disables Claude's custom status line. Codex needs no generated setting because its built-in
model/directory line is active when `tui.status_line` is absent; an explicit `[]` disables it.
Run `agentsmith doctor --agent claude|codex` to see `managed`, `builtin`, `configured`, `disabled`,
or `malformed`, then remove the explicit disable or re-run install as appropriate.

**"The context-% handoff nudge didn't fire."** On Codex, expected: it is intentionally not
installed because it depends on Claude's status line, and this release has no `PreCompact` hook.
On Claude, it is best-effort by design. No hook can reliably read live context usage (a documented
Claude Code gap; see the [hooks guide](https://code.claude.com/docs/en/hooks)),
so the % nudge is fragile. It is also disabled until `HANDOFF_PCT_THRESHOLD` is set: no single
percentage predicts quality across models and tasks. Use the reliable path: treat the `ctx:NN%`
gauge as load information, hand off at a natural phase boundary or when quality signals appear,
and say **"handoff"** yourself. The keyword trigger is solid; a threshold you calibrated on your
own work is an optional backstop, not the mechanism.

**"My Codex hook is installed but does not run."** Codex requires trust for installed hook
definitions. Open `/hooks`, review the Agentsmith commands and paths, then approve them. Re-running
setup merges the definitions idempotently; it should not create duplicates.

**"Codex says `config.toml` is invalid after setup."** Setup should back up the old file and parse
the new one before replacing it. Restore the adjacent `.bak` and report the input that escaped
validation. Do not discard the whole config: unrelated comments/tables and foreign MCP servers are
manually owned and must survive. A warning that an MCP server name conflicts is different — setup
has deliberately skipped that manually owned name; rename one side or remove the manual table,
then re-run.

**"It's burning tokens / feels slow."** Three usual causes. (1) Static context is bloated — run
`scripts/lint-leanness.sh`; over budget means move knowledge into skills/docs
([`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)). (2) A loop is
polling too tightly — widen the interval and make the first step a cheap "anything to do?" that
exits fast on an empty watchlist ([`06-your-first-loop.md`](06-your-first-loop.md)). (3) You ran
the window past its useful point for this model and task — use phase boundaries, repetition, missed
details, and your own calibrated context observations as the handoff signals.

**"It wrote to my tracker / Slack / CRM without being asked."** It shouldn't, on a current setup —
tracker writes default to *ask*, and `core/10` makes the first write to any outside system a
stop-and-ask. If you're seeing this, check that setup was run recently enough to have the consent
default, and that a profile isn't carrying an old always-write instruction. The principle and the
fix are in [`15-safety-model.md`](15-safety-model.md) and [`14-project-tracker-guide.md`](14-project-tracker-guide.md).

**"Re-running setup changed my operator name / role."** Current setup *recovers* your identity from
the existing managed block before re-rendering, so a re-run preserves it. If you're on an older
harness and a `--global` re-run blanked it, pass the fields explicitly (`--operator-name …
--operator-role …`) and update — the recovery behaviour is the fix for exactly this. Your previous
native rule file was backed up before the write, so nothing is lost.

**"Files disappeared after a git operation."** Not the harness — a `git reset --hard` or a branch
switch does exactly what it's told, and can remove files that were tracked in one commit and not
another. Recover from the backup or from history. The durable lesson (re-verify a preservation
claim *after* the last destructive step, not after the one that preserved it) is in
[`10-best-practices.md`](10-best-practices.md).

**"The rules don't seem to apply in my tool."** Run `agentsmith doctor --agent <id>` and inspect
the resolved global/project/nested source chain separately from safety, skills, MCP, hooks, and
runtime ownership. A `duplicate-managed-core` warning means one tool loads the universal core from
more than one file. Doctor models each tool's own discovery rule: Claude Code reads `CLAUDE.md`
files from the folder and every folder above it (and `AGENTS.md` only when no `CLAUDE.md` exists
anywhere in that chain); Codex reads from the Git root down. `instructions.loaded_files` in
`doctor --json` lists what each tool loads. `--profile-only` removes that duplication on a future install, but keep the
full project copy when collaborators need self-contained rules. Project `AGENTS.md` is canonical;
Claude gets a generated `CLAUDE.md`, while configured adapters must still point to it. Web surfaces
do not gain local hooks merely by reading instructions. See
[`13-platforms-and-tools.md`](13-platforms-and-tools.md).

**What a doctor finding means.** Each finding has a stable code. All are warnings; the ones
marked *strict* also make `agentsmith doctor --strict` exit 1, because they mean a run's evidence
cannot be quoted as the shipped behaviour.

| Code | Means | What to do |
|---|---|---|
| `runtime-file-modified` (strict) | An installed runtime file no longer matches the hash install recorded. Hooks, verify receipts and runs come from edited code. | Re-run install or the reviewed update. |
| `duplicate-managed-core` | One tool loads the full core from two or more files, so it reads every rule twice. | Reinstall the project with `--profile-only`, or remove the extra copy. |
| `legacy-managed-block` | A tool loads an AgentSmith block outside this project that no current install owns, such as a `~/AGENTS.md` from an old setup.sh install. | Keep the rules through a current install, then delete the block by hand. |
| `output-rewriting-hook` | A pre-tool hook on the shell tool (today: `rtk hook`) rewrites commands, so the agent reads filtered output. It stays a warning under `--strict`: the update's own post-check runs doctor in your environment. | Quote proof from a raw run (`rtk proxy <command>`) or from the verify receipt. |
| `skill-path-missing` | An installed skill tells the agent to use a script, template or `.harness/` file this install does not have. A skill that names the installed path and the source path needs only one. | Install the profile that ships the file, or adjust the skill. |
| `superpowers-not-enabled` | A rules file Claude Code loads names `superpowers:*` skills, but `enabledPlugins` (user, project or local settings) does not enable the superpowers plugin. | Enable it with `/plugin`, or know that the rule falls back to doing the step by hand. |
| `managed-block-behind-default-branch` | The default branch has a newer managed block in `AGENTS.md` or `CLAUDE.md` than this branch, and this branch did not change it. Skipped without Git or a default branch. | Merge or rebase onto the default branch, or re-run install. |
| `feedback-open-too-long` | A `docs/feedback/NNNN-*.md` record has stayed `Status: open` for more than 30 days. | Land its edit and mark it `applied`, or mark it `wont-fix` with a reason. |
| `feedback-surface-missing` | An `applied` feedback record's `Surface:` line names a file, a literal line or a verify phase that is gone, so the fix it records no longer holds. | Restore the surface, or reopen the record. |
| `harness-review-overdue` | Ten or more feedback records, or more than 60 days, since the dated `_Last harness review:` line in `docs/feedback/README.md`. A missing file counts as never reviewed; `agentsmith new-feedback` creates it on first use. | Run the harness-review checkpoint and date that line. |
| `stale-worktrees` | Git still lists worktrees whose folders are gone (`prunable`). | Check nothing unmerged lives only there, then `git worktree prune`. |
| `many-worktrees` | More than 10 linked worktrees. | Remove worktrees of merged or abandoned work. |
| `low-disk-space` | Less than 5 GiB free on the target's disk. | Free space before long runs. |
| `profile-only-core-missing` | The project was installed with `--profile-only`, but the tool loads no file with the named core sections, so the consent, secrets and identity rules are absent. | Install the core at user level (`--global`), or reinstall without `--profile-only`. |
| `hook-unused-30-days` | An installed hook did not fire in 30 days ([firing log](../hooks/README.md#firing-log--track-every-workaround-delete-it-when-it-stops-firing)). | Advisory: consider removing it; a safety gate may rightly never block. |

**"`agentsmith evaluate` refuses to call the client."** Real model calls require all three pieces:
`--live`, a positive `--claude-max-usd` when Claude is selected, and a positive
`--codex-max-tokens` when Codex is selected. Without `--live`, the command intentionally performs a
write-free dry run. If a live scenario fails, inspect its raw directory printed in the normalized
record; do not promote a favorable subset or edit the grader outcome by hand.

**Still stuck?** If a genuinely new failure mode turns up — something none of the above covers —
that's not just a nuisance to work around, it's the raw material for a system fix. Run
`agentsmith new-feedback "symptom"` and walk it through the loop; the next person gets a
guard instead of the same surprise ([`09-adapting-it-to-your-team.md`](09-adapting-it-to-your-team.md)).
