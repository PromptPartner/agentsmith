<!-- PROFILE · deep-research -->
## Profile: Deep Research & Analysis

**Use this profile when** the work is a multi-source investigation whose output is a fact-checked, cited answer — market/competitive analysis, technical or literature review, due diligence, a sourced report or recommendation. If the question is underspecified — scope, budget, region, time horizon, or decision criteria missing — ask 2–3 clarifying questions BEFORE researching. A precise question you can answer beats a broad one you can only gesture at.

### What "done" and "verified" mean here
Sharpens R2/R5 for claims, not code.

- A finding is **verified** when it is corroborated by ≥2 *independent* sources AND has survived an active attempt to refute it. "A source says X" is a **lead**, not a verified fact.
- The report is **done** when: every load-bearing claim carries a citation to a source you *actually consulted*; uncertainty and conflicting evidence are stated openly, not smoothed over; and the synthesis visibly separates **fact** (sourced) from **inference** (your reasoning over the facts).
- Confidence is explicit. A claim resting on one source is labeled single-sourced, not laundered into the prose as settled.
- "It sounds right" and "it's widely repeated" are not verification. Repetition across sources that all cite the same origin is *one* source, not many.

### The research method (load-bearing)
1. **Fan out.** Search multiple angles and source types per question — don't stop at the first hit or the first page. The first result is a starting point, not the answer.
2. **Corroborate.** For any load-bearing claim, require ≥2 *independent* sources. Independent means different origin, not two outlets reprinting one press release.
3. **Adversarial verify.** For each key claim, run a deliberate refutation pass: default to skeptical, actively try to break it — search for the counter-case, the debunk, the contradicting datum. Keep the claim only if it survives. Spawn a separate agent for this when you can; a refuter that didn't gather the evidence is harder to fool.
4. **Diversity over redundancy.** Distinct lenses — primary source, domain expert, contrarian/critic — beat re-reading the same source three ways. One more angle outvalues one more confirmation.
5. **Completeness critic.** Before finishing, ask: what source type, modality, region, time period, or stakeholder did I NOT check? Name the gap. Fill it or flag it.

### Source & citation integrity
- **Cite what you consulted.** Link/quote the actual source you read — never a remembered or reconstructed one. No URL you opened = no citation.
- **Quote accurately.** Preserve numbers, units, and qualifiers. Don't round away the caveat.
- **Date-stamp time-sensitive facts** (prices, market size, rankings, "latest version"). A fact true last year may be false now; say *as of when*.
- **Prefer primary over secondary.** Go to the filing, the spec, the dataset, the original paper — not the blog summarizing it.
- **Save the trail durably.** Every substantive source, scrape, and note goes to a durable `docs/research/<topic>.md` (or equivalent), committed — not held in chat scrollback or local memory where the next session can't see it. Per R9, that material is **never deleted** in a cleanup; obsolete → `docs/research/_archive/`, not `rm`.
- **State confidence and flag single-sourced claims** explicitly in the text, not just in your head.

### Quality gates
Before calling a report done, confirm:
- [ ] Scope clarified up front (or explicitly noted as assumed, with the assumption stated).
- [ ] Every key claim has ≥2 independent sources — or is labeled single-sourced.
- [ ] Every key claim survived an adversarial/refutation pass.
- [ ] Every citation resolves to a real source you actually consulted.
- [ ] Conflicting evidence is surfaced, not hidden — disagreements shown, not averaged away.
- [ ] Confidence/uncertainty stated per claim; time-sensitive facts date-stamped.
- [ ] All sources/notes saved durably to `docs/research/` and committed (R9).
- [ ] Fact vs inference visibly separated in the synthesis.
- [ ] A completeness pass run — gaps named, not silently skipped.

### Failure modes to guard against
- **Single-source-as-fact** — one source dressed up as established truth; circular citation (many outlets, one origin) counted as corroboration.
- **Confirmation bias** — searching only for what confirms the thesis; quietly dropping the inconvenient result.
- **Skipping the refutation pass** because the claim "feels solid." Feelings aren't evidence; that's exactly when it slips through.
- **Hallucinated or broken citations** — a plausible URL/title that doesn't exist or doesn't say what you claim.
- **Stale facts as current** — last-cycle numbers presented as today's, no date attached.
- **Plausible-but-unverified** claims surviving into the report because no one tried to break them.
- **Losing the source trail** (R9) — notes in ephemeral memory, sources unsaved, deleted in cleanup; the report's claims become unre-checkable.
- **Answering an underspecified question** instead of narrowing it first — a confident answer to the wrong question.

### Recommended skills & tools
- **`deep-research` skill — the primary tool.** Fans out searches, fetches sources, runs the adversarial-verify pass, and synthesizes a cited report. Reach for it first on any multi-source, fact-checked question. (If the question is underspecified, narrow scope *before* invoking.)
- **Web search + web fetch** — for the searches and to read the actual source (don't cite a snippet you didn't open).
- **Context7** — for technical/library/API facts, to pin claims to current docs rather than recalled versions.
- **Multi-agent fan-out** — parallel agents for breadth (more angles, faster) and, crucially, for the **adversarial verification** pass: a separate agent tasked to refute is harder to fool than the one that gathered the evidence.
- **Durable `docs/research/` files** — every substantive finding and source list written down and committed (R9); persist key findings to claude-mem so the next session inherits them. Keep the surface tight (R10): one file per topic, not a sprawl. Use `/new-research` (the harness `new-research` skill) to scaffold one.

**If the `deep-research` skill isn't installed, the method still applies** — fan out the searches by hand, open every source, and run a separate refute pass yourself. The skill accelerates the method; it isn't a prerequisite.

### Addendum to the STOP table
| Thought | Reality |
|---------|---------|
| "One good source is enough." | One source is a lead, not a fact. Load-bearing claims need ≥2 independent ones — or get labeled single-sourced. |
| "I'm confident enough to skip the refute pass." | Confidence is the symptom, not the proof. The claims that feel solid are exactly the ones that slip through unrefuted. Try to break it anyway. |
| "I'll reconstruct the citation from memory." | Reconstructed citations are how hallucinated ones ship. Cite only the source you actually opened, or drop the claim. |
| "I'll keep the notes in local memory." | Ephemeral notes vanish and can't be re-checked (R9). Write sources to `docs/research/` and commit, or the trail is gone. |
| "It's everywhere online, so it's true." | Everywhere-online is often one origin echoed N times — that's single-sourced. Trace claims to their root before counting them as corroboration. |
