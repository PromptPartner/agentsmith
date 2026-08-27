# Feedback 0013: normalized evidence retained operator home path

> A harness post-incident. Never delete this record; archive it under `_archive/` if it becomes obsolete.

- **Date:** 2026-08-27
- **Status:** applied
- **Cost:** The first committed-state release gate failed immediately before the authorized push.

## 1. Evidence / symptom

After reviewed evaluation records became tracked, `scripts/leak-gate.sh` found the operator's
absolute home path in a Claude summary describing a denied read of the user's `.gitconfig`.
Untracked evidence had not been part of earlier tracked-surface leak checks.

## 2. Failure mechanism

`evaluate.redact()` normalized known credential shapes but did not normalize host-specific absolute
home paths emitted in model summaries. Promotion preserved the normalized record faithfully, so the
machine identifier crossed into the shipped surface.

## 3. Bounded edit

Replace the active home-directory prefix with `~/` during normalized summary/failure redaction. Apply
the same deterministic transformation to the already reviewed record; leave raw evidence unchanged.

## 4. Named surface

`evaluate.py` normalized-output boundary, covered by the `evaluation-runner` and `leak-gate`
verification phases.

## 5. Non-regression validation

`scripts/test-evaluate.py` proves the current home path becomes `~/.gitconfig`; it failed before the
fix and passes after it. The real tracked-surface leak gate also changed from blocked to clean.
