# MCP / integration validation checkpoint

Use this only when adding, restoring, or validating an external integration. Complete the record
before first launch. Inventory is secret-bearing: parse structured configuration, retain credential
references rather than values, and suppress complete argument vectors and environment blocks.

## 1. Need and durable configuration

- Required capability and why the existing native CLI is insufficient:
- Upstream version discovery source/date:
- Exact executable package pin in durable configuration:
- Integration owner:
- Named consumers and credential class for each:
- Authentication mode and data scope:
- Read authority, possible writes, and credential privilege:

Stop when an adequate native CLI already supplies the capability. A package discovered as current
is not durably pinned until the exact version is in configuration.

## 2. Declared validation

- Tool schema inspected:
- Harmless call named before invocation:
- Minimum retained response fields:
- Bounded local/remote side effects:
- Operation can automatically re-prime or otherwise write:

Use the least revealing call that proves authorization; avoid identity endpoints when a narrower
call works. A service-plan 403 does not justify broader credential scopes. Record these states
separately: configured, authenticated, client auto-start observed, capability listing completed,
declared call observed, read-tested, and least privilege (or excess privilege) accepted.

## 3. Durable-state boundary

- Persistent profiles and caches:
- Mutable backing stores and existing background writers:
- Protected artifact hashes before/after:
- Shared-store observation window, acceptable drift, observed drift, and causality:
- Expected server/browser child identities and exact launched PIDs:

Prefer an isolated Playwright profile and browser cache. A shared browser cache needs
`PLAYWRIGHT_SKIP_BROWSER_GC=1` or a trustworthy pre-snapshot. Classify automatic re-priming as
write-capable. Stop on ambiguous shared-store causality; retain legitimate background workers and
do not attribute their writes to this validation.

`--no-sandbox` requires a runtime-specific reason plus an isolated profile and browser cache.
Close the client/server, then prove every exact PID launched here exited; ignore unrelated names.

## 4. Structured record and static gate

Store a JSON record shaped like this, substituting credential references for live values:

```json
{
  "schema_version": 1,
  "integrations": [{
    "id": "example",
    "name": "service-name",
    "kind": "mcp",
    "capabilities": ["declared-capability"],
    "authentication_mode": "oauth|token|none",
    "data_scope": ["bounded dataset"],
    "owner": "team-or-person",
    "consumers": [{"name": "named-consumer", "credential_class": "credential-class"}],
    "authority": {"read": "authorized", "write": "none|authorized|possible", "credential_privilege": "minimal|admin|other"},
    "package": {"discovered_version": "1.2.3"},
    "configuration": {
      "command": "npx",
      "args": ["-y", "@vendor/server@1.2.3"],
      "env": {},
      "diagnostics": {"emit_full_argv": false, "emit_full_environment": false}
    },
    "native_cli": {"available": false, "adequate": false},
    "mcp_install_planned": true,
    "validation": {
      "configured": true,
      "authenticated": true,
      "read_tested": true,
      "least_privilege_accepted": true,
      "client_auto_start_observed": false,
      "capability_listing_completed": true,
      "declared_harmless_call": "tool_name",
      "bounded_side_effects": [],
      "harmless_tool_invocation_observed": true,
      "tool_schema_inspected": true,
      "minimum_response_fields": ["id"],
      "received_response_fields": ["id"],
      "retained_response_fields": ["id"],
      "response_status": 200,
      "scope_widening_recommended": false
    },
    "resources": {
      "profile": {"mode": "isolated|not-applicable"},
      "browser_cache": {"mode": "isolated|shared|not-applicable", "preservation": "skip-browser-gc|trusted-snapshot"},
      "protected_artifacts": [{"path": "path", "before_sha256": "sha256", "after_sha256": "sha256"}],
      "shared_store": {
        "observation_window": "start/end",
        "background_writers": [],
        "acceptable_drift": [],
        "observed_drift": [],
        "causality": "none|validation|independent|ambiguous"
      }
    },
    "operation": {"name": "read", "can_reprime": false, "write_capable": false},
    "sandbox_exception": {"enabled": false, "runtime_reason": "", "compensating_isolation": false},
    "lifecycle": {"expected_children": ["server"], "launched_pids": [], "alive_pids_after_cleanup": [], "unrelated_pids": []}
  }]
}
```

Run:

```text
agentsmith validate-integration --checkpoint <record.json>
```

This command only reads JSON and checks explicit fields. It never installs or launches packages,
and it never infers authority, harmlessness, real invocation, response minimization, least
privilege, causal attribution, or cleanup. Those observations must be supplied as evidence.
