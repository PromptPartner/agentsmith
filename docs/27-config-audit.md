# Local configuration audit

`agentsmith audit-config` reads selected project configuration and reports static
security concerns. It is advisory: findings alone leave its exit status at zero.
Use `--fail-on high` to make high or critical findings fail CI. An incomplete
inspection always returns status 2; a severity gate returns 1.

```sh
agentsmith audit-config --target /path/to/project
agentsmith audit-config --target /path/to/project --json --fail-on high
agentsmith audit-config --include-user
```

Project inspection covers Claude settings and hook JSON, Codex TOML and hook JSON,
MCP declarations, and canonical instruction files. `--include-user` adds known
Claude and Codex configuration under your home directory, including `~/.claude.json`.
User configuration is excluded by default. `--include-user` honors `CODEX_HOME`
for Codex; Claude configuration relocated through environment overrides, managed
system policy and plugin configuration are outside
this first release's selected paths. Reports describe inspected paths explicitly;
they do not infer effective settings after client precedence or host overrides.

The version 1 JSON report separates `inspected`, `absent`, `unsupported` and
`unreadable` paths, includes `complete`, and gives each finding a `rule_id`, severity,
path, location, message and remediation. No source snippets or credential values
are included. Terminal controls and secret-shaped values are removed from labels.

| Rule | Meaning |
| --- | --- |
| `credential-exposed` | A secret pattern, credential field, URL password or Authorization bearer header contains a possible literal credential. |
| `shell-permission-broad` | A shell permission grants arbitrary command access. |
| `permission-bypass` | Permission checks or approval prompts are disabled. |
| `trusted-mode` | A setting explicitly enables trusted operation without containment. |
| `download-execute` | A hook or MCP launcher matches a static download-and-execute command pattern. |
| `package-unpinned` | A launcher matches an `npx` or `uvx` command without an exact numeric package version. |

MCP URL passwords and Authorization bearer values are checked without printing
them. `${ENV}` and `$ENV` references remain safe placeholders.

Command checks recognize simple command positions, separators, environment
prefixes and bounded shell wrappers. Printed command text is treated as an argument.
This is a static pattern check, not a full shell parser or evidence of execution;
complex shell syntax can require manual review.

Trusted mode is reported explicitly and left unchanged. `approval_policy = "never"`
alone is medium severity because the separate sandbox may still restrict execution.
`danger-full-access` and Claude's bypass mode are high severity. Review findings in
context; a deliberate trusted setup can legitimately keep these settings.

Reads are bounded to 1 MiB per known file. Symlinked entries, malformed JSON/TOML,
duplicate JSON keys, excessive nesting, invalid inspected configuration structures and unreadable
files make the report incomplete. Non-command hook types are explicitly unsupported
and make inspection incomplete. Reads require descriptor-relative no-follow support;
platforms without it report unsupported paths rather than risk following a link. Codex TOML inspection requires Python 3.11's
standard-library `tomllib`; older Python reports it as unsupported. An empty set
of present configuration files is reported through `absent`, rather than invented
configuration. The audit runs no configured command, contacts no MCP server,
reads no transcripts and changes no files. Passing these selected static checks
makes no containment claim.

## Provenance

Selected check categories were inspired by Affaan Mustafa's
[Everything Claude Code](https://github.com/affaan-m/everything-claude-code) and
[AgentShield](https://github.com/affaan-m/agentshield): exposed credentials,
permissions, hook execution and MCP launcher risks. AgentSmith's implementation
is original Python using its existing secret detector and redactor; neither
project nor Node is a runtime dependency.

Configuration paths and permission terminology were checked against official
[Claude settings documentation](https://code.claude.com/docs/en/settings) and
[Codex configuration reference](https://developers.openai.com/codex/config-reference/)
on 2026-10-06.
