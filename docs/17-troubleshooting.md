# Troubleshooting — when it's behaving oddly

This is the operational FAQ: the agent is running but doing something you didn't expect. It's the
*runtime* companion to [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)
— that doc is for when a rule you wrote didn't take; this one is for symptoms you observe while
working. Find the symptom, understand the cause, apply the fix.

**"It asks permission for shell or higher-risk actions."** Working as intended — you're in
**cautious** safety mode (the omitted-flag and wizard default). Claude uses `acceptEdits`; Codex uses
`approval_policy = "on-request"` with `sandbox_mode = "workspace-write"`. If that's more
friction than you want *on a machine you own*, switch to trusted; if it's a shared or client box,
keep it. How to change it: README → "Permissions & dangerous mode", or [`15-safety-model.md`](15-safety-model.md).

**"It ran a command I didn't want it to."** The inverse — you're in **trusted**
(`bypassPermissions` in Claude; `approval_policy = "never"` and
`sandbox_mode = "danger-full-access"` in Codex), which runs most tool calls without asking. Dial
back to cautious the same way. If this happened on a shared/prod machine, that's the signal to lock
it from above with
`--org-policy` for Claude ([`15-safety-model.md`](15-safety-model.md)). Codex organization policy
is out of scope; the installer rejects platform `codex` or `both` with `--org-policy`.

**"An update says trusted safety will migrate to cautious."** The prior AgentSmith-managed config
used bypass/no-approval settings and the current command did not explicitly opt back into them.
That warning is the `0.2.0` safety correction, not loss of foreign config: the installer backs up
the file and changes only its safety setting. Run the same command with `--dry-run` to inspect the
paths without writing. Use `--safety trusted` only if preserving the larger blast radius is the
intended choice.

**"It keeps trying the same fix and won't stop."** The stop-rule in `core/40` says two identical
failures means re-diagnose, not retry — but a loop or a long run can slip it. The cause is usually
a wrong root-cause diagnosis (R1) or a flake treated as a regression. Interrupt it, and make it
state its hypothesis before the next attempt rather than firing a third blind try. In a loop, this
is exactly what the attempt cap (three, then escalate) is for — if it's not capping, the count
isn't persisting in the state file ([`06-your-first-loop.md`](06-your-first-loop.md)).

**"It said 'done' but the work wasn't actually verified."** Almost always a stub `verify.conf`. A
fresh install ships a deliberately failing `unwired` phase, so `agentsmith verify` stays red until
you wire real checks. Replace that line with your build/test commands — that's what makes "done"
mean something ([`03-verify-means-evidence.md`](03-verify-means-evidence.md)).

**"There is no status line."** AgentSmith adds Claude's default only when `statusLine` is absent;
an explicit empty/disabled/custom value is user-owned and survives re-runs. `disableAllHooks=true`
also disables Claude's custom status line. Codex needs no generated setting because its built-in
model/directory line is active when `tui.status_line` is absent; an explicit `[]` disables it.
Run `agentsmith doctor --agent claude|codex` to see `managed`, `builtin`, `configured`, `disabled`,
or `malformed`, then remove the explicit disable or re-run install as appropriate.

**"The context-% handoff nudge didn't fire."** On Codex, expected: it is intentionally not
installed because it depends on Claude's status line, and this release has no `PreCompact` hook.
On Claude, it is best-effort by design. No hook can reliably read live context usage (a documented
Claude Code gap; details in
[`research/claude-code-hooks-and-managed-policy.md`](research/claude-code-hooks-and-managed-policy.md)),
so the % nudge is fragile. Use the reliable path: watch the `ctx:NN%` gauge in the status line and
say **"handoff"** yourself around 25–30% used. The keyword trigger is solid; the auto-nudge is a
bonus, not the mechanism.

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
the window too long — hand off at ~25–30% used; quality *and* cost degrade as it fills.

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
runtime ownership. A `duplicate-managed-core` warning means both global and project sources carry
the universal core; `--profile-only` removes that duplication on a future install, but keep the
full project copy when collaborators need self-contained rules. Project `AGENTS.md` is canonical;
Claude gets a generated `CLAUDE.md`, while configured adapters must still point to it. Web surfaces
do not gain local hooks merely by reading instructions. See
[`13-platforms-and-tools.md`](13-platforms-and-tools.md).

**"`agentsmith evaluate` refuses to call the client."** Real model calls require all three pieces:
`--live`, a positive `--claude-max-usd` when Claude is selected, and a positive
`--codex-max-tokens` when Codex is selected. Without `--live`, the command intentionally performs a
write-free dry run. If a live scenario fails, inspect its raw directory printed in the normalized
record; do not promote a favorable subset or edit the grader outcome by hand.

**Still stuck?** If a genuinely new failure mode turns up — something none of the above covers —
that's not just a nuisance to work around, it's the raw material for a system fix. Run
`agentsmith new-feedback "symptom"` and walk it through the loop; the next person gets a
guard instead of the same surprise ([`09-adapting-it-to-your-team.md`](09-adapting-it-to-your-team.md)).
