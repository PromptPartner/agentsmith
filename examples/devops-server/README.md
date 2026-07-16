# Example: Harbor — self-hosted app server on a VPS (devops-setup profile)

**Scenario.** Harbor is a self-hosted web app running on a single VPS: Docker Compose for the
services, Caddy out front for automatic TLS, and an `install.sh` that brings a clean box up to a
running stack reproducibly. The operator is Sam Okafor, a sysadmin who tracks work as GitHub
issues/PRs. This folder shows the harness *layered onto that one box's repo*: the universal core
is installed globally on Sam's machine, and the project itself carries only the devops-setup
profile plus the project-specifics below.

**Set it up like this:**

```bash
# 1) Install the universal core once, globally (Sam's machine, all projects):
./setup.sh --global --operator-name "Sam Okafor" --operator-role "sysadmin"

# 2) Layer the devops-setup profile onto THIS repo (no core copied in — core is global):
./setup.sh --profile devops-setup --profile-only --target . \
  --operator-name "Sam Okafor" --operator-role "sysadmin" \
  --tracker github --with-hooks
```

**What to notice.**

- **`.harness/verify.conf` is the single source of truth for "shippable."** The profile says
  "scripts are sound and the service actually comes up healthy"; the conf makes that concrete for
  Harbor — `shellcheck install.sh`, `docker compose config -q` (the compose file parses and its
  env resolves), then `bash scripts/smoke.sh` (curl the public route, confirm TLS, watch for a
  restart loop). `verify.sh` and any human read this one file, so the commands never drift.
- **`CLAUDE.md` here is *only* the project-specifics layer.** It doesn't repeat the core or the
  profile — `setup.sh` stacks all three. It sharpens what "done" means for *infra*: the install
  re-runs cleanly (idempotent), rebuilds from a clean box (reproducible), TLS is valid and the
  container is *healthy*, not merely "running" — and there's a documented rollback in hand.
- **Secrets stay out of the repo, deterministically.** `--with-hooks` installs the secret-scan,
  protect-main, and conventional-commit guardrails, so the "no live credentials in tracked files"
  rule is enforced at commit time, not just remembered. Harbor's secrets live in an untracked
  `.env` with no real-value default; the repo ships `.env.example` only.
- **"Done" for infra is reachability + reversibility, not a green exit code.** A backup runs
  before any destructive or migrating step, and hosts are named by *role* (app box, db box) with
  a rotation policy — never by value.

**Files here:**

- `README.md` — this file.
- `CLAUDE.md` — the project-specifics layer (Harbor's stack, "done," conventions, gotchas).
- `.harness/verify.conf` — the concrete verify phases for this VPS deploy.
