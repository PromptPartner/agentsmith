<!-- PROFILE · data-crunching -->
## Profile: Data Crunching & Analysis

**Use this profile when** you're cleaning, transforming, joining, aggregating, or analyzing datasets — notebooks, metrics/reporting, ETL, spreadsheets, SQL. Any work where the deliverable is a number, a table, or a chart that someone will trust and act on.

### What "done" and "verified" mean here
"The query ran" is NOT verified — a query can run cleanly and still be wrong. An analysis is verified when:

- The pipeline runs **end-to-end from the raw source to the final output in one clean pass**, reproducibly (R5). No hand-edits between steps that a re-run wouldn't reproduce.
- **Row counts reconcile at every stage**: inputs in = outputs + explained drops. Every lost record is accounted for (R3).
- **One concrete record is traced raw → final** by hand (R3): pick a real ID, follow it through each transform, confirm it lands where and how you expect.
- **Spot-checks against the raw source match** — sample 5–10 rows of the output and confirm them against the original, not against an intermediate.
- **Totals reconcile** against a known control (a prior report, a source-system total, a hand-summed subset).

Until all five hold, it's "the code executed," not "the answer is right."

### Integrity rules (load-bearing)
- **NEVER silently drop rows.** Every filter, join, dedup, or `dropna` that loses records logs the **count and the reason** ("dropped 412 rows: null customer_id"). Unexplained shrinkage is a bug until proven otherwise.
- **Account for NULL / missing / duplicate explicitly.** Decide and document: drop, impute, or keep — and how many. A NULL silently becoming 0 in a SUM is a classic wrong-number bug.
- **Watch join fan-out.** A non-unique key on the "one" side multiplies rows and silently double-counts. Check cardinality (1:1 / 1:many) before and the row count after every join.
- **Validate types, ranges, units.** Numbers stored as strings, dates as text, negative quantities, prices off by 100× (cents vs dollars) — assert the expected type and a sane range at ingest.
- **Keep the RAW source immutable (R9).** Transform into NEW outputs; never overwrite or hand-edit the source. The raw file/table is the ground truth you spot-check against.
- **Beware silently-changed sources between runs.** Record source row count + a snapshot date/hash; if today's "same" source has different counts, stop and find out why before trusting any result.

### Reproducibility rules
- **Script or notebook over manual edits.** Manual spreadsheet surgery isn't reproducible or auditable — a re-run can't reproduce a cell you edited by hand, and nobody can review it. If you must touch a sheet, encode the change as a documented, repeatable step.
- **Pin and record the source snapshot + date.** "Sales export, pulled 2026-06-25, 1,204,891 rows" — name the version in the output so the number can be reproduced.
- **Set seeds for any randomness** (sampling, train/test split, shuffles) so a re-run is identical.
- **One concern per transform step (R4).** Clean, then join, then aggregate — as separate, named steps, not one opaque mega-query. Easier to row-count and trace each stage.
- **Record assumptions and the exact source version in the output** — timezone, currency, fiscal-year start, "active = last 30 days," whatever you assumed. The next person (or future you) inherits the assumptions, not just the number.

### Quality gates
Before calling an analysis done, tick each:

- [ ] Row counts reconcile at each stage (in = out + explained drops).
- [ ] No unexplained drops or NULLs; every loss has a logged count + reason.
- [ ] Join cardinality checked; no fan-out double-counting.
- [ ] Types, units, ranges validated at ingest and after each transform.
- [ ] Output spot-checked against the RAW source (not an intermediate).
- [ ] Totals reconcile against a known control.
- [ ] Output reproduces from a single clean run (no manual steps).
- [ ] Methodology + source provenance documented (R6) — source, snapshot date, assumptions, transform steps.

### Failure modes to guard against
- **Silent row loss** from an inner join that should've been a left join, or a filter that's broader than intended.
- **Double-counting** from join fan-out on a non-unique key.
- **Mixed units / currencies / timezones** — summing USD with EUR, UTC with local, cents with dollars.
- **Off-by-one date windows** — inclusive vs exclusive endpoints, `>= start AND < end` vs `<= end`, week-start day.
- **Survivorship / selection bias** — analyzing only active accounts, only completed orders, only surviving cohorts, and generalizing.
- **Copy-paste spreadsheet errors** — a formula not dragged to the last row, a hard-coded number where a reference belonged.
- **"Looks plausible" but wrong** — the number is in a believable range, so it's never checked against the source.
- **Non-reproducible manual steps** — a hand-edited cell or one-off sort that a re-run won't reproduce.

### Recommended skills & tools
- **Scripted transforms with assertions** — express the pipeline as a script/notebook; bake in `assert` checks on row counts, schema, and key uniqueness so a bad run fails loudly instead of emitting a wrong number.
- **jq / SQL** for filtering, joining, aggregating — and for the schema/row-count assertions that gate each step.
- **Code-execution** for the analysis itself — run the transform, print intermediate counts, eyeball the spot-checks.
- **claude-mem** for dataset quirks — record the gotchas (this column is cents not dollars; this export drops the header row; this key isn't unique) so the next session doesn't relearn them the hard way.
- **Context7** for library/API docs — confirm the exact semantics of a join/merge/window function instead of guessing.

### Addendum to the STOP table
| Thought | Reality |
|---------|---------|
| "The query ran, so the number's right." | A query can run clean and be wrong. Verified = row counts reconcile + traced record + spot-check + total reconciles. |
| "I'll just fix it by hand in the sheet." | A hand-edit isn't reproducible or auditable. Encode it as a documented, re-runnable step or it didn't happen. |
| "Those few dropped rows don't matter." | You don't know that until you count them and know WHY. Silent drops are bugs until explained. |
| "The join looks fine." | "Looks fine" double-counts. Check key uniqueness and the row count before/after every join. |
| "It's in a plausible range, ship it." | Plausible-but-wrong is the most expensive failure. Spot-check against the raw source and reconcile to a control. |
