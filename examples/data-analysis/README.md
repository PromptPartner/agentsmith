# Example: Tideline — monthly churn analysis (data-crunching profile)

**Scenario.** Tideline is a monthly customer-churn analysis — Python, pandas, DuckDB, and
Jupyter notebooks that ingest CSV/Parquet extracts and emit a stakeholder report. The operator is
Priya Nair, a data analyst who tracks open problems in a `KNOWN-ISSUES.md` at the repo root. This
folder shows the harness *layered onto that one analysis repo*: the universal core is installed
globally on Priya's machine, and the project itself carries only the data-crunching profile plus
the project-specifics below.

**Set it up like this:**

```bash
# 1) Install the universal core once, globally (Priya's machine, all projects):
./setup.sh --global --operator-name "Priya Nair" --operator-role "data analyst"

# 2) Layer the data-crunching profile onto THIS repo (no core copied in — core is global):
./setup.sh --profile data-crunching --profile-only --target . \
  --operator-name "Priya Nair" --operator-role "data analyst" \
  --tracker "a KNOWN-ISSUES.md at the repo root" --with-hooks
```

**What to notice.**

- **`.harness/verify.conf` is the single source of truth for "shippable."** The profile says
  "schema holds and row counts reconcile"; the conf makes that concrete for Tideline — a `schema`
  phase asserts the processed Parquet's columns/types, a `reconcile` phase checks inputs in ==
  outputs + explained drops, and a `notebook` phase executes the report notebook top-to-bottom so
  a stale cell can't smuggle a wrong number into the report.
- **`CLAUDE.md` here is *only* the project-specifics layer.** It doesn't repeat the core or the
  profile — `setup.sh` stacks all three. It sharpens what "done" means for *this* analysis:
  reproducible from the raw extract in one clean pass, row counts reconciled at every join, schema
  asserted, and every number in the report traceable back to the query that produced it.
- **"Done" is data-honest, not just green.** A notebook that runs is not a verified analysis —
  no silent NaN coercions, no silent dedup, no unexplained dropped rows. Every loss carries a
  logged count and reason, so a believable-but-wrong total gets caught instead of shipped.
- **`--with-hooks` installs git guardrails** (secret-scan, protect-main, conventional-commit) so
  the no-secrets and atomic-commit rules are enforced deterministically — useful even here, where
  raw extracts can carry customer PII that must never land in a commit.

**Files here:**

- `README.md` — this file.
- `CLAUDE.md` — the project-specifics layer (Tideline's stack, "done," conventions, gotchas).
- `.harness/verify.conf` — the concrete verify phases for this churn analysis.
