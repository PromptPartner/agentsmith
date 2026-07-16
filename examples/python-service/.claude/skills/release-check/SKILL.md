---
name: release-check
description: Use when cutting an Orchard release (tagging a new version of the FastAPI inventory service) — walks the pre-tag checklist so migrations, verify, changelog, and the tag stay in sync.
---

# Release Check — Orchard

Cutting a release for Orchard is mechanical but easy to half-do (tag without the migration check,
bump the version but forget the changelog). This skill is the checklist so nothing slips. It
loads only when you're releasing — everyday work doesn't pay for it.

## When this fires

You type `/release-check`, or you're about to tag a new Orchard version.

## Checklist

Walk these in order. Stop at the first failure, fix it, restart — a release is atomic.

1. **Clean tree, right branch.** `git status` is clean and you're on `main` (or the release
   branch). No uncommitted work rides along in a tag.
2. **Bump the version.** Update `version` in `pyproject.toml`. Use semver: breaking API/contract
   change → major; new endpoint/field → minor; fix only → patch.
3. **Migrations present and current.** `alembic check` is clean (no model-vs-history drift), and
   every new revision has been **applied once against a dump of representative data**, not just an
   empty DB. `alembic check` proves agreement, not applicability — this step proves applicability.
4. **Verify is green.** Run `scripts/verify.sh` and read the output: `format`, `lint`, `types`,
   `migrations`, `test` all pass. Within-a-layer green only — also confirm one real request path
   (TestClient against the full app) still works end to end.
5. **Changelog updated.** Add a dated section to `CHANGELOG.md` for this version: what changed,
   and call out any **API-contract or migration** change explicitly so callers know to look.
6. **Commit, then tag.** `chore(release): vX.Y.Z` commit, then `git tag vX.Y.Z`. Tag points at the
   release commit — never an earlier one.
7. **Push commit and tag.** `git push && git push --tags`. Open/reference the GitHub release.

## Notes

- If `alembic check` fails, you have a model change with no migration — that's a code bug, not a
  release step. Go back and add the revision before tagging.
- Don't allowlist a secret to make a hook pass; the no-secrets rule is absolute (core).
