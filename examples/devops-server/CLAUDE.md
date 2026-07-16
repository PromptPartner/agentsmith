<!--
  PROJECT-SPECIFICS LAYER — Harbor.
  This file is ONLY the project-specific bottom layer. setup.sh stacks three layers:
  (1) the universal core (installed globally, see README), (2) the devops-setup profile, and
  (3) this file. Do NOT re-state core rules or the profile here — they're already loaded. This
  layer says what is true about THIS box and sharpens "done" for Harbor's infra. When core/
  profile and this file all speak, the stricter wins; Sam's explicit instructions win over all.
-->

# Project: Harbor

Harbor is a single self-hosted web app on one VPS. The whole stack — the app, its datastore, and
a Caddy reverse proxy that issues TLS automatically — is described by `docker-compose.yml` and
brought up by `install.sh` on a clean box. The goal that shapes every change: a fresh box plus
`install.sh` lands a working, HTTPS-reachable site with no hand-tweaking afterward.

## Stack & layout

- `docker-compose.yml` — the services: `app`, `db`, and `caddy`. Caddy publishes `:80`/`:443` and
  proxies the app; the app and db are on an internal network, not published to the host.
- `Caddyfile` — one site block per domain; Caddy handles ACME/TLS on its own. The domain is read
  from `${APP_DOMAIN}`, never hardcoded.
- `install.sh` — the one entry point: installs Docker if absent, writes `.env` from the operator's
  answers (or refuses to clobber an existing one), pulls/builds images, runs migrations, brings the
  stack up, then runs the smoke check. Strict mode (`set -euo pipefail`); safe to run twice.
- `scripts/smoke.sh` — the proof-of-life: curls the public URL, asserts the expected status, checks
  the cert, and confirms the container has been up long enough to not be crash-looping.
- **Env handling.** All secrets and host-specific values live in an untracked `.env`. The repo
  ships `.env.example` (keys + dummy placeholders) only. Compose reads `${VAR}`; nothing real is
  committed. A missing required var fails the script loudly — there is no real-value fallback, so a
  half-configured box stops at the door instead of booting with a silent default.
- **Data lives in named volumes.** The db's data is a named Docker volume so an image swap or
  `compose up` recreation keeps it; only an explicit `down -v` (gated by a backup) ever removes it.

## What "done" means here

"Done" for Harbor is infra-grade, stricter than "the command exited 0":

- **Idempotent re-run.** Running `install.sh` a second time is a no-op, not a crash and not a
  duplicate — no "port already bound", no second `.env`, no doubled migration. Prove it by running
  it twice.
- **Reproducible from a clean box.** A throwaway VPS plus `install.sh` reaches the same running
  stack. If a step only works because of leftover state on the current box, it isn't done.
- **TLS valid.** Caddy has actually issued the cert; `https://${APP_DOMAIN}` serves with no expiry
  or SAN warning — checked from *off* the box, not just `curl localhost`.
- **Container healthy, not just "running".** Up >60s, not cycling, health route returns OK, first
  log lines after boot show no error. "running" in `docker ps` is not evidence.
- **Secrets out of the repo.** Every credential comes from `.env` / the environment. If a secret
  ever lands in a tracked file, treat it as compromised: rotate, remove, scrub history.
- **A documented rollback.** Before any change to prod, the previous image tag and a DB dump are in
  hand, and the exact restore command is written down. No rollback path = not shippable.
- **Reboot-survival.** Services carry `restart: unless-stopped`; after a host reboot the stack and
  TLS come back on their own. If a deploy only survives because the box never restarted, it isn't
  done — confirm the stack returns after a reboot when the change touches startup.

## verify.conf phases

`.harness/verify.conf` is the contract; it mirrors the profile and stops on the first failure.

- **`shellcheck :: shellcheck install.sh`** — the cheapest infra bug catcher. Catches unquoted
  vars, missing `set -euo pipefail` fallout, and the typos that silently no-op a deploy. Runs
  first because a broken script can't be trusted to do anything else right.
- **`compose :: docker compose config -q`** — proves the compose file parses *and* every `${VAR}`
  resolves from the environment. Catches an env-var typo or a missing `.env` key before it becomes
  a half-started stack at 2am.
- **`smoke :: bash scripts/smoke.sh`** — the real gate. Curls the public route, confirms TLS, and
  checks the container isn't restart-looping. This is what turns "it came up" into "it's actually
  serving." Last because it needs the stack live.

## Conventions

- **Env vars are declared in one place.** Every variable lives in `.env.example` with a comment and
  a dummy value; `install.sh` and `docker-compose.yml` only ever *read* them. Add a new secret? Add
  the key to `.env.example` in the same change — never the real value.
- **Name hosts by ROLE, not by value.** In docs, commits, and scripts refer to "the app box" / "the
  db box" / "the staging box" and the credential's *rotation policy* — never a real IP, hostname, or
  password. Scripts take the target host as an explicit arg and echo it before acting; never rely on
  an ambient default.
- **Backup before anything destructive.** Any `down -v`, image swap, or migration is preceded by a
  volume snapshot and a `pg_dump`, confirmed non-empty, before the destructive step runs.
- **One thing at a time.** Change the image *or* the config *or* the migration in a step — not all
  three — so a regression is attributable and undoable.
- **Dry-run before mutating state.** Anything that changes the box reads its plan first — `docker
  compose config` to see the resolved stack, a migration `--dry-run`/`check` before it applies.
  Read the plan, then apply; never apply blind.

## Gotchas & decisions

- **"running" but crash-looping.** Early on, `docker ps` showed `app` as Up while it was actually
  restarting every few seconds (bad env var). `docker ps` looked green; the site was down. Decision:
  `smoke.sh` asserts uptime >60s and a 200 from the health route — a green `ps` never counts as
  verified again.
- **Caddy cert race on first boot.** On a fresh box the smoke check ran before Caddy finished the
  ACME handshake and failed on a not-yet-issued cert — a false negative. Decision: `smoke.sh` retries
  the TLS check with a short backoff for up to ~60s before failing, so it distinguishes "cert still
  issuing" from "cert will never issue".
- **Second `install.sh` clobbered `.env`.** The first version rewrote `.env` on every run, wiping the
  operator's real values with placeholders. Decision: `install.sh` refuses to overwrite an existing
  `.env` (writes only if absent) — idempotency includes *not* destroying config.
- **Image swap with no dump.** A deploy did `compose up` with a new image and a forward migration
  before any backup existed; rollback meant guesswork. Decision: every prod-touching step dumps the
  DB and notes the prior image tag first — rollback in hand before, not after.
- **Caddy 404'd a route that "deployed fine".** Compose came up green and the app container was
  healthy, but Caddy 404'd the public path because the proxy target named the wrong upstream port.
  The app worked on its internal port; the edge didn't. Decision: `smoke.sh` curls the *public*
  Caddy URL, not the app container directly — the edge path is the one users hit, so it's the one
  that gets proven.
- **Wrong-box near-miss.** A `down -v` was almost run against the app box while meaning the staging
  box, because the target was an ambient default. Decision: every destructive script takes the host
  as an explicit arg and echoes "acting on: <role>" for confirmation before doing anything — no
  ambient default is ever trusted for a destructive op.
