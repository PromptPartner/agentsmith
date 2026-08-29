# Feedback 0022: global update blocked by foreign MCP

> A harness post-incident. The point is not to fix THIS bug — it is to change the
> SYSTEM so this CLASS of mistake is less likely next time (core/60). Keep it small,
> specific, and traceable to the incident. Never delete this; archive if obsolete (R9).

- **Date:** 2026-08-29
- **Status:** applied
- **Fixed release:** `v0.2.3`
- **Cost:** Stable `v0.2.2` blocks every global update on a machine where a selected agent has any
  user-scope MCP server. The operator found the released regression by tracing the configured and
  supported MCP sets after the release gate had passed.

## 1. Evidence / symptom

A pre-manifest Claude global installation with an unrelated `gemini` server in `~/.claude.json`
fails `update plan --global` with "global MCP ownership is not supported." The configured set is
`{"gemini"}` and its intersection with AgentSmith-supported project MCP names is empty. No bypass
exists at the explicit plan/apply boundary.

The regression fixtures failed before the correction across both affected seams:

- reconstruction returned `capabilities.mcp: ["gemini"]` instead of `[]`;
- direct post-update health validation rejected foreign global MCP as omitted managed evidence;
- malformed foreign Claude JSON and Codex TOML were parsed and rejected during capability
  reconstruction even though AgentSmith cannot own either global MCP file.

## 2. Failure mechanism

The v0.2.2 legacy reconstruction fix correctly began parsing MCP configuration per agent, but then
treated the full configured set as owned at global scope. The post-update evidence check duplicated
the same special case. This inverted the ownership rule: `--with-mcp` is project-scoped, so every
global MCP entry is foreign by construction.

The v0.2.2 regression test encoded fail-closed refusal as the expected result. It proved detection,
but did not trace the ownership invariant through a successful global plan and apply.

## 3. Bounded edit

Classify detected MCP names through one ownership helper: return no managed names at global scope
before reading MCP files, and parse then intersect configured names with supported names at project
scope. Keep the existing plan and health rejection of a non-empty global manifest capability as
defense against invalid authenticated state.

Replace the refusal fixture with a legacy global plan/apply path that proves an unrelated MCP server
is preserved byte-for-byte and omitted from schema-v1 managed capabilities. Retain a direct health
fixture using a supported MCP name to prove that name alone cannot imply global ownership.

## 4. Named surface

- Production ownership boundary: `managed_mcp_names()` in `agentsmith.py`, used by legacy
  reconstruction and post-update evidence validation.
- Deterministic guard: `scripts/test-update.py`, run by the `update` phase in
  `.harness/verify.conf` and the cross-platform CI matrix.
- Operator warning: `docs/23-updating-existing-installations.md` until a fixed release is published.

## 5. Non-regression validation

The regression fixtures fail on released `v0.2.2` at reconstruction and at the health gate. With the
bounded edit they pass, including valid foreign-server preservation, malformed Claude and Codex
file short-circuiting during capability reconstruction, authenticated apply, and schema-v1
persistence. All 39 updater tests pass, and the full 19-phase local verification gate passes,
including secret and leak checks. A fresh independent review found no remaining ownership, test,
documentation, or security issues.
