---
name: new-feedback
description: Log a harness lesson / post-incident so the SYSTEM improves, not just this one bug — fires on "log a harness lesson", "post-incident", "we should make this less likely", System-Evolution moments. Part of the Agentsmith harness; scaffolds a numbered docs/feedback/NNNN-*.md with the five-stage template (R9 — numbers are never reused).
---

# New feedback note (harness post-incident)

The point is not to fix THIS bug — it's to change the SYSTEM so this whole CLASS is less likely
(core/60). Small, specific, traceable to the incident.

## When this fires
You were corrected on something a rule could have prevented; you iterated more than you should
have; a human stepped in; you re-derived a decision a past session already made. After fixing the
immediate thing, capture the lesson.

## Fast path — if `./scripts/new-feedback.sh` exists
Run `./scripts/new-feedback.sh "short symptom"` — it computes the next number and writes
`docs/feedback/NNNN-<slug>.md` with the five-stage template, Status `open`.

## Fallback — no script
1. Next number = (highest existing `docs/feedback/NNNN-*.md` + 1), zero-padded to 4 digits.
   Numbers are **never reused** (R9), even if an old entry was archived.
2. Create `docs/feedback/NNNN-<slug>.md` (Status: open) with the five stages:
   - **Evidence / symptom** — what was observed, quoted.
   - **Failure mechanism** — WHY the system allowed it (missing rule / vague instruction / absent
     guardrail / unreached tool / noisy context — almost never "the model was dumb").
   - **Bounded edit** — the smallest change that prevents the whole class.
   - **Named surface** — exactly where it lands (a core rule, a hook, a verify phase, a template);
     prefer a deterministic surface over prose the model can skip.
   - **Non-regression** — the check that stays red on recurrence. Until it's real, Status stays open.

## Report
Name the file, then land the bounded edit on its named surface and flip Status to `applied`.
