# Research: August 2026 harness foundation review

> Source material and findings. Never delete this in a cleanup or history rewrite;
> move it to `docs/research/_archive/` if it becomes obsolete.

## Question / scope

What has to change before AgentSmith can truthfully ship a `0.2.0` foundation release with a
cautious default, one secret scanner, race-safe autonomous state, an authoritative release gate,
effective-state diagnostics, and native behavioral evaluations? This note preserves the source
review, local before-state, attribution correction, and roadmap rationale that led to those six
root-cause batches.

## Sources consulted

Opened 2026-08-26 unless otherwise noted:

- OpenAI, [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/),
  2026-02-11 — repository-local knowledge, progressive disclosure, executable architectural
  invariants, and recurring documentation maintenance.
- OpenAI, [The next evolution of the Agents SDK](https://openai.com/index/the-next-evolution-of-the-agents-sdk/),
  2026-04-15 — sandboxed execution plus snapshot/rehydration for durable long-horizon work.
- Anthropic, [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps),
  2026-03-24 — decomposed work, structured handoffs, planner/generator/evaluator separation, and
  criteria-based evaluation.
- Anthropic, [Agentic coding and persistent returns to expertise](https://www.anthropic.com/research/claude-code-expertise),
  2026-06-16 — observed success tied to verifiable evidence and continuing human judgment.
- Addy Osmani, [Agent Harness Engineering](https://addyosmani.com/blog/agent-harness-engineering/),
  2026-04-19, and [Agentic Code Quality](https://addyosmani.com/blog/agentic-code-quality/),
  2026-08-08 — failures should ratchet into harness changes; quality increasingly rests on
  deterministic constraints around the agent.
- Andrej Karpathy with Stephanie Zhan, [From Vibe Coding to Agentic Engineering](https://www.youtube.com/watch?v=96jN2OCOfLs),
  Sequoia AI Ascent, published 2026-04-29 — disciplined agentic engineering depends on retained
  understanding, taste, judgment, and verifiability.
- Armin Ronacher, [The Tower Keeps Rising](https://lucumr.pocoo.org/2026/7/13/the-tower-keeps-rising/),
  2026-07-13 — the primary source for the observation that software teams require a shared
  architectural language of concepts, boundaries, invariants, ownership, and rationale.
- Existing repository evidence in `docs/research/agentsmith-influences-and-credits.md`,
  `docs/18-influences.md`, `docs/21-autonomous-runs.md`, `docs/22-compatibility-contract.md`,
  `.harness/verify.conf`, `agentsmith.py`, and the shell/Python test suites.

## Findings

### Local before-state evidence

All commands below were run at compatibility HEAD `de6a354` on macOS on 2026-08-26, before the
foundation implementation:

| Command | Observed result | Defect exposed |
|---|---|---|
| `python3 agentsmith.py verify` | exit 1; autonomous suite `41 passed, 1 failed` at “stop leaves durable interrupted state” | stop/controller state-write race is inside the configured gate |
| `bash scripts/test-assemble.sh` | exit 1; `21 passed, 1 failed`; root help did not expose the install flags | assembly suite was stale and omitted |
| `bash scripts/test-tracker-consent.sh` | exit 1; `10 passed, 7 failed`; assertions still extracted removed shell/PowerShell implementation | consent migration suite was stale and omitted |
| `bash scripts/test-operator-identity.sh` | exit 0; `14 passed, 0 failed`; PowerShell execution skipped locally | valid invariant was omitted from the local gate |
| `bash scripts/test-platform-install.sh` | exit 1; `73 passed, 37 failed`; failures included retired RTK/copied-hook/statusline behavior | platform suites mixed retained contracts with obsolete implementation detail |

The ordinary install parser set `--safety` to `trusted` when omitted, while installation and
troubleshooting prose described cautious behavior as the default. The Python `secret-scan`
command implemented four patterns over tracked and untracked working-tree files, whereas the shell
scanner implemented nine patterns and staged-added-lines semantics. `doctor` inspected only a
project `AGENTS.md`; all other capabilities were echoed as declared rather than observed.

### Root-cause decisions

1. Restore cautious as the actual implicit safety contract. Explicit `--safety trusted` remains
   available; silently grandfathering an AgentSmith-managed implicit trusted setting would preserve
   the defect.
2. Keep one standard-library Python scanner and reduce the shell file to a compatibility launcher.
   One implementation must back the CLI, hook, tests, and documentation.
3. Give autonomous lifecycle state one writer. `stop` requests and signals; the active controller
   owns the interruption transition and the state file.
4. Port retained invariants into the shared Python conformance suite before retiring obsolete
   platform assertions. A green subset cannot be the release gate.
5. Make `doctor` resolve effective installed state, including layered instruction duplication.
   Duplication is a warning because self-contained project instructions can be intentional.
6. Gate releases on deterministic fixture evaluations and attended native Claude/Codex baselines.
   Live runs require explicit positive budgets and remain pending until the operator authorizes
   billed client execution.

### Attribution correction

OpenAI’s Codex harness article provides a strong implementation example for repository legibility
and mechanically enforced architecture. It is not the primary source for the broader claim that a
team’s common language is its shared understanding of concepts, boundaries, invariants, ownership,
and rationale. Ronacher states that observation directly in *The Tower Keeps Rising*, so the curated
influences page now credits him first and describes OpenAI as complementary implementation evidence.

## Open questions / what was not checked

- Native Claude and Codex behavioral baselines were not run: no live budget authorization was
  supplied. Client presence/version discovery is read-only; model calls are not.
- Native Windows execution cannot be claimed from this macOS session. The three-OS CI matrix is the
  release authority once the repaired deterministic gate is green.
- Later context-reduction, replayable event sourcing, and architecture-index work belong to
  `0.3.0`–`0.5.0`; they are deliberately outside this foundation note.
