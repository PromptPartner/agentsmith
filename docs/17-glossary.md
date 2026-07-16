# Glossary

The harness vocabulary, one entry each, with a pointer to where the concept properly lives. For
an expert developer, most of the friction here is words — clear that, and the rest reads itself.

## The foundation

- **Harness** — everything around the model: rules, tools, memory, guardrails, hooks,
  orchestration, feedback loops. The ~90% of agent behavior you control. The model is the ~10%
  you don't. → [`01-harness-philosophy.md`](01-harness-philosophy.md)
- **Agent** — the model *plus* the harness, running with autonomy. Not a chatbot with tools.
- **Context window** — the model's working memory for a session. Finite, and quality degrades as
  it fills — which is why sessions hand off early (~25–30% used), not when full.
- **Static context** — what's loaded *every turn* and paid for every turn: the assembled
  `CLAUDE.md`. Rationed hard (600 lines / ~10k tokens here). → [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md)
- **Dynamic context** — loaded only on demand: skills, docs, memory, tool results. Free until used.
- **`CLAUDE.md`** — the assembled rulebook the agent re-reads every turn. A contract, not a
  config file — nothing parses it; the agent *understands* it. → [`02-your-first-hour.md`](02-your-first-hour.md)
- **Managed block** — the `<!-- BEGIN AGENTSMITH … -->` region of `CLAUDE.md` that setup owns and
  rewrites. Anything outside it is yours and survives re-runs.

## The rulebook's parts

- **Core** — the universal layer (`core/00`–`60`): identity, operating model, the ten principle
  rules, the STOP table, tool discipline, git & handoff, system evolution. Never changes between
  projects.
- **Profile** — the work-type layer: what "done" and "verified" mean for software vs devops vs
  research vs…, plus that work's quality gates and failure modes. One or more per project;
  stack them, dominant first. → [`07-how-to-pick-a-profile.md`](07-how-to-pick-a-profile.md)
- **R1–R10** — shorthand for the ten principle rules (R2 = prove it, R8 = no secrets, R9 =
  research never deleted…). Profiles cite them by number rather than restating them.
- **STOP table** — a list of *rationalizing thoughts* ("I'll verify later", "too small to
  check") paired with the failure each precedes. The anti-rationalization layer.
- **Operator** — you: the human who picks the work, owns direction, and accepts the risk.

## Operating

- **Unit of work** — one tracked item per session; its description is the contract.
- **Session** — one conversation-length run: kickoff → plan → do → verify → finalize → handoff.
- **Handoff** — the end-of-session protocol: safe-state the work, write the memory note, emit a
  kickoff block. The only bridge across sessions — a fresh session remembers nothing.
- **Kickoff prompt** — the paste-ready block a handoff produces; starting a session with it is
  how work resumes.
- **Conductor / orchestrator** — the two altitudes within a session: hands-on watching each
  change vs delegating to subagents and reviewing outcomes. Surprise → drop to conductor.
- **Subagent** — a child agent dispatched for a self-contained piece of work, reporting back a
  summary. The parallelism primitive.
- **Skill** — a named, on-demand procedure the agent can invoke (`/handoff`, `/verify`).
  Dynamic context: costs nothing until triggered.
- **MCP** — Model Context Protocol; how external tools/services (trackers, CRMs, browsers) are
  wired in. A *connected* tool is not a *writable* tool — see availability vs authorization.
- **Tracker** — wherever your team records work (GitHub issues, Linear, a markdown file). The
  harness treats naming it and being allowed to write to it as two different consents.
  → [`13-project-tracker-guide.md`](13-project-tracker-guide.md)

## Verification

- **Evidence** — an artifact a check produced (failing→passing test, wire response, rendered
  page). The opposite of a claim. → [`03-verify-means-evidence.md`](03-verify-means-evidence.md)
- **Test vs eval** — tests prove the deterministic part (input → output); evals judge the part
  that needs judgment (right approach? quality bar met?). Most real work needs both.
- **Quality gate** — a profile's concrete pre-"done" checklist for its kind of work.
- **Guard** — a deterministic check outside the model — a hook, a verify phase, a test — that
  fails mechanically when a rule is broken. "Guardrails hold what prose forgets."
- **Hook** — code that runs at a lifecycle point (pre-commit, pre-tool-call) and can block the
  action. The strongest kind of guard.
- **`verify.sh` / `verify.conf`** — the project's "is this shippable?" gate and its definition:
  `label :: command` phases, run in order, first failure stops.

## Loops (unattended work)

- **Loop** — a harness plus a schedule, durable state, and a verification chain; work that lands
  with no human watching. → [`05-operating-modes.md`](05-operating-modes.md), `profiles/autonomous-loops.md`
- **Maker / checker** — the mandatory split: the agent that did the work never judges it; a
  separate checker (default stance: reject) reruns the checks itself. Real only if it measures
  something the maker can't fake.
- **L1 / L2 / L3** — the autonomy ladder: report-only → small auto-wins → unattended. Each level
  earned, never skipped.
- **State file** — the loop's committed, durable memory: read at run start, written at run end,
  pruned every run. Holds the attempt counts.
- **Attempt cap** — three tries per item, then escalate to a human. Persisted in state, because
  a fresh run remembers nothing.
- **Kill switch** — the documented, *tested* one-move stop for a loop. Untested = hypothetical.

## Improvement

- **System evolution** — the compounding habit: when something goes wrong, fix the system (a
  rule, a gate, a hook), not just the instance. `core/60`.
- **Feedback record** — a numbered post-incident file: evidence → mechanism → bounded edit →
  named surface → non-regression. → [`feedback/README.md`](feedback/README.md)
- **Leanness budget** — the hard cap on static context (600 lines / ~10k tokens), linted by
  `scripts/lint-leanness.sh`. Over budget means move knowledge to dynamic context, not grow the file.
