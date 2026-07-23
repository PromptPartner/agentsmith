# Securing what you build

There are two security questions in agent work, and they need separating — because every control
for one does nothing for the other:

1. **Can the agent hurt *me*?** Blast radius: what it can delete, exfiltrate, push, or post. That's
   [`15-safety-model.md`](15-safety-model.md), and the harness enforces it directly.
2. **Is the thing it *builds* safe?** Authorization, injection, dependency CVEs, least-privilege
   infra. **That's this page.**

The gap between them is easy to miss, so state it plainly: **a perfectly sandboxed agent will
happily write an IDOR.** Cautious mode, the pause-list, the secret-scan hook, the loop denylist —
none of them look at the code. They bound what the agent can do *to you*, not what it ships *for
you*.

## Why this exists (the gap, honestly stated)

For most of this harness's life, question 2 had no answer. The `software-dev` quality gates were
build, typecheck, lint, test, docs — five checkboxes, **zero** about security. `devops-setup`
covered secrets-in-git and nothing else. The word "security" appeared in the profiles not once.

That's the same shape as the [design-system gap](11-designing-uis.md): not a model failure, a
**configuration failure**. Asked to add an endpoint, an agent optimizing for the stated gates
produces something that builds, types, lints, tests, and is documented — and never once asks who's
allowed to call it. It did exactly what it was told. The rule wasn't there.

So the fix is the same as always: [add the rule, don't blame the model](04-why-your-agent-ignored-the-rule.md).

## The everyday path: security as a gate, not a ceremony

Most security work shouldn't be a separate project. It should be two questions that get asked while
you're shipping the feature, which is why they live in the profile quality gates rather than in a
document nobody books time for.

**`software-dev`** adds:

- a **named security pass** on code touching auth, user input, or secrets — authorization enforced
  server-side *at the handler* (not the caller), input parameterized or escaped *at the sink*, no
  credential in the diff. *Named* is the operative word: "looks fine" is not a pass, same as
  everywhere else in this harness ([verify means evidence](03-verify-means-evidence.md)).
- a **CVE check** on new or changed dependencies.

**`devops-setup`** adds:

- the **exposed surface is only what you intended** — ports, routes, buckets, checked from off the
  host.
- **workload identity is least-privilege** — non-root container, scoped role, no wildcard IAM.
  Admin-by-default is a finding, not a default.

Two STOP-table rows back each up, because both have a well-worn rationalization:

| The thought | The reality |
|---|---|
| "It's internal-only, nobody can reach it." | Internal today, exposed after the next routing change. Enforce authz at the handler, not the caller. |
| "The scanner was clean, so it's secure." | Clean means no *known pattern* matched. Auth and ownership bugs are logic — no grep finds them. |
| "The default config is fine for now." | Defaults are permissive by design — open ports, root user, wildcard IAM. "For now" is what ships. |

## The mechanical half: two things that shouldn't be judgment calls

The security pass above is a judgment call and stays one. But two of its parts aren't judgment at
all — a dependency with a known high/critical CVE and a credential in a tracked file are both
*mechanically detectable*. Per [core/60](../core/60-evolving-the-harness.md), anything mechanical
should be a guard, not a reminder:

```
# .harness/verify.conf — offered in the software-dev and devops-setup presets
deps    :: npm audit --audit-level=high    # or: pip-audit | govulncheck ./... | cargo audit
secrets :: ./scripts/secret-scan.sh --all  # R8, whole tracked tree
image   :: trivy image --severity HIGH,CRITICAL --exit-code 1 <your-image>
```

They ship **commented out**, like every other preset line — uncomment what your stack actually has.
`scripts/verify.sh` runs whatever the conf lists, so CI picks them up for free with no new
machinery. An uncommented phase whose tool isn't installed fails loudly, which is the correct
behavior: a green check that silently skipped is worse than no check.

## When security *is* the job: the `security-audit` profile

The gates above are for shipping. When the deliverable is a **finding** rather than a ship — an
audit, a pentest, a threat model, an incident write-up, a compliance assessment — use the
[`security-audit` profile](07-how-to-pick-a-profile.md). Its spine is [R2](03-verify-means-evidence.md)
sharpened to this domain:

> **A grep hit is a lead, not a finding.** A finding is real only once it has been *reproduced* — a
> request that succeeds when it shouldn't, a payload that lands, a record returned that belongs to
> someone else.

Unreproduced findings are how a report becomes noise the engineering team learns to skim, and one
false critical costs more credibility than ten unreported lows. Every finding carries reproduction,
impact **in this deployment** (not the advisory's CVSS), a remediation you've checked for what it
breaks, and a disposition.

Two of its rules are deliberately **stricter than core**, and they're the reason the profile exists
rather than being a checklist:

- **Authorization moves earlier than the [core/10 pause-list](../core/10-operating-model.md).** Core
  makes the first *write* to an outside system a stop-and-ask. Here, **reading is not free** —
  scanning, probing, and enumerating a system you don't own is itself the sensitive act, legally and
  operationally. No probing without written authorization and a defined scope; scope is a ceiling,
  not a starting point; prove with the minimum (one record, never a bulk extract); never demonstrate
  destructively. Static review of a repo you were handed needs none of this — the bar rises on
  *running* systems.
- **R8 beats R7 in the report.** Security findings are the one document type that naturally wants to
  quote the credential they found. Don't: the report is a tracked file, so pasting a live secret
  into it creates a **second exposure, authored by the audit itself**. Rotate first, name the
  resource and its rotation path, never the value.

**Don't stack it with `software-dev`.** These are the two largest profiles and together they
overrun the [rule budget](01-harness-philosophy.md) (~635 lines against 600) — which is the signal
that you're asking the agent to carry two full rule sets it won't use at once. Re-assemble for the
audit and switch back after; it's one command, and it matches the mode you're actually in.
(`devops-setup,security-audit` stacks fine, if you're hardening infra you also run.)

## Depth on demand: the `security` pack

The rules above are deliberately thin, because [static context is paid every
turn](01-harness-philosophy.md). Actual security expertise belongs in **dynamic context** — skills
loaded only when a task calls for them. That's the opt-in pack:

```bash
./setup.sh --with-plugins security
```

It installs two things, for different reasons:

- **`claude-security`** (Anthropic, first-party). A panel of agents maps the architecture,
  threat-models it, hunts, and then **independently verifies every finding before it reaches the
  report**, with the tally computed in code rather than asserted. That last part is why it's here
  and not merely "a scanner": it's this harness's own [checker-the-maker-can't-fool](03-verify-means-evidence.md)
  principle, shipped by the vendor. Use it as your *adversary* — have it try to refute a finding,
  not confirm it. The [`codex` two-AI gate](12-whats-built-in.md) does the same job for a diff.
- **`cybersecurity-skills`** ([briiirussell](https://github.com/briiirussell/cybersecurity-skills),
  MIT). 29 specialist workflows: `owasp-audit`, `threat-modeling`, `api-audit`, `dependency-audit`,
  `prompt-injection`, `container-audit`, `cloud-audit`, `iam-audit`, `incident-triage`,
  `finding-triage`, `security-comms`, plus compliance (HIPAA/PCI/GDPR) and blue-team (SIEM,
  threat-hunting, forensics) sets.

**Registered and installed, never vendored.** Upstream maintains it, updates arrive free, and the
harness owns none of it — 29 skills at ~250 lines each is exactly the surface
[R10](../core/20-principle-rules.md) exists to keep us out of owning. It ships as *one* plugin
carrying all 29 skills; there's no per-skill install, which costs nothing here since skills load on
demand by their `description`.

Which one to reach for, and when, is mapped in
[`skills/RECOMMENDED.md`](../skills/RECOMMENDED.md) — by profile and by engagement type.

## The cheapest security work happens before the code

`threat-modeling` is the one to reach for *first*, on anything auth-, money-, or PII-adjacent. It's
the only kind of security work that happens pre-implementation, which makes it the only kind whose
fix costs nothing — you're changing a design, not a shipped system. Pair it with
[`superpowers:brainstorming`](12-whats-built-in.md) at the same point in the loop.

## What this does *not* do

Worth being explicit, so nobody reads more assurance into it than is there:

- **It does not make the agent a security engineer.** The gates make it *ask* the question and give
  it somewhere to look. Judgment on a real finding is still yours.
- **It does not machine-verify that code is secure.** No such check exists. `deps` and `secrets`
  catch two mechanical classes; everything else is held by the rule, the gate, the STOP row, and a
  reviewer — human or adversarial agent.
- **It does not replace a real audit** for anything regulated, custodial, or safety-critical. It
  raises the floor and makes an audit cheaper by the time you book one.
- **It does not bound what the agent can do to your machine.** That's still
  [`15-safety-model.md`](15-safety-model.md) — different question, different controls.
