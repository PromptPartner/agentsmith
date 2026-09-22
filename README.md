# AgentSmith

**Proof before done.**

**Give your coding agent project rules, a definition of done, and a way to prove the work.**

AgentSmith installs a shared operating agreement and work-specific profiles into a project. The agent reads those rules, works on a bounded task, runs the project's checks, exercises the real path, records evidence, and leaves a handoff the next session can validate. You choose the task and retain control of external writes. AgentSmith is a local Python tool; no account or hosted service is required.

![AgentSmith flow: project rules and profile, bounded agent work, automated checks and real-path exercise, evidence, then handoff and resume.](site/assets/agentsmith-flow.svg)

The [flow guide](docs/README.md#how-the-loop-works) describes each step. The SVG is editable and has a text description for screen readers.

## See one real loop

The [First Verified Loop proof](docs/demos/first-verified-loop/README.md) records an intentionally failing readiness test, the correction, three passing verification phases, and a real command that reports `NOT READY` for incomplete checks. It includes a verification receipt and handoff/resume pair. This is a sanitized, reproducible fixture, not proof that every agent or operating system behaves identically.

## Guided path — try it in a disposable project

Requires Python 3.11 or newer and Git. No third-party Python package is needed.

```bash
git clone https://github.com/PromptPartner/agentsmith.git ~/tools/agentsmith
cd ~/tools/agentsmith
python3 agentsmith.py demo first-loop --target /tmp/agentsmith-first-loop
```

The command refuses a non-empty target and prints the next steps and cleanup boundary. Follow the [guided first hour](docs/02-your-first-hour.md). On Windows, use `py -3` and a disposable Windows target; see [installation](INSTALL.md).

## Experienced path — install in an existing project

To install directly:

```bash
./setup.sh --agent codex --profile software-dev --target /path/to/project
# Windows: pwsh ./setup.ps1 --agent codex --profile software-dev --target C:\path\to\project
```

Run `python3 agentsmith.py status --target /path/to/project` to inspect the setup. Preview installation with `./setup.sh ... --dry-run`. The [installation guide](INSTALL.md) covers safety modes, profiles, updates, and removal.

## Agent support, with evidence boundaries

| Agent clients | Current status | What the status means |
|---|---|---|
| Claude Code, Codex | Native integrations; certification passed | AgentSmith configures their documented local instruction and runtime surfaces. Dated native-client evaluation records exist. |
| GitHub Copilot, Cursor, Gemini CLI, Windsurf / Devin, Cline, Roo Code, Aider, Continue, OpenHands, Goose, OpenCode, JetBrains Junie, Zed, Jules | Certification targets; certification pending | Each has an adapter and a registry-contract fixture only. Client behavior and native runtime remain unverified or unsupported as marked in the registry. |

The [machine-readable registry](config/agents.json) is authoritative. Read the [compatibility contract](docs/22-compatibility-contract.md) for the evidence required for each claim.

## Go deeper

- [Documentation map](docs/README.md) — start by task.
- [First Verified Loop proof](docs/demos/first-verified-loop/README.md) — inspect red, green, real-path, receipt, and handoff artifacts.
- [Verification and evidence](docs/03-verify-means-evidence.md) — what a passing check proves.
- [Profiles](docs/07-how-to-pick-a-profile.md) — choose the quality gate for the work.
- [Safety model](docs/15-safety-model.md) — what can write where and when consent is needed.
- [Troubleshooting](docs/17-troubleshooting.md) — diagnose install or runtime problems.

MIT licensed. See [LICENSE](LICENSE) and [credits](docs/18-influences.md). Built by PromptPartner.
