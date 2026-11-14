# Install AgentSmith with an AI agent

Use this guide when a user asks you to install AgentSmith, or when you opened a copy of this repository and the user is not developing AgentSmith itself. Keep the experience conversational. The user should make choices about their work, not translate installer flags.

## Safety boundary

- Inspect the target statically. Do not run project code, package scripts, or dependency installers to choose a profile.
- Download only an official stable release from `PromptPartner/agentsmith`.
- Match the release asset to the current operating system and CPU architecture. Verify it against the release's `SHA256SUMS` file before running it and, when the GitHub CLI is available, with `gh attestation verify <file> --repo PromptPartner/agentsmith --signer-workflow PromptPartner/agentsmith/.github/workflows/standalone.yml --source-ref refs/tags/<version>`, using the release tag as `<version>`. If either check fails, do not run the file; report it. The builds are currently unsigned, so macOS and Windows may warn before the first run. Explain the warning to the user instead of suppressing it.
- Never place credentials in project files or command history.
- Show one concrete plan before the first write. Ask once to apply it. Availability of GitHub, a tracker, or any external service is not authorization to write there.

## The guided procedure

1. **Identify the starting point.** Ask whether this is an existing project or a new project. For a new project, ask for an absent or empty folder. Explain that AgentSmith initializes Git but does not select an application framework.
2. **Install the CLI if needed.** Use the latest release asset for macOS, Windows, or Linux, verified as described above. Do not clone the source repository for an ordinary user install. If the latest release has no asset for this platform, stop and explain that source installation is the advanced fallback.
3. **Identify the agent.** Detect Claude Code, Codex, and other supported clients already present. Confirm which should read the rules. Do not claim native certification beyond the evidence in `config/agents.json`.
4. **Recommend one profile.** For an existing project, run `agentsmith profiles recommend --target <path>` and explain the leading recommendation using the reported files. For an empty project, ask what the project will mainly produce and map that answer to the profile table in the main README. Show the full list only when requested or when the evidence is ambiguous. Treat `autonomous-loops` as an optional modifier.
5. **Calibrate explanations.** Ask whether the user is new to programming, is an experienced developer new to AI agents, or already works deeply with AI agents. Do not infer one universal technical level.
6. **Keep project scope and cautious permissions as defaults.** Inside a container, recommend `--safety container`, or `--assemble-only` when the image already sets the agent's permissions. Explain that project rules travel with the repository. Put user-wide rules, layered setups, profile stacks, skills, MCP, hooks, trusted permissions, organization policy, and design-system generation under an advanced choice.
7. **Preview the exact result.** Run the direct command with `--dry-run`. Summarize the target, rule scope, agent clients, profile, permission mode, and every managed destination. Explain preserved foreign content and the uninstall boundary.
8. **Ask once, then apply.** After approval, run the same command without `--dry-run`. For a new project, create the folder and initialize Git only now.
9. **Verify the installation.** Run `agentsmith doctor --agent <selection> --target <path>` and `agentsmith status --target <path>`. Inspect one assembled instruction chain end to end. Report any unsupported client capability or unwired verification phase.
10. **Give one next step.** Usually this is replacing the `unwired` entry in `.harness/verify.conf` with the project's real checks, then assigning one bounded task.

## The setup questions

These are the questions the installer's wizard asks, in its order. Ask them in conversation; do not show the table. `agentsmith wizard schema --json` gives the same list for this computer, including a `container` choice for `safety` inside a container.

<!-- BEGIN GENERATED: wizard questions (from WIZARD_QUESTIONS in agentsmith.py; do not edit by hand) -->
| Key | Question | Answers | Default | Asked when |
| --- | --- | --- | --- | --- |
| `language` | Language | `en` / `de` / `es` / `fr` / `zh-CN` | computed: locale_environment | always |
| `project_kind` | Are you setting up an existing project or a new folder? | `existing` / `new` | `existing` | always |
| `target` | Project folder | a folder path | computed: current_directory | always |
| `agent` | Which agent should use these rules? | agent ids or groups, comma separated | computed: agent_detection | always |
| `goal` | What will this project mainly do? 1 software, 2 systems/deployments, 3 marketing, 4 documents, 5 data, 6 administration, 7 research, 8 visual design | `1` software-dev, `2` devops-setup, `3` marketing-outreach, `4` document-creation, `5` data-crunching, `6` general-admin, `7` deep-research, `8` creative-design | `1` | project_kind = `new` |
| `profile` | Use this profile, enter another name, or type 'all' | `recommended` or one profile name | `recommended` (computed: profile_recommendation) | project_kind = `existing` |
| `experience` | Your background: 1 new to programming, 2 developer new to AI agents, 3 experienced with AI agents | `1` / `2` / `3` | `2` | always |
| `safety` | Agent permissions | `cautious` / `trusted` | `cautious` | always |
| `advanced` | Configure advanced options such as user-wide rules, extra profiles, skills, MCP, or hooks? | `y` / `n` | `n` | always |
| `scope` | Rule scope | `project` / `user` | `project` | advanced = `y` |
| `extra_profiles` | Extra profile names, comma separated | profile names, comma separated | none | advanced = `y` |
| `capabilities` | Optional capabilities, comma separated: skills,mcp,hooks,handoff-hooks,ui-design-hook,memory-startup | `skills` / `mcp` / `hooks` / `handoff-hooks` / `ui-design-hook` / `memory-startup` | none | advanced = `y` |
| `confirm` | Apply this plan? | `yes` / `no` | `yes` | always |
<!-- END GENERATED: wizard questions -->

## Without the CLI

Use this path only when you cannot run commands, for example in a chat-only session, or when the user declines the CLI.

1. **Ask the same questions.** Ask the starting point (`project_kind`), the main kind of work (`goal`, or the profile for an existing project), and the user's background (`experience`). Ask their name and role. Skip the questions that only the CLI can act on, such as `agent`, `safety`, and `capabilities`.
2. **Assemble the rules by hand.** Copy every file in `core/` in file-name order. Then add a line `---`, a heading `# Work-Type Profile(s): <profile>`, and the text of `profiles/<profile>.md`. Put the first two comment lines of the root `AGENTS.md` above it (the `BEGIN AGENTSMITH` marker, then the `Generated. Profiles:` line with your profile name), and its `END AGENTSMITH` line below it, so a later CLI install can manage the block. Leave out the routing note that stands above the markers.
3. **Fill in the operator line.** Replace `{{OPERATOR_NAME}}` and `{{OPERATOR_ROLE}}` with the answers, and `{{OPERATOR_BIO}}` with one or two sentences about the user's background. Replace `{{TRACKER}}` with where defects are recorded (for example `KNOWN-ISSUES.md`), and `{{TRACKER_POLICY}}` with "writes are NOT authorized: draft the entry for the operator to post" unless the user allows writes. Replace any other placeholder with `[TODO: set NAME]`.
4. **Hand it over.** Save the result as `AGENTS.md` at the root of the user's project, or give it to the user to save when you cannot write files. Claude Code reads `AGENTS.md` only when no `CLAUDE.md` exists; otherwise add the line `@AGENTS.md` to `CLAUDE.md`.
5. **Say plainly that nothing was verified.** No doctor check ran, no status report exists, no native safety settings were written, and the project's verify phases are not wired. Recommend a CLI install later, which replaces the hand-made block in place.

## Direct command shape

Use direct flags only after translating the conversation into a reviewed plan:

```console
agentsmith install --agent <id-or-group> --profile <profile> --safety cautious --dry-run --target <project>
agentsmith install --agent <id-or-group> --profile <profile> --safety cautious --target <project>
agentsmith doctor --agent <id-or-group> --target <project>
```

For a new project, initialize the approved empty directory with Git before the real install. For user-wide or layered setups, follow the explicit commands in [INSTALL.md](INSTALL.md#where-the-rules-live).

When another program already collected the wizard's answers, run `agentsmith install --answers <file> --dry-run`, then the same command without `--dry-run` after approval. The questions and their valid answers come from `agentsmith wizard schema --json`.

## Report format

Tell the user:

- what was installed and where;
- why the profile was selected and which files supported it;
- what the doctor check proved;
- what remains unwired or unverified;
- the single recommended next action.
