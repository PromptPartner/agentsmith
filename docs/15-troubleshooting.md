# Troubleshooting — when it's behaving oddly

This is the operational FAQ: the agent is running but doing something you didn't expect. It's the
*runtime* companion to [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)
— that doc is for when a rule you wrote didn't take; this one is for symptoms you observe while
working. Find the symptom, understand the cause, apply the fix.

**"It asks permission for every shell command."** Working as intended — you're in **cautious**
safety mode (the wizard default): edits auto-apply, but shell and network prompt. If that's more
friction than you want *on a machine you own*, switch to trusted; if it's a shared or client box,
keep it. How to change it: README → "Permissions & dangerous mode", or [`14-safety-model.md`](14-safety-model.md).

**"It ran a command I didn't want it to."** The inverse — you're in **trusted**
(`bypassPermissions`), which runs most tool calls without asking. Dial back to cautious the same
way. If this happened on a shared/prod machine, that's the signal to lock it from above with
`--org-policy` ([`14-safety-model.md`](14-safety-model.md)).

**"It keeps trying the same fix and won't stop."** The stop-rule in `core/40` says two identical
failures means re-diagnose, not retry — but a loop or a long run can slip it. The cause is usually
a wrong root-cause diagnosis (R1) or a flake treated as a regression. Interrupt it, and make it
state its hypothesis before the next attempt rather than firing a third blind try. In a loop, this
is exactly what the attempt cap (three, then escalate) is for — if it's not capping, the count
isn't persisting in the state file ([`06-your-first-loop.md`](06-your-first-loop.md)).

**"It said 'done' but the work wasn't actually verified."** Almost always a stub `verify.conf`. A
fresh install ships a placeholder phase that just echoes, so `verify.sh` passes vacuously until you
wire real checks. Replace the sanity line with your build/test commands — that's what makes "done"
mean something ([`03-verify-means-evidence.md`](03-verify-means-evidence.md)).

**"The context-% handoff nudge didn't fire."** Expected — it's best-effort by design. No hook can
reliably read live context usage (a documented Claude Code gap; details in
[`research/claude-code-hooks-and-managed-policy.md`](research/claude-code-hooks-and-managed-policy.md)),
so the % nudge is fragile. Use the reliable path: watch the `ctx:NN%` gauge in the statusline and
say **"handoff"** yourself around 25–30% used. The keyword trigger is solid; the auto-nudge is a
bonus, not the mechanism.

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
fix are in [`14-safety-model.md`](14-safety-model.md) and [`13-project-tracker-guide.md`](13-project-tracker-guide.md).

**"Re-running setup changed my operator name / role."** Current setup *recovers* your identity from
the existing managed block before re-rendering, so a re-run preserves it. If you're on an older
harness and a `--global` re-run blanked it, pass the fields explicitly (`--operator-name …
--operator-role …`) and update — the recovery behaviour is the fix for exactly this. Your previous
`CLAUDE.md` was backed up before the write, so nothing is lost.

**"Files disappeared after a git operation."** Not the harness — a `git reset --hard` or a branch
switch does exactly what it's told, and can remove files that were tracked in one commit and not
another. Recover from the backup or from history. The durable lesson (re-verify a preservation
claim *after* the last destructive step, not after the one that preserved it) is in
[`10-best-practices.md`](10-best-practices.md).

**"The rules don't seem to apply in my tool."** Check the surface. Web (claude.ai/code) and iOS get
the *rules* but no local hooks, skills, or scripts; only local Claude Code gets the full harness.
Other agents (Codex, Gemini CLI) need their own rule file emitted — see
[`12-platforms-and-tools.md`](12-platforms-and-tools.md).

**Still stuck?** If a genuinely new failure mode turns up — something none of the above covers —
that's not just a nuisance to work around, it's the raw material for a system fix. Run
`./scripts/new-feedback.sh` and walk it through the loop; the next person (or the next you) gets a
guard instead of the same surprise ([`09-adapting-it-to-your-team.md`](09-adapting-it-to-your-team.md)).
