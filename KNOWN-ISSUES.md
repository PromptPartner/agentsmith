# Known issues

These defects are intentionally separate from the legacy global updater ownership fix. They are
recorded here because no external tracker write has been authorized.

- [ ] Project-scoped install writes Claude's user-global `permissions.defaultMode` through
  `install_native_config()`; the default `--safety cautious` therefore changes the user's global
  mode to `acceptEdits` from a project operation.
- [ ] Project install appends a generated block to an existing unmarked `CLAUDE.md` and also adds
  `AGENTS.md`, leaving two authoritative instruction rulebooks in one repository.
