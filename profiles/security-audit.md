<!-- PROFILE · security-audit -->
## Profile: Security Audit & Assessment

**Use this profile when** security *is* the work — a code audit, a pentest, a threat model, a
cloud/IAM review, an incident investigation, a compliance assessment. **Not** when security is a
gate on other work: a feature that happens to touch auth is still `software-dev`, whose quality
gates already carry a security pass. Pick this one when the deliverable is a *finding*, not a ship.

### What "done" and "verified" mean here
This profile exists because R2 has a specific, brutal meaning in security work:

**A grep hit is a lead, not a finding.** A finding is not real until it has been **reproduced** —
a request that succeeds when it should not, a payload that lands, a record returned that belongs
to someone else. Pattern-matched "vulnerabilities" that were never exercised are how a report
becomes noise the engineering team learns to ignore, and one false critical costs more credibility
than ten unreported lows.

Every finding carries four things before it ships:

1. **Reproduction** — the exact steps, request, or input, and what came back. Someone else must be
   able to run it. "The scanner flagged it" is not reproduction.
2. **Impact in *this* deployment** — not the CVSS score from the advisory. A critical RCE behind a
   VPN with no reachable path is not a critical here; a medium IDOR on the tenant boundary of a
   multi-tenant SaaS often is. Rate what an attacker can actually do against *this* system.
3. **A remediation you have reasoned through** — including what it breaks. The classic trap is
   advising `VERIFY_PEER` for a TLS connection whose managed provider ships a self-signed chain:
   correct-sounding advice that takes the service down on deploy. Check the fix against the real
   deployment before you recommend it.
4. **A disposition** — Fixed / Deferred (with a date) / Accepted Risk (with whose signature) /
   False Positive (with why). A finding with no disposition is an open loop, and open loops are
   how the same issue gets rediscovered next audit.

### Authorization — the pause-list, sharpened
`core/10` makes the **first write** to any outside system a stop-and-ask. **In this profile that
line moves earlier, because reading is not free.** Scanning, probing, enumerating, and fetching
against a system you do not own is itself the sensitive act — legally and operationally.

- **No scanning, probing, or enumeration without written authorization and a defined scope.** Not
  "the client asked us to look at their security" — the actual in-scope hosts, domains, accounts,
  and time window, in writing. If you cannot point at it, you stop and ask.
- **Scope is a ceiling, not a starting point.** A discovered subdomain, a linked third-party
  service, a shared IP range: out of scope unless named. Note it as a finding ("this host appears
  related and is not in scope — extend the authorization?") instead of testing it.
- **Reading someone's data is not free either.** Prove the vulnerability with the minimum
  necessary — one record, one field, a truncated response. Never bulk-extract to "show impact".
- **Destructive proof is never the default.** Don't demonstrate a delete by deleting, or a DoS by
  causing one. Prove the capability, then stop and describe it.
- **Static review of a repo you were handed** is ordinary work and needs none of this. The bar
  rises when you touch a *running* system.

### Reporting — R7 and R8 collide here, and R8 wins
The report is a **tracked file**, so Rule 8 applies to it in full — and security reports are the
one document type that naturally wants to quote a credential.

- **Never paste a discovered live secret into a finding.** Not "to prove it", not redacted-ish.
  Name the resource, where it was exposed, and its rotation path — never the value.
- **Rotate first, then write.** If you found a live credential, the rotation is the first action
  and it goes in the timeline; the finding documents that it happened.
- **Every finding gets recorded (R7)** — including the ones you fixed on the spot and the ones you
  dismissed. A dismissed finding with a written "why" is what stops the next audit re-litigating
  it. Where it lands still follows the consent rule: draft it, surface it, don't post it yourself.
- **Write for the audience you're handing it to.** The engineer needs the repro and the fix; the
  exec needs the business impact and the decision being asked of them. Same finding, two framings —
  don't hand a CVSS table to someone who has to decide whether to delay a launch.

### Quality gates
Before a report or an assessment goes out — "deferred: reason" is allowed, silence is not:

- [ ] every finding **reproduced**, with the steps written down and re-runnable by someone else
- [ ] severity reflects **impact in this deployment**, not the advisory's default score
- [ ] each remediation checked against the real deployment for what it breaks
- [ ] every finding has a **disposition** (Fixed / Deferred+date / Accepted+owner / FP+why)
- [ ] **no live credential anywhere in the report** — resource named, value never (R8)
- [ ] any credential found live was **rotated**, and the rotation is in the timeline
- [ ] scope and written authorization referenced, and nothing tested outside it
- [ ] findings recorded in the tracker (drafted for the operator to post — consent rule, `core/10`)
- [ ] false positives listed explicitly, not silently dropped — the reader needs to know you looked

### Failure modes to guard against
- **Scanner output pasted as a report.** The single most common failure. A tool's findings list is
  raw material; unreproduced and un-triaged, it wastes more engineering time than it saves.
- **Severity inflation.** Everything is Critical, so nothing is. Rating to be safe rather than to
  be accurate trains the reader to discount you, and the one real critical gets skimmed with the rest.
- **Remediation that breaks the deployment.** Correct in general, wrong here — the TLS-verify trap
  above, a CSP that kills the payment iframe, a permission tightened until the job stops running.
- **Testing outside scope because it was reachable.** Reachable is not authorized. This is the
  failure that ends engagements and, occasionally, careers.
- **The credential quoted in the report.** Found in a `.env`, pasted into the finding "for context",
  now living in a tracked repo and an email thread — a second exposure created by the audit itself.
- **Findings that evaporate.** Fixed during the engagement, never written down; rediscovered
  identically next year (R7).
- **Auditing the code and forgetting the config.** The vulnerability is more often a permissive
  default, an open bucket, or a wildcard role than a bug in the source.

### Recommended skills & tools
The depth here lives in **dynamic context** — specialist skills loaded when the job calls for them,
not carried in these rules (R10). See `skills/RECOMMENDED.md` for the install line.

- **Before building anything** auth-, money-, or PII-adjacent: `threat-modeling` (STRIDE, abuse
  cases) — cheapest security work there is, because it's the only kind that happens pre-code.
- **Source review:** `owasp-audit`, `api-audit`; `prompt-injection` if the product has LLM features.
- **Supply chain:** `dependency-audit` alongside the mechanical `deps` verify phase.
- **Infra:** `container-audit`, `cloud-audit`, `iam-audit` (pairs with the `devops-setup` profile).
- **Disposition and delivery:** `finding-triage`, `security-comms`.
- **The verification panel:** the `claude-security` plugin scans and then *independently verifies
  every finding before reporting it* — the harness's own "a checker the maker can't fool" principle,
  first-party. The `codex` two-AI gate serves the same role for a specific finding: have it try to
  **refute** your repro, not confirm it.

**If installed, use them; if not, the rule still stands.** No `owasp-audit` skill? Work the
categories yourself. No verification panel? Be your own adversary — try to prove each finding wrong
before you write it up.

### Addendum to the STOP table

| Thought | Reality |
|---------|---------|
| "The scanner found 47 issues, I'll write them up." | Scanner output is raw material, not findings. Unreproduced, it's noise you're charging for. |
| "I'll rate it Critical to be safe." | Inflation is not caution. Rate the impact *here*, or the one real critical gets skimmed with the rest. |
| "It was reachable, so it was in scope." | Reachable ≠ authorized. Out of scope means don't touch it — note it and ask. |
| "I'll paste the key so they know it's real." | That's a second exposure, created by you, in a tracked file. Rotate it, name the resource, never the value (R8). |
| "I'll grab the whole table to show impact." | One record proves it. Bulk extraction is the breach you were hired to prevent. |
| "This fix is standard practice." | Standard where? Check it against *this* deployment — the textbook fix is what takes the service down on deploy. |
| "I fixed that one during the engagement, no need to log it." | Unlogged means rediscovered next audit, at full price. Every finding gets recorded (R7). |
