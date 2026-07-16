---
name: harness-doctor
description: Check whether this project's Agentsmith harness is installed correctly and healthy — fires on "is my harness set up right?", "harness doctor", "check my harness". Part of the Agentsmith harness; runs self-contained health checks (CLAUDE.md managed block, settings, verify.conf, scripts, leanness) with a one-line fix for each finding.
---

# Harness doctor — is the harness healthy?

Confirm the harness is wired correctly, in plain language, with a concrete fix per finding.

## When this fires
"is my harness set up right / healthy?" / "harness doctor" / after an install or a `--self-update`.

## Fast path — if a harness checkout is reachable
If you can find a harness checkout that has `setup.sh` (the cwd, or a path the operator names),
offer to run `bash setup.sh --doctor` for the full machine-level report (global CLAUDE.md,
settings keys, plugins, skills dir). `setup.sh` is NOT copied into projects — don't assume it's here.

## Fallback — self-contained project checks
Check each; report pass, or a one-line fix:
- **CLAUDE.md** present and contains an `AGENTSMITH:BEGIN … END` managed block (not just a stray
  file). Fix: re-install, or `./setup.sh --self-update` from a checkout.
- **`.claude/settings.json`** (and/or `settings.local.json`) present. Fix: `cp` the shipped
  `.claude/settings.local.json.example`.
- **`.harness/verify.conf`** exists AND has a real phase — not just the `sanity ::` placeholder.
  Fix: edit it to list this project's real checks.
- **`scripts/*.sh`** present and executable. Fix: `chmod +x scripts/*.sh`.
- **Leanness:** if `./scripts/lint-leanness.sh` exists, run it on `CLAUDE.md` and report the
  line/token budget. Over budget → move prose into a skill or doc, not more `core/`.

## Report
A short pass/fix list, most-important first. End with the single highest-value fix to do next.
