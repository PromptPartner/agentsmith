# Compatibility contract

AgentSmith reports compatibility in three independent dimensions. A client reading Markdown does
not imply that it loads Agent Skills, accepts MCP configuration, or supports hooks.

1. **Instructions** — discovery of the canonical root `AGENTS.md`, global/project scope, and
   nested-rule behavior.
2. **Skills and tools** — Agent Skills directories and MCP support. Client support and AgentSmith
   management are separate fields.
3. **Native runtime integration** — supported hooks, per-capability doctor checks, and managed
   install/update/uninstall behavior.

The machine-readable source is [`config/agents.json`](../config/agents.json); its
closed vocabulary and shape are documented by
[`agents.schema.json`](../config/agents.schema.json). `target_tier` is the intended support contract.
`certification` records whether evidence has satisfied it. A target with
`target_tier: certified` and `certification: pending` is a roadmap target, not a compatibility
claim.

## Support tiers

- **Native:** AgentSmith manages instructions, skills, supported MCP and hooks, doctor checks, and
  the install/update/uninstall lifecycle.
- **Certified:** real-client evidence proves instruction discovery and every capability claimed
  for that client; a thin adapter may be used where the client requires configuration.
- **Community-compatible:** the client is expected to consume `AGENTS.md`, but this project does
  not test or manage it.

Claude Code and Codex are the native-tier targets. The certified-tier matrix contains GitHub
Copilot, Cursor, Gemini CLI, Windsurf/Devin, Cline, Roo Code, Aider, Continue, OpenHands, Goose,
OpenCode, JetBrains Junie, Zed, and Jules. Tabby and LM Studio are not agent targets: they are
model backends. LM Studio, Ollama, and other local providers are reported only as part of a
client-plus-model scenario.

## Canonical instructions and adapters

`AGENTS.md` is the one portable, independently editable instruction artifact. Direct consumers
read it unchanged. Claude receives a generated `CLAUDE.md` copy. Gemini is configured to select
`AGENTS.md`; Aider, Continue, and Goose receive the smallest managed configuration that points to
it. Generated or configured surfaces must not introduce symlinks, proprietary imports, or a
second editable copy of the core.

The canonical Agent Skills pack lives in `.agents/skills`. A runtime-specific copy is allowed
only when the client genuinely requires it; Claude's `.claude/skills` adapter is the known native
case. Registry `skill_directories` list only paths the client discovers;
`managed_skill_directories` separately lists every canonical or derived surface AgentSmith owns.
Claude discovers only `.claude/skills`; AgentSmith preserves canonical customizations in
`.agents/skills` and regenerates the Claude adapter from those effective bytes. A skill's behavior
must come from its declared compatibility metadata, never merely from the directory in which it
happens to be installed.

## Evidence vocabulary

| Type | What it proves | What it does not prove |
|---|---|---|
| `fixture` | Paths, generated config, parsing, ownership, idempotence, and uninstall behavior. | That a real client discovered or obeyed the instructions. |
| `observed` | An automated run of the named client captured the end-to-end result. | Behavior on untested client versions, operating systems, or providers. |
| `manual` | A dated human-observed run covered a closed IDE or cloud surface. | Repeatability outside the recorded environment. |

A fixture alone can never set `certification` to `passed`. A certification record must name the
client version, OS, date, scope, and evidence artifact. Nondeterministic functional scenarios run
three times and require two successes; instruction discovery must succeed every time, while any
secret, destructive-action, or external-write violation fails certification. Local-model records
also capture the model digest, context window, hardware class, and latency in their evidence
artifact.

Real-client and local-model records live under [`compatibility/evaluations/`](../compatibility/evaluations/)
and validate against schema v2. `agentsmith evaluate --agent claude|codex|native` supplies the eight
foundation scenarios. Its default dry run resolves clients, commands, scenarios, isolation, and
budgets without invoking a model. Live runs require `--live` and explicit positive budgets; raw
logs remain outside tracked files. No dated records are bundled until an observed/manual run has
actually occurred and its failures have been inspected.

Native evaluation isolation includes client configuration, not just the temporary project. Codex
runs from an ephemeral client home with a single-file bridge to validated ChatGPT authentication;
OAuth refresh state remains shared, while inherited global instructions, settings, hooks, plugins,
apps, MCP servers, and API-key authentication are excluded.

Unsupported and unverified are deliberately different. **Unsupported** is an explicit boundary;
AgentSmith will not emulate it to make a matrix cell green. **Unverified** means no claim is made
until evidence exists. Compatibility output and doctor must preserve that distinction and report
each dimension separately.
