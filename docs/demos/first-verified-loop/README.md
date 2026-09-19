# First Verified Loop — public proof

This bundle is a reproducible, sanitized record of one bounded AgentSmith task. It follows the same
value from an intentional failing test through the corrected logic, all configured checks, the
visible command, a verification receipt, a durable handoff, and read-only resume.

Start with the [runbook](RUNBOOK.md), then inspect the [flow](FLOW.md),
[claim map](CLAIM-MAP.md), [security review](SECURITY-REVIEW.md),
[release-readiness boundary](RELEASE-READINESS.md), and [current limitations](LIMITATIONS.md).

## Evidence chain

1. [Read-only status and coverage](artifacts/status.json)
2. [Named red test](artifacts/red.txt)
3. [Green three-phase verification](artifacts/green.txt)
4. [Real command-path output](artifacts/real-path.txt)
5. [Verification receipt](artifacts/receipt.json)
6. [Handoff](artifacts/handoff.md) and [zero-drift resume](artifacts/resume.json)
7. [Clean installation lifecycle](artifacts/install-clean.json)
8. [Existing-config preservation lifecycle](artifacts/install-existing.json)
9. [Compatibility evidence snapshot](artifacts/compatibility.json)

All commands ran from a temporary clean Git copy of the current source. The checked-in artifacts are
normalized only as documented in [sanitization.json](sanitization.json); raw temporary paths and
timestamps are not public proof. Regenerate the bundle with:

```bash
python3 scripts/generate-first-loop-proof.py --output /tmp/agentsmith-first-loop-proof
```
