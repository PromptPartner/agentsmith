## Autonomous run deliver

Implementation ticket: IMP-7. Accepted commit `<commit>` on base `<commit>`.

### Changed paths
```text
- src/change.txt
```

### Risk
Tier **B** (recorded B, recomputed now B, declared none). Lenses: code. Policy blob at the base: `<commit>`.

### Reviewer focus
Read these paths first, highest tier first. Lenses: code.
```text
- B src/change.txt (rule:1; lenses: code)
```

### Verification
Verifier exit 0; output `<sha256>`; 1 evidence file(s) recorded by hash.

### Checker
Status accepted; every citation was checked at acceptance, and the ones that quote the verifier log were checked again now.
```text
- fixture verification passed :: attempt-1-verify.txt :: fixture verification passed
```

### Assumptions made without authority
The maker's report lists none.

### Calibration
Checker calibration: none. This makes it checker advisory: its acceptance is advice, not a gate, so a human reviews the change before it lands.

### Models used
```text
- maker: codex, model fixture-model, effort high (attempt 1)
- checker: claude, model fixture-model, effort high (attempt 1)
```

### Budgets used
Attempts: 1 of 3. Claude: 0.25 USD of 20. Codex: 10 tokens of 2500000.

### Base
0 commits behind origin/main; the accepted diff applies cleanly.

### Demo
None: the accepted spec declares no `## Demo` command, so this landing carries no replayable demonstration of the changed behaviour.

Auto-merge eligible: no for <commit> — tier A: unmet (B); no floor path: met; checker accepted with valid citations: met; passing calibration for this checker: unmet (none); head equals the accepted commit: met; CI green for this commit: pending CI

Auto-merge eligibility is information only: a human merges this pull request, and nothing in this release merges automatically.
