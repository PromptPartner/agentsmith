# Feedback 0010: empty Codex MCP override did not isolate native runs

> A harness post-incident. Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-26
- **Status:** applied
- **Cost:** A read-only subscription preflight initialized configured MCP servers before any model call, invalidating the evaluator's no-connectors claim.

## 1. Evidence / symptom

Running Codex with the evaluator's exact `-c mcp_servers={}` override still showed eleven enabled
MCP servers. Interactive startup attempted several connections even though no prompt was submitted.

## 2. Failure mechanism

Codex merges the empty command-line TOML table with user and plugin configuration instead of
replacing those layers. The launcher treated a syntactically empty override as proof of an empty
effective tool surface and continued to inherit the user's global instructions and plugins.

## 3. Bounded edit

Run Codex with an ephemeral `CODEX_HOME` containing a same-filesystem hard link to validated
ChatGPT authentication and minimal no-telemetry configuration. This keeps token refresh state
single-source without inheriting the rest of the client home. Disable hooks, plugins, apps, and skill
MCP installation as defense in depth, and reject non-ChatGPT authentication before launch.

## 4. Named surface

`native_launcher.py` and the shared evaluation/autonomous runtime call sites, covered by the
`evaluation-runner` verification phase.

## 5. Non-regression validation

`scripts/test-evaluate.py` proves configuration and global instructions do not cross the boundary,
subscription authentication and refresh writes do, API-key authentication fails closed, and the
temporary home is removed. A real read-only Codex probe remained logged in through ChatGPT while
reporting no MCP servers under the isolated environment.
