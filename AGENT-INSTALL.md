# Installing AgentSmith for a user

Use this when a user asks you to install AgentSmith into their project.

## Boundaries

- Read before writing. Inspect the target project and choose a profile from `profiles/` based on
  evidence in its files.
- Ask which agent IDs or group they want only if their request does not already say. Availability
  is not authorization for external systems.
- Run a dry-run first and show the concrete destinations.
- Never place credentials in tracked files.
- Do not describe a client as fully compatible because it reads `AGENTS.md`; report instructions,
  skills/MCP, and native runtime separately.

## Procedure

1. Ensure Python 3.11+ is available.
2. Clone or locate this repository outside the target project.
3. Inspect the target and select a work profile. `--profile auto` is acceptable when its detected
   choice matches the files you observed.
4. Preview:

   ```bash
   ./setup.sh --agent <id|group> --profile <profile> --dry-run --target /path/to/project
   ```

   On Windows use the identical arguments through `pwsh ./setup.ps1`.
5. Explain that project `AGENTS.md` is canonical. Claude gets a generated `CLAUDE.md`; Gemini,
   Aider, Continue, and Goose receive minimal managed adapters when selected.
6. Run the real install. Add `--with-skills`, MCP, or hooks only when the user asked for those
   capabilities or they clearly belong to the approved setup scope.
7. Verify:

   ```bash
   python3 agentsmith.py doctor --agent <id|group> --target /path/to/project
   ```

   Confirm the generated paths and inspect one assembled instruction example end to end.
8. Report unsupported/unverified capabilities explicitly. Do not claim live-client certification
   from fixture output.

The current IDs, groups, OS constraints, and evidence are in `config/agents.json`. The detailed
installation reference is `INSTALL.md`.
