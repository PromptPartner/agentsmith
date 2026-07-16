<!--
  PROJECT-SPECIFICS LAYER — Orchard.
  This is NOT the whole operating agreement. setup.sh assembles three layers, in order:
    1. universal core      (installed globally — the rigid rules: read-before-write,
                            failing-test-first, atomic commits, no secrets, evolve-the-harness)
    2. software-dev profile (what "done"/"verified" mean for code that builds, runs, is tested)
    3. THIS file           (the Orchard-only sharpening below)
  When core and profile both speak, the stricter wins; the operator's explicit instructions win
  over both. Don't re-emit the core or the profile here — see README.md for how the layers stack.
-->

# Project: Orchard

Orchard is a small inventory microservice: a FastAPI app over Postgres that tracks stock items,
quantities, and warehouse locations for other internal services to call. It is a backend service
with **no UI** — the "user-facing surface" is the HTTP/JSON API and its OpenAPI schema. Operator:
**Maya Chen** (backend engineer). Work is tracked as **GitHub** issues and PRs.

## Stack & layout

- **Python 3.12**, FastAPI, Pydantic v2, SQLAlchemy 2.x (async), Alembic for migrations.
- **Postgres 16** — the only datastore. No ORM-side business logic; queries live in the repo layer.
- **pytest** (+ `pytest-asyncio`), `ruff` (format + lint), `mypy` for types.
- Key directories/files:
  - `app/main.py` — FastAPI app factory + router wiring.
  - `app/api/` — route handlers (one module per resource, e.g. `items.py`, `locations.py`).
  - `app/models/` — SQLAlchemy ORM models (the DB shape).
  - `app/schemas/` — Pydantic request/response models (the API contract — distinct from ORM).
  - `app/repositories/` — DB access; handlers call these, never the session directly.
  - `app/db.py` — engine/session setup, dependency-injected into handlers.
  - `migrations/` — Alembic revisions (`alembic.ini` at repo root).
  - `tests/` — mirrors `app/` (`tests/api/`, `tests/repositories/`).
  - `.harness/verify.conf` — the verify phases; `scripts/verify.sh` runs them in order.

## What "done" means here

The profile's loop (read → failing test → implement → verify → commit) and its two-gate
"verified" (within-a-layer **and** across-layers) apply as-is. Orchard sharpens them:

- **Schema change ⇒ migration, always.** Any edit under `app/models/` that changes a table is
  not done until there's a matching Alembic revision *and* `alembic check` is clean. A model the
  DB can't actually hold is a broken change, even if the unit tests pass against a fresh schema.
- **The API contract is the response model.** Every route declares a Pydantic `response_model`.
  If you change what a route returns, change the schema in the same unit — the OpenAPI doc at
  `/openapi.json` is generated from these, and downstream callers read it. A field renamed in the
  handler but not in the schema is the classic contract drift the profile's R3 trace catches.
- **"Across layers" = a real request.** Within-a-layer green (mypy + pytest) is not enough.
  Exercise the actual path at least once: start the app (or use FastAPI's `TestClient` against the
  full app, not a mocked handler) and send the request, so handler → repository → DB → response
  model is run end to end. Trace one concrete value (e.g. an item's `sku`) through all four.
- **Migrations are forward-safe.** A migration must apply cleanly on a copy of current data, not
  only on an empty DB. Destructive column drops get a deprecation step first (see Gotchas).
- **Errors are part of the contract too.** A new failure mode (a 404, a 409 on duplicate `sku`,
  a 422 validation error) is only done when it's a deliberate, tested response — not an
  uncaught 500. If a handler can now fail a new way, there's a test that asserts the status and
  the error body, because callers branch on those.

A concrete across-layers trace (the R3 five-liner, done in the PR body before commit) for adding
an item's `sku`: the request JSON carries `sku` → the Pydantic `ItemCreate` schema validates it →
the repository writes it to the `items.sku` column (unique index) → the response is built from the
`ItemRead` schema → `/openapi.json` advertises `sku` as a required string. If `sku` is present at
the handler but missing from `ItemRead`, callers never see it — and only the trace, not a green
unit test, catches that.

## verify.conf phases

`scripts/verify.sh` reads `.harness/verify.conf` and runs these top-to-bottom; the **first
failure stops the run** so you fix the earliest break instead of chasing a cascade:

1. **`format` — `ruff format --check .`** — formatting is non-negotiable and mechanical, so it
   runs first and cheapest; a diff here means "run `ruff format`," not "think."
2. **`lint` — `ruff check .`** — catches unused imports, shadowed names, obvious bugs before the
   slower type/test phases spend time on code we already know is wrong.
3. **`types` — `mypy app`** — Pydantic v2 + SQLAlchemy 2.x are heavily typed; mypy catches
   contract drift (wrong field types, a handler returning the wrong schema) statically, cheaper
   than a test run. We type-check `app`, not `tests`, to keep the signal on shipping code.
4. **`migrations` — `alembic check`** — fails if the ORM models have drifted from the migration
   history (a model change with no revision). This is the deterministic guard behind the
   "schema change ⇒ migration" rule above — it's why that rule rarely needs a human reminder.
5. **`test` — `pytest -q`** — the full suite last, because it's the slowest and most likely to
   depend on everything above being sound. Run the *whole* suite, not just your new test (R5).

## Conventions

- **Commit scope = the area touched:** `feat(api): …`, `fix(repo): …`, `feat(models): …`,
  `chore(migrations): …`, `test(api): …`. The message says WHY, not what (profile R4).
- **Routes** live in `app/api/<resource>.py`; **ORM models** in `app/models/`; **API schemas**
  in `app/schemas/`; **DB access** in `app/repositories/`. Handlers never touch the session
  directly — they go through a repository, so DB logic stays testable in one place.
- **Tests mirror source:** a change in `app/api/items.py` gets/updates `tests/api/test_items.py`.
- **Every new/changed endpoint ships its `response_model`** and at least one `TestClient` test
  that hits the running app, not a mocked function — that's the across-layers gate, encoded.
- **GitHub is the tracker:** open/reference the issue in the PR; one concern per PR.

## Gotchas & decisions

- **Async sessions, async tests.** We use `pytest-asyncio` with an async session fixture per
  test, rolled back at teardown, because early sync-test attempts shared a session across
  tests and leaked state, making failures order-dependent and impossible to bisect. Use the
  `async_session` fixture; don't open your own engine in a test.
- **Two model worlds on purpose.** SQLAlchemy models (`app/models/`) and Pydantic schemas
  (`app/schemas/`) are kept separate because collapsing them once leaked DB-only columns
  (internal `row_version`, soft-delete flags) into the public API. The schema is the contract;
  the ORM model is storage. Map between them explicitly in the repository layer.
- **No destructive migration in one step.** Dropping/renaming a column happens over two releases
  (add-new + backfill, then drop-old) because a single-step drop broke an in-flight reader
  during a rolling deploy. `alembic check` guards drift; the two-step rule guards live data.
- **`alembic check` ≠ `alembic upgrade`.** `check` only tells us models and history agree; it
  does **not** prove the migration applies to real data. Before merging a migration, run it once
  against a dump of representative data (the `release-check` skill reminds you at release time).
