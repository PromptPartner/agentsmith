# AgentSmith documentation

AgentSmith gives an AI coding agent rules for your project, a profile for the kind of work, and a checkable path from a task to evidence and a handoff. Start with the route that matches what you want to do.

| I want to… | Start here |
|---|---|
| Try the full loop in a disposable project | [Your first hour](02-your-first-hour.md), then the [First Verified Loop proof](demos/first-verified-loop/README.md) |
| Install it in a real project | [Install and configure](../INSTALL.md), then [pick a profile](07-how-to-pick-a-profile.md) |
| Understand what “verified” means | [Verification and evidence](03-verify-means-evidence.md) |
| Check an agent's actual support | [Compatibility contract](22-compatibility-contract.md) and [registry](../config/agents.json) |
| Run longer work safely | [Autonomous runs](21-autonomous-runs.md) and [parallel work graphs](24-parallel-work-graphs.md) |
| Fix a problem | [Troubleshooting](17-troubleshooting.md) |

## How the loop works

![Flow from project rules and profile through bounded agent work, automated checks and real-path exercise, evidence, and handoff/resume.](../site/assets/agentsmith-flow.svg)

1. **Project rules and profile:** the agreement describes boundaries; the profile says what “done” means.
2. **Bounded agent work:** the agent takes one clear task and makes an inspectable change.
3. **Checks and real path:** automated checks test deterministic behavior; a real invocation checks the path a person would use.
4. **Evidence:** the result is recorded so a completion claim can be checked.
5. **Handoff and resume:** the next session can validate saved state and continue.

The [First Verified Loop](06-your-first-loop.md) walks through this sequence. The [public evidence bundle](demos/first-verified-loop/README.md) shows one concrete run and its limits.

## Full guide

| Topic | Pages |
|---|---|
| Foundations | [Harness philosophy](01-harness-philosophy.md) · [Why rules get ignored](04-why-your-agent-ignored-the-rule.md) · [Operating modes](05-operating-modes.md) |
| Adapt the system | [Choose a profile](07-how-to-pick-a-profile.md) · [Add a profile](08-how-to-add-a-profile.md) · [Adapt it to your team](09-adapting-it-to-your-team.md) · [Best practices](10-best-practices.md) |
| Build and operate | [Designing UIs](11-designing-uis.md) · [What's built in](12-whats-built-in.md) · [Platforms](13-platforms-and-tools.md) · [Project tracker](14-project-tracker-guide.md) · [Wayfinding specs](20-wayfinding-spec-flow.md) · [Updating installs](23-updating-existing-installations.md) |
| Trust and reference | [Safety](15-safety-model.md) · [Securing what you build](16-securing-what-you-build.md) · [Influences](18-influences.md) · [Glossary](19-glossary.md) · [Parallel work graph security](24-parallel-work-graphs-security.md) |

Product templates, demos, and the [spec format](specs/README.md) remain public. Your project research and specs belong in its `docs/research/` and `docs/specs/`, committed where that work is authorized to live.
