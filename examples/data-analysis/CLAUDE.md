<!--
  PROJECT-SPECIFICS LAYER ONLY.
  This file is NOT the whole operating agreement. setup.sh (see README.md) stacks three layers:
    1. the universal core   (installed globally on Priya's machine — the rigid, universal rules)
    2. the data-crunching profile (what "done" / "verified" means for analysis work)
    3. THIS file            (the Tideline-specific stack, "done," conventions, and gotchas)
  Don't re-state the core or the profile here. When the core, the profile, and this file all
  speak, the STRICTER rule wins. Keep this lean — it's loaded every turn.
-->
# Project: Tideline

Tideline is the monthly **customer-churn analysis**. Each run ingests that month's raw extracts,
reconciles them, and emits one stakeholder report (churn rate, churn by cohort/plan, the top
churn drivers). The audience acts on these numbers — they decide retention spend off them — so a
plausible-but-wrong number here is expensive. Reproducibility and provenance are the whole job.

## Stack & layout

- **Language / tools:** Python 3.12, pandas, DuckDB (SQL over the Parquet files), Jupyter.
- **`data/raw/`** — the immutable source extracts, one dated folder per month
  (`data/raw/2026-06/`). **Never overwritten, never hand-edited.** This is the ground truth we
  spot-check the output against. Files: `subscriptions.csv`, `events.parquet`, `accounts.csv`.
- **`data/processed/`** — generated, disposable, git-ignored. The pipeline writes
  `churn.parquet` (one row per account-month) and intermediate stage outputs here. Safe to delete
  and regenerate — if you can't, that's a reproducibility bug.
- **`notebooks/`** — `churn.ipynb` is the report notebook (loads `churn.parquet`, builds tables +
  charts, narrates the findings). Exploration notebooks live in `notebooks/scratch/` and are
  never a pipeline dependency.
- **`scripts/`** — the reproducible pipeline steps and the verify gates (`check_schema.py`,
  `reconcile_rows.py`, plus the per-stage transforms).
- **`reports/`** — the rendered monthly deliverable (`reports/2026-06-churn.html`), dated.
- **`KNOWN-ISSUES.md`** (repo root) — the tracker. Every data quirk, deferred fix, and open
  question goes here so next month doesn't relearn it the hard way.

**Pipeline order (one concern per step, each re-runnable):**
`raw → ingest+validate → clean → join → aggregate → churn.parquet → notebook → report`.
Each step is its own script writing a named stage output, so row counts can be checked between
stages and one record traced through each transform.

## What "done" means here

The profile's gates apply in full. Concretely, for Tideline an analysis is done only when:

- **It reproduces from `data/raw/<month>/` in one clean pass** — wipe `data/processed/`, run the
  pipeline, re-execute the notebook, and you get the same report. No hand-edited cells, no
  one-off sorts, no manual spreadsheet surgery between steps. If a re-run can't reproduce it, it
  didn't happen.
- **Row counts reconcile at every join and filter** — inputs in == outputs + explained drops.
  Every dropped record is logged with a count and a reason ("dropped 38 rows: account_id null").
  Unexplained shrinkage is a bug until proven otherwise.
- **The schema is asserted, not assumed** — `check_schema.py` fails the run if a column is
  missing, renamed, or the wrong dtype (the classic: `account_id` arriving as float, or
  `signup_date` as a string).
- **Every number in the report traces to a query** — no hard-coded figures, no numbers typed into
  a markdown cell. If a stakeholder asks "where does 4.2% come from?", you can point at the exact
  DuckDB query and the stage output it ran on.
- **No silent NaN / dedup** — every `dropna`, `fillna`, and `drop_duplicates` is deliberate,
  counted, and documented. A NULL silently becoming 0 in a churn-rate denominator is exactly the
  wrong-number class we guard against.
- **Provenance is recorded in the output** — source extract names, the snapshot row counts, the
  pull date, and the assumptions (timezone, "active = billed in last 30 days") are written into
  the report so the number can be reproduced and audited months later.

## verify.conf phases

`.harness/verify.conf` defines what `verify.sh` runs. Phases run top-to-bottom; the **first
failure stops the run** — fix it and re-run, don't skip ahead.

- **`schema`** — `python scripts/check_schema.py data/processed/churn.parquet`. *Why first:* a
  wrong dtype or a renamed column poisons every downstream number silently. Catch the shape
  before trusting any value computed from it.
- **`reconcile`** — `python scripts/reconcile_rows.py`. *Why:* this is the load-bearing
  data-integrity gate. It re-derives inputs-in vs outputs-plus-explained-drops across each stage
  and fails loudly on any unexplained row loss or join fan-out — the failure that a clean-running
  query will otherwise hide.
- **`notebook`** — `jupyter nbconvert --execute notebooks/churn.ipynb`. *Why last:* executing the
  report end-to-end proves the deliverable reproduces from the validated, reconciled data — and a
  stale cached cell can't smuggle a stale number into the report.

## Conventions

- **Raw is immutable.** Read from `data/raw/`, write to `data/processed/`. Never edit a raw file —
  if a source is dirty, fix it in a documented, re-runnable cleaning step, not by hand.
- **Intermediate artifacts** go in `data/processed/` (git-ignored), one named file per stage
  (`stage1_clean.parquet`, `stage2_joined.parquet`). Never commit generated data — extracts carry
  customer PII and must never land in git.
- **Notebook hygiene:** `churn.ipynb` runs top-to-bottom from a fresh kernel — no out-of-order
  cells, no manual edits to cached output. Clear outputs before committing so diffs stay readable
  and a stale render can't masquerade as a fresh result. Exploration stays in `notebooks/scratch/`.
- **Name the snapshot in the output:** e.g. "subscriptions.csv, pulled 2026-06-25, 1,204,891
  rows." A number you can't tie to a source version isn't reproducible.
- **Seed any randomness** (sampling, cohort shuffles) so a re-run is byte-identical.
- **One concern per commit / per transform step.** Clean, then join, then aggregate — separate,
  named steps, so each can be row-counted and traced.

## Gotchas & decisions

- **Timezone: events are UTC, billing is account-local.** A churn "month" is defined on **billing
  local time** (the account's billing anchor), not UTC. Mixing the two once shifted ~0.3% of
  accounts into the wrong month at boundaries. Convert event timestamps to billing-local before
  the month bucket — documented in `KNOWN-ISSUES.md`.
- **The accounts→subscriptions join silently dropped rows once.** `account_id` is **not unique**
  in `subscriptions.csv` (one row per subscription, accounts can have several). An inner join
  dropped accounts with no active subscription and a naive join fanned out the rest, double-
  counting churn. Decision: left-join from accounts, assert 1:many cardinality, and reconcile the
  row count before and after. `reconcile_rows.py` now guards this.
- **Churn-rate denominator must exclude brand-new accounts.** An account that signed up *this*
  month can't churn this month; including them deflates the rate. "At-risk base = accounts active
  at the start of the month." Assumption recorded in the report header.
- **`plan_price` is stored in cents, not dollars.** Summing it as dollars overstated revenue-at-
  risk 100×. `check_schema.py` asserts the column is integer cents; the aggregation divides by 100
  exactly once, at the reporting step. Logged in `KNOWN-ISSUES.md` so it isn't rediscovered.
- **The "same" extract can change shape between months.** Upstream has renamed columns
  (`is_active` → `active`) and changed row counts on a supposedly stable export without notice.
  `ingest+validate` records each source's row count + a content hash and compares against last
  month's; a surprise diff stops the run for investigation before any number is trusted. If the
  source genuinely changed, document the new shape in `KNOWN-ISSUES.md` before proceeding.
