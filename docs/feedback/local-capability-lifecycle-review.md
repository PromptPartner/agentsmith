# LOCAL-CAPABILITIES: module tests missed a CLI disclosure seam

## Evidence

Effect helper tests passed while a real install dry-run omitted disclosures. The call had landed in uninstall because both paths used the same instruction-path expression. The real preview check exposed the missing user-visible output before release.

## Failure mechanism

Testing the helper alone did not establish that the installer called it before writes. Broad textual insertion crossed function boundaries.

## Bounded edit

Move disclosure into installation before reconciliation. Add a real CLI dry-run regression checking disclosure order and an unchanged target. No new universal instruction is needed; R3 already requires the complete path.

## Named surface

`scripts/test-capability-effects.py` exercises the installer; its phase is in `.harness/verify.conf`. Shared hook-group fixtures additionally guard foreign handlers during registration and removal.

## Non-regression

The CLI fixture failed for missing output before the call moved and now passes. Partial records and expanded candidate effect declarations have separate failing-first guards. Full verification is required before each unit is finalized.
