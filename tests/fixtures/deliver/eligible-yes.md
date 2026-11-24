## Autonomous run deliver

Implementation ticket: IMP-7. Accepted commit `<commit>` on base `<commit>`.

### Changed paths
```text
- src/change.txt
```

### Risk
Tier **A** (recorded A, recomputed now A, declared none). Lenses: code. Policy blob at the base: `<commit>`.

### Reviewer focus
Every path is tier A under the policy at the base; no path needs more than the usual review. Lenses: code.

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
Checker calibration: passed (<time>).

### Models used
```text
- maker: codex, model fixture-model, effort high (attempt 1)
- checker: claude, model fixture-model, effort high (attempt 1)
```

### Budgets used
Attempts: 1 of 3. Claude: 0.25 USD of 20. Codex: 10 tokens of 2500000.

### Base
0 commits behind origin/main; the accepted diff applies cleanly.

Auto-merge eligible: yes for <commit> — tier A: met; no floor path: met; checker accepted with valid citations: met; passing calibration for this checker: met; head equals the accepted commit: met; CI green for this commit: met

Auto-merge eligibility is information only: a human merges this pull request, and nothing in this release merges automatically.
