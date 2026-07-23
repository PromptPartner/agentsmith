<!-- PROFILE · devops-setup -->
## Profile: DevOps & Server Setup

**Use this profile when** the work provisions or changes infrastructure — boxes, installers, Docker/compose, configs, firewalls, DNS, TLS, CI pipelines, deploys. Guiding star: prefer the safest reversible path, and prefer a UI or documented step over a clever one-off terminal incantation.

### What "done" and "verified" mean here
R2 and R5 are stricter for infra. A change is verified only when the service **actually comes up healthy and reachable from outside the box** — not when a command exited 0 and not when `docker ps` shows "running". Real reachability over green exit codes.

A real smoke check means:
- `curl` the public endpoint (or health route) and get the expected status/body — from off the host where possible.
- Confirm TLS terminates (valid cert, no expiry/SAN warning) if the service is meant to be HTTPS.
- Watch for restart loops: check the process/container has been up >60s and isn't cycling (`docker ps` uptime, `restart count`, or `systemctl status`).
- Tail logs for the first error after start, not just the boot banner.
- Reboot-survival when relevant: the unit/container restarts on its own (enabled service, `restart: unless-stopped`).

"It exited 0" is a claim, not evidence. The evidence is the response on the wire.

### Safety rules (infra-specific, load-bearing)
- **Backup/dump BEFORE any destructive or migrating op.** Snapshot the volume, `pg_dump`/`mysqldump` the database, copy the config you're about to overwrite. No backup = no migration. Confirm the backup is non-empty and restorable before you proceed.
- **Idempotent by default.** A script must be safe to run twice. Guard creates with existence checks, use `mkdir -p`, append only if absent, make migrations re-entrant. Second run should be a no-op, not a crash or a duplicate.
- **Dry-run first** on anything that mutates state. Provide and use `--dry-run` / `--check` / `terraform plan` / `--what-if`. Read the plan before you apply it.
- **Confirm the target host before every destructive op.** Echo the hostname/context you're acting on and verify it's the intended one. A `down -v` on the wrong box is unrecoverable. Pin the target explicitly — never rely on an ambient default.
- **Secrets stay out of git.** No passwords, keys, or tokens in compose files, `.env` committed to the repo, Dockerfiles, or CI YAML — R8. Read them from the environment, a secrets store, or untracked files with no real-value default. Fail loudly when a secret env var is missing rather than baking in a fallback.
- **Reversible before irreversible.** Have a rollback (previous image tag, prior config, snapshot) in hand before you touch prod. Change one thing at a time so you can attribute and undo.

### Quality gates
Before claiming an infra change done:
- [ ] Scripts pass `bash -n` and **shellcheck** clean (strict mode: `set -euo pipefail`).
- [ ] Script is **idempotent** — proven by running it twice; the second run is a no-op.
- [ ] A **smoke test** exists and exits 0 (curl endpoint + health + TLS + no restart loop).
- [ ] **Reachability verified from outside the box**, not just localhost on the host.
- [ ] **Backup/rollback path documented** and tested (you know the exact restore command).
- [ ] **Docs/install steps updated** to match actual behavior — supported distros, env vars, ports, commands — R6. No drift between the runbook and reality.
- [ ] Dry-run output reviewed for anything that mutates prod state.
- [ ] **The exposed surface is only what you intended** — ports, routes, and buckets enumerated and checked from off the host; no secret in any committed config.
- [ ] **Workload identity is least-privilege** — non-root container, scoped role/service account, no wildcard IAM. Admin-by-default is a finding, not a default.

### Failure modes to guard against
- **"Container running but in a restart loop / 404 / no TLS cert."** The classic a visual glance misses: it's "up" but crash-looping, the reverse proxy 404s the route, or the cert never issued. Always curl the real URL.
- **Config drift between docs and reality.** Docs say Ubuntu-only but the installer supports 14 distros; docs list ports/env vars that no longer match. Drift actively misleads half-knowledge users. Reconcile in the same change — R6.
- **Destructive op on the wrong host.** Right command, wrong box. Confirm the target every time.
- **Non-idempotent script that breaks on the second run** — duplicate users, port already bound, "file exists" crash, doubled cron entries. Re-run safety is part of the spec.
- **Secrets leaking into committed config** — a literal password in compose/env/CI. Once pushed, treat as compromised: rotate, then scrub history (R8).
- **State-loss on deploy** — `down -v`, image swap, or migration that drops the volume/DB because no backup was taken first.

### Recommended skills & tools
- **bash strict mode** (`set -euo pipefail`, quoted vars) + **shellcheck**/`bash -n` for every script — the cheapest infra bug catcher.
- **Idempotent scripts with `--dry-run`** and **backup-before-destructive** built in as flags, not afterthoughts.
- **Smoke-test scripts** that curl the endpoint, check health, confirm TLS, and detect restart loops — the gate for "verified".
- **sentry-cli skill** for wiring up and querying error monitoring after a deploy — catch the runtime errors a smoke check won't.
- **Context7** for authoritative tool docs (Docker, Traefik/Nginx, systemd, cloud CLIs) before guessing flags; **web search** for vendor/provider docs and changed API behavior.
- **claude-mem** for runbook memory — record the working sequence, the gotchas, and the rollback so the next session doesn't re-derive them.

### Addendum to the STOP table
| Thought | Reality |
|---------|---------|
| "Exit 0 means it works." | Exit 0 means the command ran. Curl the endpoint, check TLS, watch for a restart loop — reachability is the proof. |
| "It's just a config tweak, no backup needed." | The one-line tweak is what takes prod down. Snapshot/dump first; a tweak with no rollback is a gamble. |
| "I'll make it idempotent later." | Later is the failed second run at 2am. Re-run safety is part of writing the script, not a follow-up. |
| "I'll test on prod, it's faster." | Faster until it isn't. Dry-run, then a staging/throwaway box, then prod with a rollback in hand. |
| "It's running, so it's fine." | "Running" hides crash-loops and 404s. Up >60s, healthy route, valid cert — or it's not fine. |
| "The default config is fine for now." | Defaults are permissive by design — open ports, root user, wildcard IAM. "For now" is what ships. |
