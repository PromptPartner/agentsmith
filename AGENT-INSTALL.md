# Install AgentSmith with an AI agent

Use this guide when a user asks you to install AgentSmith. Keep the experience conversational. The user should make choices about their work, not translate installer flags.

## Safety boundary

- Inspect the target statically. Do not run project code, package scripts, or dependency installers to choose a profile.
- Download only an official stable release from `PromptPartner/agentsmith`.
- Match the release asset to the current operating system and CPU architecture. Verify it against `SHA256SUMS` before running it. On macOS and Windows, also verify the platform signature.
- Never place credentials in project files or command history.
- Show one concrete plan before the first write. Ask once to apply it. Availability of GitHub, a tracker, or any external service is not authorization to write there.

## The guided procedure

1. **Identify the starting point.** Ask whether this is an existing project or a new project. For a new project, ask for an absent or empty folder. Explain that AgentSmith initializes Git but does not select an application framework.
2. **Install the CLI if needed.** Use the latest signed release for macOS, Windows, or Linux. Do not clone the source repository for an ordinary user install. If no supported signed asset exists for this platform, stop and explain that source installation is the advanced fallback.
3. **Identify the agent.** Detect Claude Code, Codex, and other supported clients already present. Confirm which should read the rules. Do not claim native certification beyond the evidence in `config/agents.json`.
4. **Recommend one profile.** For an existing project, run `agentsmith profiles recommend --target <path>` and explain the leading recommendation using the reported files. For an empty project, ask what the project will mainly produce and map that answer to the profile table in the main README. Show the full list only when requested or when the evidence is ambiguous. Treat `autonomous-loops` as an optional modifier.
5. **Calibrate explanations.** Ask whether the user is new to programming, is an experienced developer new to AI agents, or already works deeply with AI agents. Do not infer one universal technical level.
6. **Keep project scope and cautious permissions as defaults.** Explain that project rules travel with the repository. Put user-wide rules, layered setups, profile stacks, skills, MCP, hooks, trusted permissions, organization policy, and design-system generation under an advanced choice.
7. **Preview the exact result.** Run the direct command with `--dry-run`. Summarize the target, rule scope, agent clients, profile, permission mode, and every managed destination. Explain preserved foreign content and the uninstall boundary.
8. **Ask once, then apply.** After approval, run the same command without `--dry-run`. For a new project, create the folder and initialize Git only now.
9. **Verify the installation.** Run `agentsmith doctor --agent <selection> --target <path>` and `agentsmith status --target <path>`. Inspect one assembled instruction chain end to end. Report any unsupported client capability or unwired verification phase.
10. **Give one next step.** Usually this is replacing the `unwired` entry in `.harness/verify.conf` with the project's real checks, then assigning one bounded task.

## Direct command shape

Use direct flags only after translating the conversation into a reviewed plan:

```console
agentsmith install --agent <id-or-group> --profile <profile> --safety cautious --dry-run --target <project>
agentsmith install --agent <id-or-group> --profile <profile> --safety cautious --target <project>
agentsmith doctor --agent <id-or-group> --target <project>
```

For a new project, initialize the approved empty directory with Git before the real install. For user-wide or layered setups, follow the explicit commands in [INSTALL.md](INSTALL.md#where-the-rules-live).

## Report format

Tell the user:

- what was installed and where;
- why the profile was selected and which files supported it;
- what the doctor check proved;
- what remains unwired or unverified;
- the single recommended next action.
