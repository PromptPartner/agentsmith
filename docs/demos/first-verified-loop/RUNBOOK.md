# Reproduction runbook

## Automated clean-room replay

From the AgentSmith repository root, choose a new output directory:

```bash
python3 scripts/generate-first-loop-proof.py --output /tmp/agentsmith-first-loop-proof
```

The generator copies the current source into a temporary directory, initializes and commits that
copy locally, asserts it is clean, and runs every recorded command from that copy. It creates no
remote, performs no network call, and deletes the raw workspace when finished.

Compare the regenerated directory with `docs/demos/first-verified-loop/`. The FVL-07 contract does
this byte-for-byte after normalizing the fields listed in `sanitization.json`.

## Manual command journey

The automated replay executes this sequence against a new `$DEMO` directory:

```text
agentsmith demo first-loop --target $DEMO
git init && git checkout -b proof/first-loop && git add -A && git commit
agentsmith status --target $DEMO --json
agentsmith verify --target $DEMO                         # named red test
# change only readiness.py: any(checks.values()) → all(checks.values())
agentsmith verify --target $DEMO --record .harness/evidence/public-proof \
  --tree-class disposable-fixture
python3 readiness.py checks.json                         # NOT READY, exit 1
agentsmith handoff first-verified-loop --target $DEMO
agentsmith resume HANDOFF --target $DEMO --json
```

The lifecycle replay separately installs into a clean fixture and a fixture carrying foreign
project and Codex configuration, repeats each install byte-idempotently, reads status, uninstalls,
and verifies that owned markers are gone while foreign bytes remain.
