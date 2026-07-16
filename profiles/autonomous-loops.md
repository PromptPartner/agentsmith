<!-- PROFILE · autonomous-loops -->
## Profile: Autonomous Loops & Unattended Agents

**Use this profile when** the agent's work takes effect without a human in the verification path — a scheduled or cron agent, a `/loop` run, a long multi-agent orchestration whose steps you won't read. The test isn't "is it on a timer," it's **"if this is wrong, will anyone notice before it lands?"** If you're watching each step and approving it, you don't need this profile — `core/10` already covers that. A harness is one session's setup; a **loop is a harness plus a schedule, durable state, and a verification chain**. This profile governs the difference.

### What "done" and "verified" mean here
Sharpens R2/R5 for work nobody watched.

- A result is **verified** only when a *separate* checker approved it — different agent, different instructions, ideally a stronger model — **and that checker measured something the maker structurally cannot fake.** A second opinion on the maker's own summary is not verification, it's theater. Re-running the check is verification; reading the claim that it passed is not.
- **The maker never marks its own work done.** The checker's default stance is **REJECT** until the evidence is strong. "Tests passed" from the implementer is a *claim*; the checker runs them itself and quotes the output.
- A loop is **done for the run** when its state file says what it did, what it skipped, and what's waiting on a human — readable without opening a chat log.
- **Running is not working.** A loop that runs clean but produces output nobody reads has failed; it's just spending. Measure it against the metric you named, don't admire the green checkmark.

### The loop design rules (load-bearing)
1. **Earn autonomy in stages — never skip L1.** L1 report-only (writes state, takes no action) → L2 small auto-wins (separate checker + isolation + attempt cap) → L3 unattended (only with denylist, budget, metrics, and human gates). Roughly two weeks of L1 with <20% noise before L2. Report-only *is* the calibration phase; skipping it means acting on a signal you never checked.
2. **Maker/checker split, always.** The agent that did the work is the worst judge of it (R2). Split the roles, and make the check one the maker can't satisfy by assertion.
3. **Cap attempts mechanically, and persist the count.** Three tries on one item, then escalate with full context. This sharpens `core/40`'s stop-rule for the unattended case: a fresh run has no memory of the last two attempts, so the count must live **in the state file**, not in a context window. Never widen a threshold to keep looping — escalation is a feature, not a failure.
4. **State is the spine.** One durable, committed state file per loop, outside any conversation. Read it at the start of every run, write outcomes and timestamps at the end, and **prune** resolved/merged/closed items every run — or the loop acts on ghosts. It is usually the most important artifact the loop produces (R9).
5. **Budget and kill switch before the first unattended run.** A daily token cap, a rule that degrades to report-only at ~80%, and a documented one-move stop you have actually tested. No budget, no cap, no L3.
6. **Denylist the blast radius.** Secrets, auth, payments, billing, infra/prod, migrations: never auto-edited, always escalated (R8). Default to **no auto-merge**; scope connectors read-only until trust is earned; the smallest diff that works, never an opportunistic refactor.

### Quality gates
Tick each before enabling a loop or raising its level — "deferred: reason" is allowed, silence is not:
- [ ] **One-sentence goal** and explicit **non-goals**; the watched scope named (which repo, branch, tickets).
- [ ] **Checker is separate** from the maker, and measures something the maker cannot fake.
- [ ] **Attempt cap** set (≤3) with an escalation path, and the count persists in state.
- [ ] **State file** documented: read-at-start, write-at-end, prune-every-run.
- [ ] **Budget** set with a degrade rule, plus an append-only **run log** (found / did / escalated).
- [ ] **Denylist and no-auto-merge** in force; connectors at minimum permission (R8).
- [ ] **Kill switch** documented and *tested* — you have actually stopped it once.
- [ ] **One full report-only cycle observed end-to-end** (R3) before it runs unattended.
- [ ] **Success metric named**, with a review date to confirm it still earns its cost.
- [ ] Every defect the loop finds — and every defect *the loop itself causes* — filed (R7).

### Failure modes to guard against
- **Verifier theater** — the checker "approves", then CI or review finds the obvious bug. It read a claim instead of running the check. The deep version: a checker that *can't* catch the failure mode. An LLM second-opinion on a backtest cannot detect overfitting, because the backtest is already the overfit artifact. Ask what this check would have to catch, and whether it structurally can.
- **Infinite fix loop** — the same item, five-plus attempts, never converging. Usually a weak checker, a misdiagnosed root cause (R1), or a flake treated as a regression.
- **State rot** — state cites merged PRs and closed tickets; the loop acts on ghosts.
- **Fixing flakes with code** — the loop makes an intermittent test green by disabling it or bumping a timeout. Classify and quarantine; never disable a test to go green.
- **Token burn** — the full pipeline fires on an empty watchlist. Cheap triage first; spawn nothing when there's nothing to do.
- **Over-reach** — asked for one fix, refactored the module. Smallest diff; the checker verifies which files were touched (R4).
- **Notification fatigue** — it pings every run, so the one real escalation gets missed. Notify only when a human must act.
- **Comprehension debt** — the loop ships work nobody read. Faster loops make this worse, not better. Read what it made.
- **Cognitive surrender** — the loop runs and you stop having opinions. Designing loops with judgment is the cure; using them to avoid thinking is the accelerant. Same action, opposite outcome.

### Recommended skills & tools
The native primitives already cover this — keep the surface small (R10) and resist bolting on a loop framework:
- **`/loop` and `/schedule` (+ cron)** — the scheduler. Prefer a long interval and a real wake condition over tight polling; a loop that wakes to find nothing should exit cheap.
- **Subagents for the maker/checker split** — the load-bearing one. A separate agent, instructed to *find reasons to reject*, on a stronger model for anything unattended (`core/40`).
- **Worktree isolation** (`isolation: "worktree"`) — one worktree per attempt whenever a loop edits files in parallel; discard it on reject.
- **A committed state file + run log** — in the repo or the tracker (R7). Durable and outside the chat, or the loop has amnesia every run (R9).
- **Skills** — encode conventions and "we don't do it this way, because X broke" once, so the loop doesn't re-derive them cold on every run.
- **`/verify` and the project's own checks** — what the checker actually executes. The check must be one the maker can't fake.

### Addendum to the STOP table
| Thought | Reality |
|---|---|
| "The verifier approved it." | Did it *run* the check, or read the maker's claim? An approval quoting no output is theater. |
| "Let it keep trying, it'll converge." | Three attempts is the cap. The fourth is a fresh guess wearing the last three as a costume — escalate. |
| "I'll add the budget and kill switch once it works." | The run that needs the kill switch is the one you didn't expect. No budget, no cap, no unattended run. |
| "It's been running clean all week." | Clean ≠ useful. If nobody reads its output, it isn't working — it's spending. |
| "Skip L1, report-only is boring." | Report-only is the calibration phase. Skipping it means trusting a signal you never measured. |
