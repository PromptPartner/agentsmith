# Best practices — dos & don'ts, earned the hard way

Nothing below is general advice. Every entry traces to a real incident — on this harness or the
production project it was distilled from — and each one names the guard that now exists because
of it. (The full post-incident write-ups follow the [`feedback/`](feedback/README.md) convention;
the incidents are retold inline here so the lessons travel with the repo.)

**Encode thresholds with their direction — and keep one source of truth.**
An operator asked for handoffs "when context *reaches* 25–30%." It shipped as 25–30% *left* —
one misread word, silently compiled into a 70%-used default, then copied across six files, where
it survived review because every copy agreed with every other copy. *Do:* keep a magic number in
exactly one place, and state the direction and the *why* wherever it's mentioned ("~25–30%
**used** — hand off early, while the model is in its quality band"). *Don't:* let prose restate
what code defines.

**Availability is not authorization.**
Setup asked where the team tracks work. The assembler quietly compiled that *location* answer
into *permission*, and the agent began filing issues and posting comments in the operator's live
tracker — unasked. Nothing malfunctioned; the harness did exactly what its rules said, which is
the scary version. *Do:* treat "the connection exists" and "you may write there" as two separate
consents — the second explicit, opt-in, and durable once given. *Don't:* let any connected tool
(tracker, CRM, mail, chat) be writable by inference; the tracker is merely the cheap version of
this failure. *Guard:* a consent test suite runs in `verify.sh` and fails if naming a tracker
ever grants writes again — and upgrades fail closed to ask-first.

**Reminders don't hold. Guards do.**
A setup re-run had a known trap that blanked the operator-identity fields in a config file. The
session that hit it wrote an explicit, correct warning into its handoff note. The *next* session
read that warning at startup — and walked into the same trap anyway, because the dangerous moment
didn't feel dangerous (a measurement, not a change). What finally held was code: recovery logic
on the re-run path plus a test suite that goes red if the bug returns. *Do:* for anything that
must hold 100% of the time, land a deterministic guard — a hook, a verify phase, a test. *Don't:*
write the third, louder warning. If a rule needs ALL CAPS, it wants to be a hook.

**Verification has a shelf life.**
Files that had to survive being untracked were verified present on disk — real evidence, at that
moment. Four git operations later (checkout, merge, `reset --hard`), git deleted them: the old
branch still tracked them, so the reset did exactly its job. Recovery took two minutes only
because history still held copies. *Do:* re-verify *after the last destructive operation*, and
check the exact claim you're about to report at the moment you report it. *Don't:* trust
"untracked + gitignored = safe" across branch operations, and don't let an early check stand in
for a final one.

**Automate the check you're tempted to do by eye.**
Keeping a to-be-published tree free of private names was a careful manual review — until it
became a small gate script. On its first run the gate caught the operator's real name in the
`--help` output of both setup scripts (a surface no human sweep had looked at), and then flagged
its own first draft for spelling out the very terms it scans for. *Do:* turn any recurring
by-eye check into a gate; gates search where nobody thinks to look. *Don't:* exempt paths or
allow-list findings to make a gate pass — fixing the gate's input is the fix.

**Docs drift is a defect, not a chore.**
An earlier version of *this very file* claimed the shipped settings enable full-bypass
permissions. That had been true once; by the time it was caught, the wizard default had long been
**cautious** (edits auto-apply; shell and network prompt) — so the doc was telling newcomers the
harness ships more dangerous than it does. *Do:* update every doc a change makes wrong *in the
same unit of work* (R6) — stale docs don't just lag, they actively misinform the people with the
least context. The accurate permissions story lives in README → "Permissions & dangerous mode."

**The standing habits behind the stories** — context is the scarce resource (hand off at ~25–30%
used; keep static rules lean and push knowledge into skills/docs — see
[`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)); keep the surface
small (install plugins/skills per need, review third-party ones before installing — they run
shell commands); match rigor to stakes (throwaway work can be loose; anything touching users,
money, or production gets the full treatment); and when the agent stumbles, fix the system, not
the symptom (`core/60-evolving-the-harness.md`).
