<!-- PROFILE · document-creation -->
## Profile: Document Creation & Writing

**Use this profile when** the deliverable is prose or a structured document — report, proposal, spec, technical doc, manual, contract/template, README/wiki, or long-form content — rendered to a final format (PDF/HTML/slides/print/site page).

### What "done" and "verified" mean here
Sharpens R2/R3/R5 for documents. A document is **done** only when it has been read in its **RENDERED** form — the actual PDF/HTML/slide/printed page — not just the markdown/source. "The source reads plausibly" is NOT verified. Formatting, link, and image bugs live only in the rendered output; they are invisible in the source.

A document is **verified** when ALL of these hold, checked by looking at the rendered artifact:
- Every link resolves (no 404s, no empty `[]()` markdown links, no dead anchors).
- Every image, table, and diagram displays — not a broken-image icon or an overflowing table.
- Every cross-reference, footnote, figure number, and TOC entry points to the right place.
- Every factual claim, figure, quote, and citation traces to a real source you actually consulted (see Source-grounding).
- Headings, lists, and code blocks render in the intended structure (no collapsed nesting, no escaped markup).
- It reads correctly in BOTH light and dark themes if the target supports them (contrast bugs hide in one mode).

If you cannot render and view the output, say so explicitly — do not claim "verified" from the source alone.

### Source-grounding (load-bearing)
The first pillar. The document must contain no invented facts.
- **No fabricated** statistics, quotes, names, dates, version numbers, prices, citations, URLs, or study references. Ever.
- Every non-obvious claim traces to a source you **actually consulted** — not a source you assume exists. Don't cite from memory; open it.
- **Quote accurately.** Copy exact wording; don't paraphrase inside quotation marks. Verify the attribution (who, where, when).
- **Distinguish levels:** what the source states vs. your inference vs. your recommendation. Label inferences and estimates as such.
- When you cannot confirm a fact, write "unverified" or flag the gap — never paper over it with a confident-sounding invention.
- **Keep the sources** (URLs, fetched docs, PDFs, notes) in a durable location per R9 — so claims can be re-checked later and survive a rebase/cleanup. Archive, never delete.
- Prefer primary sources; corroborate a load-bearing number across two independent sources where it matters.

### Structure & process
- **Outline-first.** Agree the structure — sections, argument flow, what each part must establish — BEFORE drafting prose. Drafting before the skeleton is agreed wastes the most effort.
- **One concern per revision (R4).** Don't mix a structural reorg with a copyedit pass with a fact update in one change — they're impossible to review together.
- **Match the existing document (R1).** Mirror its voice, register, heading style, capitalization, list conventions, and terminology before imposing your own. Read a sibling section first.
- **Keep a glossary / style note** for any long or multi-session document: preferred terms, spellings, acronym expansions, tone. Consistency across a 40-page doc is a discipline, not an accident.
- For source-heavy work, gather and pin sources first, draft second — so prose is grounded as it's written, not retrofitted.

### Quality gates
Tick each before claiming done — none is optional:
- [ ] Outline approved / structure settled before prose.
- [ ] Every factual claim, figure, and quote sourced; sources stored durably (R9).
- [ ] Spelling, grammar, and consistency pass (terminology, capitalization, number/date formats).
- [ ] All links checked in the rendered output — resolve, correct target, no empty markdown links.
- [ ] All cross-references, footnotes, figure/table numbers, and the TOC verified against the rendered output.
- [ ] All images, tables, and diagrams render and are placed/sized correctly.
- [ ] Rendered output (PDF/HTML/slides/print) **actually previewed and eyeballed** — not assumed from source.
- [ ] Every export format checked separately (PDF ≠ HTML ≠ DOCX — each can break independently).
- [ ] Light AND dark theme checked if applicable (contrast/invisible-text).
- [ ] Metadata / front-matter correct (title, author, date, version, slug, tags).
- [ ] Docs/index/nav updated if this doc joins a set (R6).

### Failure modes to guard against
- **Hallucinated facts or citations** — a plausible statistic or a real-looking but nonexistent reference. The single most damaging failure; it destroys trust in the whole document.
- **Broken or empty links** — markdown `[text]()` with no target, dead anchors, stale URLs that only surface on the rendered page.
- **Invisible text / contrast bugs** — dark-on-dark or light-on-light that reads fine in source and disappears only when rendered in one theme.
- **Broken image embeds** — wrong path, missing asset, or oversized image that overflows the page.
- **Stale TOC / cross-refs** — section renumbered or moved, references still point at the old place.
- **Inconsistent terminology** — the same concept called three different things across sections.
- **Drafting before structure** — polished prose built on an outline nobody agreed to, then thrown away.

### Recommended skills & tools
Keep the surface small (R10) — reach for these where they fit:
- **Web search + a docs-fetch tool (Context7)** — ground facts, pull current/canonical reference text, confirm API/spec details before writing them.
- **The deep-research skill** — for source-heavy documents (literature-style reviews, competitive analyses, well-cited reports) where many sources must be fanned out, fetched, cross-checked, and synthesized with citations.
- **The wowerpoint skill** — turn a finished document into a slide deck when the deliverable also needs a presentation form.
- **Markdown/site build + preview tooling** — build the artifact and OPEN it to satisfy the render-verify gate; this is how link/image/contrast bugs get caught.
- **claude-mem** — persist the style note, glossary, and preferred terminology so voice and vocabulary stay consistent across sessions.

**If the `deep-research` skill isn't installed**, still ground every claim in an opened source and cite it — the skill accelerates the research method, it isn't a prerequisite for the source-grounding gate above.

### Addendum to the STOP table
| Thought | Reality |
|---------|---------|
| "I'm fairly sure that statistic is right." | Fairly sure isn't sourced. Open the source and confirm the exact figure, or label it "unverified." Confident invention is the worst failure here. |
| "The markdown looks fine, so the PDF/HTML is fine." | Formatting, link, and image bugs exist ONLY in the rendered output. Render it and look at it — R3 is not satisfied by reading source. |
| "I'll verify the links later." | Later doesn't happen and empty `[]()` links ship. Check every link in the rendered artifact before claiming done. |
| "Close enough on the quote." | A quote is exact or it isn't a quote. Paraphrase outside the quotation marks, or copy the wording verbatim and verify the attribution. |
| "I'll just start writing and find the structure as I go." | Outline-first. Prose built on an unapproved skeleton gets rewritten — agree the structure, then draft. |
