<!-- PROFILE · security-audit -->
## Profile: Security Audit & Assessment

**Use this profile when** security *is* the deliverable — a code audit, a pentest, a threat model,
a cloud/IAM review, an incident investigation, a compliance assessment. **Not** when security is a
gate on other work: a feature that touches auth is still `software-dev`, whose quality gates
already carry a security pass. Pick this one when the output is a *finding*, not a ship.

### What "done" and "verified" mean here
R2 has a specific, brutal meaning in this work:

**A grep hit is a lead, not a finding.** A finding is real only once it has been **reproduced** — a
request that succeeds when it shouldn't, a payload that lands, a record returned that belongs to
someone else. Unreproduced "vulnerabilities" are how a report becomes noise the engineering team
learns to skim, and one false critical costs more credibility than ten unreported lows.

Every finding carries four things before it ships:

1. **Reproduction** — exact steps, request, or input, and what came back. Someone else must be able
   to re-run it. "The scanner flagged it" is not reproduction.
2. **Impact in *this* deployment** — not the advisory's CVSS. A critical RCE with no reachable path
   isn't critical here; a medium IDOR across a multi-tenant boundary often is.
3. **A remediation you reasoned through, including what it breaks.** The classic trap: advising
   TLS `VERIFY_PEER` against a managed provider that ships a self-signed chain — correct-sounding
   advice that takes the service down on deploy. Check the fix against the real deployment.
4. **A disposition** — Fixed / Deferred+date / Accepted+owner / False Positive+why. A finding
   without one is an open loop, and open loops get rediscovered next audit at full price.

### Authorization — the pause-list, sharpened
`core/10` makes the first *write* to an outside system a stop-and-ask. **Here that line moves
earlier, because reading is not free.** Scanning, probing, and enumerating a system you don't own
is itself the sensitive act — legally and operationally.

- **No scanning, probing, or enumeration without written authorization and a defined scope** — the
  actual in-scope hosts, domains, accounts, and time window. Can't point at it? Stop and ask.
- **Scope is a ceiling, not a starting point.** A discovered subdomain or linked third party is out
  of scope unless named. Report it as "this looks related — extend the authorization?" and don't test it.
- **Prove with the minimum.** One record, one field, a truncated response. Never bulk-extract to
  "show impact" — that's the breach you were hired to prevent.
- **Never demonstrate destructively.** Don't prove a delete by deleting or a DoS by causing one.
  Establish the capability, then stop and describe it.
- **Static review of a repo you were handed** needs none of this. The bar rises on *running* systems.

### Reporting — R7 and R8 collide here, and R8 wins
The report is a **tracked file**, and security findings are the one document type that naturally
wants to quote the credential they found.

- **Never paste a discovered live secret into a finding** — not "to prove it", not partly redacted.
  Name the resource, where it was exposed, and its rotation path. Never the value.
- **Rotate first, then write.** The rotation is the first action and goes in the timeline; the
  finding records that it happened.
- **Every finding gets recorded (R7)** — including ones you fixed on the spot and ones you
  dismissed. A dismissal with a written "why" is what stops the next audit re-litigating it. Where
  it lands still follows the consent rule: draft it, surface it, don't post it yourself.
- **Frame for the reader.** The engineer needs the repro and the fix; the exec needs the business
  impact and the decision being asked of them. Same finding, two framings.

### Quality gates
Before a report or assessment goes out — "deferred: reason" is allowed, silence is not:

- [ ] every finding **reproduced**, steps written down and re-runnable by someone else
- [ ] severity reflects **impact in this deployment**, not the advisory's default score
- [ ] each remediation checked against the real deployment for what it breaks
- [ ] every finding has a **disposition** (Fixed / Deferred+date / Accepted+owner / FP+why)
- [ ] **no live credential anywhere in the report**; anything found live was **rotated** first (R8)
- [ ] written authorization and scope referenced — and nothing tested outside it
- [ ] findings recorded in the tracker (drafted for the operator to post — consent rule, `core/10`)
- [ ] false positives listed explicitly, not silently dropped — the reader needs to know you looked

### Failure modes to guard against
- **Scanner output pasted as a report.** The most common failure by far. A tool's list is raw
  material; unreproduced and un-triaged it burns more engineering time than it saves.
- **Severity inflation.** Everything Critical means nothing is, and the one real critical gets
  skimmed with the rest.
- **Remediation that breaks the deployment.** Right in general, wrong here — the TLS-verify trap
  above, a CSP that kills the payment iframe, a role tightened until the job stops running.
- **Testing outside scope because it was reachable.** Reachable is not authorized. This is the
  failure that ends engagements.
- **The credential quoted in the report** — a second exposure, created by the audit itself (R8).
- **Auditing the code and forgetting the config.** The finding is more often a permissive default,
  an open bucket, or a wildcard role than a bug in the source.

### Recommended skills & tools
The depth here lives in **dynamic context**, not in these rules (R10): the `security` pack
(`./setup.sh --with-plugins security`) carries `threat-modeling`, `owasp-audit`, `api-audit`,
`cloud-audit`, `iam-audit`, `finding-triage`, `security-comms` and ~20 more, plus `claude-security`
for an independent verification pass. **`skills/RECOMMENDED.md` maps skill → engagement type** —
read it there rather than duplicating the catalog here.

Use `claude-security` or the `codex` two-AI gate as your adversary: have it try to **refute** each
finding, not confirm it. **If installed, use them; if not, the rule still stands** — be your own
adversary and try to prove each finding wrong before writing it up.

### Addendum to the STOP table

| Thought | Reality |
|---------|---------|
| "The scanner found 47 issues, I'll write them up." | Scanner output is raw material, not findings. Unreproduced, it's noise you're charging for. |
| "I'll rate it Critical to be safe." | Inflation isn't caution. Rate the impact *here*, or the one real critical gets skimmed with the rest. |
| "It was reachable, so it was in scope." | Reachable ≠ authorized. Out of scope means don't touch it — note it and ask. |
| "I'll paste the key so they know it's real." | That's a second exposure, created by you, in a tracked file. Rotate it; name the resource, never the value (R8). |
| "This fix is standard practice." | Standard where? The textbook fix is what takes the service down on deploy. Check it against *this* deployment. |
| "I fixed that one during the engagement, no need to log it." | Unlogged means rediscovered next audit, at full price (R7). |
