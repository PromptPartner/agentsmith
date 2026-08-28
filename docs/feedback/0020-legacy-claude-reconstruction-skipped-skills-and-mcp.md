# Feedback 0020: legacy claude reconstruction skipped skills and mcp

> A harness post-incident. The point is not to fix THIS bug — it's to change the
> SYSTEM so this CLASS of mistake is less likely next time (core/60). Keep it small,
> specific, and traceable to the incident. Never delete this; archive if obsolete (R9).

- **Date:** 2026-08-28
- **Status:** applied   <!-- open | applied | wont-fix -->
- **Cost:** A real legacy Claude-only upgrade reported success while silently omitting installed
  skills and MCP capabilities. The operator had to compare `doctor` with the saved plan to catch
  the near-miss before relying on the updated harness.

## 1. Evidence / symptom

On stable `v0.2.1` (`b838a77f`), a pre-manifest Claude-only global installation had skills under
`~/.claude/skills` but no canonical `~/.agents/skills` directory. User-scope Claude MCP configuration
was in `~/.claude.json`. Before updating:

- `doctor --agent claude --target /root` reported `skills stale` and `mcp missing`;
- `update plan --global` reconstructed `capabilities` as `skills: false` and `mcp: []`;
- the saved plan contained zero skill entries in `proposed_changes` and exited successfully.

The resulting core instructions referenced `/writing-rules`, but the skill was never installed.

## 2. Failure mechanism

`reconstruct_pre_manifest_installation()` uses Codex-shaped probes for both agents:

- skill detection checks only `(skill_root / ".agents" / "skills").is_dir()`, while
  `install_skills()` writes both `.agents/skills` and `.claude/skills` for Claude and
  `inspect_skills()` correctly inspects both roots;
- MCP detection applies a TOML table regex to concatenated Claude JSON and Codex TOML. A Claude
  `mcpServers` object cannot match a TOML `[mcp_servers.NAME]` table.

The false reconstruction compounds because the post-update skill health check runs only when
`capabilities.get("skills")` is true. The incorrect value therefore disables the check that should
catch the omitted capability. No legacy Claude-only migration fixture exercises this shape.

## 3. Bounded edit

Reconstruct legacy capabilities per selected agent using the same roots and file formats as the
installer and doctor:

- recognize either canonical `.agents/skills` or Claude's legacy `.claude/skills` as evidence that
  skills were installed;
- parse Claude `mcpServers` as JSON and Codex `mcp_servers` as TOML rather than scanning a combined
  text blob;
- fail planning explicitly if a detected legacy capability cannot be migrated safely;
- make post-update validation compare reconstructed capability evidence with the installed result,
  so a false capability value cannot suppress its own guard.

## 4. Named surface

- Production: `agentsmith.py`, specifically `reconstruct_pre_manifest_installation()` and the
  post-update capability checks.
- Deterministic guard: `scripts/test-update.py`, already the `update` phase in
  `.harness/verify.conf` and part of the three-platform CI matrix.
- Operator warning until fixed: `docs/23-updating-existing-installations.md`.

## 5. Non-regression validation

The new fixtures cover a pre-manifest Claude-only global install containing only `.claude/skills`
plus a `~/.claude.json` `mcpServers` object and no `.agents` directory. They prove:

1. the unfixed implementation reconstructs `skills: false` for the reported global shape;
2. planning after the fix detects both capabilities and refuses with the explicit global MCP
   ownership error, never a successful omission;
3. a supported project apply creates the canonical skill root, keeps the Claude mirror, retains
   Claude JSON MCP, and passes both apply-time and installed-runtime strict health checks;
4. an installation with no selected-agent skill or MCP evidence is not falsely upgraded into those
   capabilities;
5. post-update validation rejects authenticated reconstructed state whose false skill or empty MCP
   value would otherwise suppress its own check.

The full 19-phase local gate passed. PR #22 then passed the repository's cross-platform CI matrix
on Ubuntu, macOS, and Windows, including the updater fixtures on every platform and the existing
POSIX guardrails on Ubuntu.
