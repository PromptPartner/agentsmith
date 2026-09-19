# ADR format

Follow the repository's existing decision-record convention. Otherwise place sequentially numbered
files at `docs/adr/NNNN-<slug>.md` and use the smallest record that preserves the decision and why:

```markdown
# <Decision title>

<The context, decision, and rationale in one to three sentences.>
```

Add status, considered options, consequences, or supersession links only when they carry information
the short record would lose.

Create an ADR only when all three gates hold:

1. **hard to reverse** — changing it later has meaningful cost;
2. **surprising without context** — a future reader could reasonably undo or relitigate it; and
3. **real trade-off** — viable alternatives existed and the rationale distinguishes them.

Scan the existing ADR directory before choosing the next number. Create the directory lazily on the
first qualifying decision.

---
*Adapted from Matt Pocock's
[`ADR-FORMAT.md`](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/ADR-FORMAT.md)
([MIT](https://github.com/mattpocock/skills/blob/main/LICENSE), 2026).*
