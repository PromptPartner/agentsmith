# Platform installer migration coverage map

**Date:** 2026-08-26
**Release boundary:** AgentSmith 0.2.0

The former `scripts/test-platform-install.sh` and `scripts/test-platform-install.ps1` suites tested
two retired installers by asserting copied shell scripts, statusline wiring, and RTK integration.
Keeping those assertions red would test a product that no longer exists. This map records every
invariant retained before those suites are removed and names its release-blocking replacement.

## Retained invariants

| Contract | Authoritative replacement |
|---|---|
| Canonical project `AGENTS.md`; equivalent generated Claude copy | `test-agent-conformance.py`: “native install generates canonical and equivalent instruction files” |
| Every profile assembles; root/install help exposes profile discovery; static-context budget | cross-platform conformance profile loop plus `test-assemble.sh` |
| Native and configured adapters work in paths containing spaces and Unicode | conformance all-agent, configured-adapter, and native managed-install fixtures |
| Foreign Claude JSON, Codex TOML, MCP servers, hooks, skills, and adapter content survive | conformance foreign-config and native managed-install fixtures |
| Selected MCP servers and skills install for both native clients | conformance native managed-install fixture |
| Cautious/trusted mappings, migration warning, backup, parsing, and idempotence | conformance safety fixtures |
| Dry-run performs no project/global mutation | conformance dry-run fixtures and unchanged `test-operator-identity.sh` |
| Hook config calls the Python runtime; Git pre-commit invokes the canonical scanner; foreign hooks survive | conformance native-hook fixture and `test-secret-scan.py` |
| Software projects receive `.agentsmith` runtime/controller and `.harness/verify.conf`; non-owned scaffolding survives uninstall | conformance native managed-install fixture |
| Re-runs are byte-idempotent | conformance all-agent, adapter, safety, and native managed-install fixtures |
| Uninstall removes only owned rules, MCP, hooks, adapters, and unmodified skills | conformance organization, adapter, and native managed-install fixtures |
| Ask-first tracker consent, explicit opt-in, fail-closed legacy recovery, and idempotence | `test-tracker-consent.py` |
| Global operator identity recovery and explicit-field override | unchanged `test-operator-identity.sh`, plus cross-platform conformance identity fixture |
| Registry/schema and native Windows execution without an extra Bash dependency | `compatibility/test_registry.py` and strict conformance on the three-OS CI matrix |

## Explicitly retired assertions

- RTK default/opt-out execution and `@RTK.md` diagnostics. The compatibility flags remain accepted
  migration inputs, but AgentSmith no longer installs proprietary instruction imports.
- Copied `handoff-on-keyword.sh`, `context-budget-nudge.sh`, and UI-hook scripts. Managed hook
  commands now invoke the installed Python runtime directly.
- Managed Claude statusline installation/refresh and its old doctor strings.
- Claude-only project artifacts and the pre-canonical “Claude by default” file layout.
- Exact warning sentences from the shell/PowerShell installers; behavior and ownership are the
  contract, not retired wording.

## Release authority

Local `agentsmith verify` runs the full gate for the current host. CI runs registry, strict
conformance, scanner, consent, and atomic-state tests natively on Ubuntu, macOS, and Windows;
POSIX-only rendering/hook/controller integration tests run on Ubuntu, with the controller also run
on macOS through the local release gate. A green retired platform script is not evidence and is no
longer part of the repository.
