# Releasing AgentSmith

This checklist is for maintainers. Pushing a `vX.Y.Z` tag makes the `standalone builds` workflow build and
test the five standalone archives, write and attest `SHA256SUMS`, and create a **draft** release. Nothing is
published until a maintainer reviews that draft.

1. On a branch, set `VERSION = "X.Y.Z"` in `agentsmith.py`.
2. Update the hard-coded release references: the current release and bootstrap commands in
   `docs/23-updating-existing-installations.md`, and the version placeholder in `.github/ISSUE_TEMPLATE/bug.yml`.
3. Run `bash scripts/verify.sh`, open a pull request, and merge it to `master` once its checks pass.
4. Tag the merged commit with an annotated tag and push only that tag:

   ```console
   git switch master && git pull --ff-only
   git tag -a vX.Y.Z -m "AgentSmith X.Y.Z"
   git push origin vX.Y.Z
   ```

5. Wait for the tag's `standalone builds` run. The release job stops without creating anything if the tag is
   not `v` + `VERSION`; then delete the tag locally and on GitHub, fix `VERSION` through a pull request, and
   tag again. It also refuses to replace an existing release, so delete a failed draft before a rerun.
6. Open the draft release. Confirm it holds `SHA256SUMS` and five archives: `agentsmith-linux-x86_64.tar.gz`,
   `agentsmith-linux-arm64.tar.gz`, `agentsmith-macos-arm64.tar.gz`, `agentsmith-macos-x86_64.tar.gz`, and
   `agentsmith-windows-x86_64.zip`. Download one and run `sha256sum -c --ignore-missing SHA256SUMS` and

   ```console
   gh attestation verify <file> --repo PromptPartner/agentsmith --signer-workflow PromptPartner/agentsmith/.github/workflows/standalone.yml --source-ref refs/tags/<version>
   ```
7. Edit the generated notes, then publish the release.

The builds are not code-signed. Do not describe them as signed in release notes or documentation.
