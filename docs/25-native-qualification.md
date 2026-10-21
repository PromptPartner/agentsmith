# Offline native-client qualification

The [accepted contract](26-native-qualification-contract.md) defines C01–C10 containment and
R01–R10 recovery. NQ-01 and NQ-02 implement offline recording and completeness gates. They make
no native qualification claim. Actual file-tool calls, hook/connector evaluation, model cycles
and native fault series require separately authorized NQ-03 models and inference budgets.

## Run the offline series

The containment runner uses disposable linked repositories with spaces under both temporary
storage and a non-temporary evidence directory. On macOS it runs provider-free Codex sandbox
subprocesses. Claude settings construction remains fixture evidence. Synthetic hooks and
connectors have controls; an unobserved native policy evaluation remains unrun or undetermined.
Choose a new output directory outside temporary storage:

```sh
python3 scripts/qualification-containment.py --output .harness/handoffs/containment-series-1
python3 scripts/qualification-recovery.py --output .harness/handoffs/recovery-series-1
python3 scripts/qualification-recovery.py --check --output .harness/handoffs/recovery-series-1
```

The recovery runner invokes the public controller CLI with deterministic substitute roles and
named barriers. Each normal cycle starts with a failing fixture check, makes a local commit,
runs the approved fixture verifier and binds a fresh checker receipt to that commit. Fault
variants retain launch records, persisted stages, original deadlines, ordinary process groups,
raw logs and usage replay. R04 records surviving groups and explicit cleanup separately from
automatic extinction. Wrapper barriers at `validating` and accounting are fixture instrumentation.
They do not establish native-client crash behavior. POSIX process fixtures require a supported
controller/verifier sandbox host; unsupported execution cannot fill a supported cell.

## Inspect and check evidence

Containment exports `manifest.json`, `ledger.json` and `completeness.json`. The independent
manifest expands each operation, target class, alias, payload, built-in tool, role and path
layout from a frozen inventory. Native tools whose exact enabled inventory is unobserved stay
incomplete. Shell evidence cannot substitute for built-in file-tool evidence.

```sh
python3 scripts/qualification-evidence.py check \
  --manifest .harness/handoffs/containment-series-1/manifest.json \
  --ledger .harness/handoffs/containment-series-1/ledger.json \
  --output .harness/handoffs/containment-series-1/recheck.json
```

An incomplete check returns nonzero and preserves its report. `--fixture` checks fixture
containment completeness only. Recording an incomplete ledger is valid; accepting it as complete
is not. Native containment completeness alone cannot certify recovery or native pair cycles, so
`qualified` remains false. Recovery `--check` requires all independently enumerated fixture
variants to pass; `--require-native` refuses fixture promotion.

The generic recorder exposes `manifest`, `init` and `record` for an independently supplied
inventory and structured observation. Each command creates a new file exclusively. Observed
attempts cannot replace prior observations in the same series. Source, policy, version, raw
artifact and applicability hashes are checked again when consuming evidence. A smaller ledger,
stale candidate, failed verifier, duplicate usage or orphaned descendant cannot earn completeness.

Raw evidence stays in local `.harness/handoffs/`, backed up outside disposable repositories.
Keep each series after a failure. Curated reports may publish credential-free counts, hashes and
limitations; raw host paths and authentication material are not publication inputs.
