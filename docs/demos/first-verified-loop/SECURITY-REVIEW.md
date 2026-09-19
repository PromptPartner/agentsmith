# FVL-08 security review

No security blocker was found in the First Verified Loop boundary. The review names each required
threat explicitly and ties it to executable evidence rather than treating a green aggregate as a
security claim.

| Threat | Reviewed boundary and evidence |
|---|---|
| `command-injection` | Discovery never executes repository hints; only reviewed detector commands can enter a plan, and resume accepts one literal status-command grammar. |
| `path-traversal` | Absolute, parent-traversal, cross-target, home, broad-root, and outside-project targets fail before writes. |
| `symlink-escape` | Verification config, backup, demo target, and handoff fixtures reject redirected components; POSIX resume pins directory descriptors with no-follow semantics. |
| `plan-tampering` | Apply recomputes discovery and binds the schema-valid plan to its target, inputs, labels, and commands before changing configuration. |
| `secret-redaction` | Discovery, plan diffs, errors, resume output, verification sidecars, and public artifacts are covered by redaction and leak-gate fixtures. |
| `foreign-file-preservation` | CRLF, comments, custom phases, project instructions, client settings, and occupied targets are preserved at the documented ownership boundary. |
| `git-state-safety` | Demo creation performs no Git action; resume observes with optional locks disabled and leaves branch, HEAD, refs, stash, index, and dirty state unchanged. |

The independent review reran the focused FVL-02, FVL-04, FVL-05, and FVL-07 suites and found no
blocker. Residuals remain explicit: proof generation is not enclosed by an operating-system network
sandbox, and Windows uses fail-closed prechecks plus final-handle validation rather than POSIX
directory-descriptor pinning. Native report authenticity relies on same-run hosted-job artifact
trust. Output roots are explicit and symlink-checked, but an attacker who can mutate the runner's
private temporary directory during the narrow check/write interval is already inside that trust
boundary.
