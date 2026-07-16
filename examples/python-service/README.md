# Example: Orchard — FastAPI inventory service (software-dev profile)

**Scenario.** Orchard is a small FastAPI inventory microservice — Python 3.12, Postgres,
SQLAlchemy, Alembic migrations, pytest. The operator is Maya Chen, a backend engineer who
tracks work as GitHub issues/PRs. This folder shows what the harness looks like *layered onto
that one service*: the universal core is installed globally on Maya's machine, and the project
itself carries only the software-dev profile plus the project-specifics below.

**Set it up like this:**

```bash
# 1) Install the universal core once, globally (Maya's machine, all projects):
./setup.sh --global --operator-name "Maya Chen" --operator-role "backend engineer"

# 2) Layer the software-dev profile onto THIS repo (no core copied in — core is global):
./setup.sh --profile software-dev --profile-only --target . \
  --operator-name "Maya Chen" --operator-role "backend engineer" \
  --tracker github --with-hooks
```

**What to notice.**

- **`.harness/verify.conf` is the single source of truth for "shippable."** The profile says
  "build → types → lint → tests"; the conf makes that concrete for FastAPI (`ruff format`,
  `ruff check`, `mypy app`, `pytest -q`, plus a migrations-current check). `verify.sh` and any
  human both read this one file, so the commands never drift.
- **`CLAUDE.md` here is *only* the project-specifics layer.** It doesn't repeat the core or the
  profile — `setup.sh` stacks all three. It sharpens what "done" means for *this* service:
  Alembic migration present and current, OpenAPI/response-model contract honored, and the real
  request path exercised, not just a green unit test.
- **`--with-hooks` installs git guardrails** (secret-scan, protect-main, conventional-commit) so
  the no-secrets and atomic-commit rules are enforced deterministically, not just remembered.
- **The bundled `release-check` skill** shows that an example project can ship its own skill —
  it loads only when cutting a release, keeping everyday context lean.

**Files here:**

- `README.md` — this file.
- `CLAUDE.md` — the project-specifics layer (Orchard's stack, "done," conventions, gotchas).
- `.harness/verify.conf` — the concrete verify phases for this FastAPI service.
- `.claude/skills/release-check/SKILL.md` — a small bundled skill for cutting an Orchard release.
