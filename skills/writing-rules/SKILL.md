---
name: writing-rules
description: Write or review anything an agent reads — a core rule, a profile gate, a SKILL.md description, an instruction-file line, a subagent prompt, a handoff note, a verify-phase label. Part of the Agentsmith harness; supplies the levers that decide whether a line changes behaviour or only costs tokens — the two loads, context pointers, the ladder, completion criteria, leading words, the no-op test. Its default move is deletion, so it earns most on a draft that already exists.
---

# Writing rules — and anything else an agent reads

You are writing for a reader who has already read everything. Explanation is waste; precision is
the whole job. Left alone, a model writing instructions for a model spends most of its words
restating what it already knows — every one of those lines is a **no-op**: paid every turn,
changing nothing.

The packaging differs (a `core/` rule, a profile gate, a `SKILL.md`, a subagent prompt, a handoff
note) but the writing does not. The same levers make each one predictable, so the agent takes the
same *process* every run rather than producing the same output.

When the document is a harness surface — a `core/` rule, a profile, a skill, a hook — read
[`HARNESS-SURFACES.md`](HARNESS-SURFACES.md) for where it goes and what it costs.

## Platform vocabulary
Identify the active runtime from this skill's path (`.claude/skills` = Claude,
`.agents/skills` = Codex). Independently inspect the managed rule files for install mode: only
`CLAUDE.md` means Claude, only `AGENTS.md` means Codex, and both mean both-platform. Use that as the
runtime fallback if the skill path is unavailable. “Instruction file” below means the matching
file. In both mode require the generated rule blocks to remain equivalent; edit their shared
`core/` or `profiles/` source, never one generated copy.

## The two loads

Every document and every pointer spends one of two budgets. Most authoring decisions are this one
trade made in different places:

- **Context load** — what always-loaded material costs the agent's window: an instruction-file line, a
  skill `description`, anything sitting in context every turn whether or not it fires.
- **Cognitive load** — what it costs *you*: knowing which documents exist and when to reach for
  each. You are the index. Not a cost to minimise — it's the price of human agency. Spend it where
  human judgement matters; remove it where it doesn't.

Material behind a pointer escapes context load for the price of the pointer's own line. Material
with no pointer at all rides entirely on cognitive load.

## Context pointers

A **context pointer** is a reference held in context that names out-of-context material and encodes
when to reach it. A skill's `description` and an instruction-file line naming a doc are **the same
object**. The pointer's *wording*, not its target, decides how reliably the agent reaches through
it — so a must-have target behind a weak pointer is a variance bug. Sharpen the wording first;
inline the material only if sharpening fails.

A pointer does two jobs: say what the material is, and list the **branches** that should trigger it
(a branch is a distinct case the document handles). Every word is paid every turn, so prune it
harder than the body:

- **Front-load the leading word** — the pointer is where it does its triggering work.
- **One trigger per branch.** Synonyms renaming one branch are one branch written twice.
- **Cut identity the body already carries.**

## The ladder — where each piece sits

Documents are built from **steps** (ordered actions) and **reference** (facts consulted on demand).
They mix freely: all steps, all reference, or both. The decision is how far down each piece sits:

1. **In-file step** — what the agent does, in order. The primary tier.
2. **In-file reference** — consulted on demand. Often a legitimately flat peer-set (every gate of a
   profile on one rung). That's an arrangement, not a smell.
3. **Disclosed reference** — a separate file behind a pointer, loaded only when the pointer fires.

**Progressive disclosure** is the move down that ladder so the top stays legible. Branching is the
cleanest test: **inline what every branch needs; disclose what only some branches reach.** Push too
little down and the top bloats; push too much and you hide what the agent actually needs.

**Co-location** is the within-file companion — the ladder decides how far down, co-location decides
what sits beside it. Keep a concept's definition, rules and caveats under one heading so reading
one part brings its neighbours. (Distinct from duplication: that repeats one meaning in two places,
scattering fragments one meaning across many.)

**Sprawl** is the failure mode here — a document simply too long, even when every line is live and
unique. Attention thins across the excess. The cure is the ladder, not tighter sentences.

## Completion criteria

Every step ends on a **completion criterion** — the condition that says the work is done. Two
properties make it a lever, and both sharpen R5 (verify before you call it done):

- **Clarity** — can the agent tell done from not-done? A vague bound ("understanding reached")
  invites **premature completion**: ending early because attention slipped to *being done*. The
  visible steps still ahead supply the pull; the criterion's clarity is the resistance. Sharpen the
  bound first — it's local and cheap. Only if it's irreducibly fuzzy *and* you observe the rush,
  split the sequence so the later steps aren't in view. That only works across a real context
  boundary (a handoff, a subagent dispatch); an inline call clears nothing.
- **Demand** — how much it requires. "Every consumer of the change checked" forces thorough work
  where "check the change" does not. Demand drives **legwork**: the digging latent in the wording
  rather than written as its own step. It isn't step-bound — "every gate applied" binds a body of
  flat reference the same way.

The strongest criteria are both checkable and exhaustive. This is why R3 says *every* consumer and
R2 says evidence *you produced* — both are demand, written into the bound.

## Leading words

A **leading word** is a compact concept already living in the model's pretraining that the agent
thinks with while running the document (*atomic*, *evidence*, *Chesterton's Fence*, *tracer
bullet*). Repeated as a token, never as a sentence, it accumulates a distributed definition and
anchors a whole region of behaviour in the fewest tokens — because it recruits priors the model
already holds. Coining your own works if you define it clearly, but a made-up word recruits
nothing: you pay in definition tokens what a pretrained word gives free. Reach for an existing word
first.

It anchors twice — in the body for *execution* (the same behaviour every time the word appears),
and in a pointer for *invocation* (when the same word lives in your prompts, your docs and your
code, the agent links them and reaches the material more reliably).

Hunt for passages begging to collapse into one token. A triad spelled out at three sites; a pointer
spending a sentence to gesture at one idea:

- "fast, deterministic, low-overhead" → *tight* (a *tight* loop).
- "a loop you believe in" → *red* — a fuzzy gate becomes a binary observable state.

Assume every document is carrying restatements that leading words retire. Go find them.

**Negation** is the failure mode beside this lever. Steering by prohibition drags the forbidden
behaviour into context and makes it *more* available, not less — *don't think of an elephant*, and
the elephant is all there is. The negation is a weak modifier the strongly-activated concept
overruns, so the ban half-reads as an instruction. **Prompt the positive**: state the target
behaviour so the banned one is never spoken. A prohibition earns its place only as a hard guardrail
you cannot phrase positively — and even then, pair it with the positive target.

## Pruning — the default move is deletion

- Keep each meaning in a **single source of truth**, so changing the behaviour is a one-place edit.
  **Duplication** costs maintenance and tokens, and inflates a meaning's prominence past its real
  rank. (The accidental inverse of a leading word, which repeats a token on purpose, never the
  meaning.)
- The **environment** is a source of truth too — `package.json` scripts, config files, `--help`
  output, the directory layout. A document restating it is a **cache**, and a cache earns its load
  only when the lookup is expensive. Cache what the agent cannot find by looking: the unwritten
  convention, the reason behind a choice, the gotcha no config confesses. Leave one-command lookups
  to the environment, where they cannot go stale.
- Check every line for **relevance** — does it still bear on what the document does? A line loses
  it by never bearing on the task, or by going stale as the world it describes changes. Without a
  pruning discipline the default fate is **sediment**: stale layers that settle because adding
  feels safe and removing feels risky.
- Hunt **no-ops** sentence by sentence. The test is behavioural, not aesthetic: **delete the line —
  does the agent behave differently?** If not, it was never a rule. The test is model-relative, so
  two people disagreeing about a no-op disagree about the default, and settle it by *running the
  document*, not by arguing. When a sentence fails, delete the whole sentence rather than trim
  words from it. It grades leading words too: a word too weak to beat the default (*be thorough*,
  when the agent is already thorough-ish) is itself a no-op, and the fix is a stronger word.

## The review pass

Most of the value lands here, not on a blank file. **Name the failure mode before you fix it** —
sprawl, sediment, duplication, negation, premature completion, no-op — because the vocabulary is
the repair kit. Then, given a draft:

1. **No-op sweep, sentence by sentence.** Grade each line by behaviour, not by length: an agent
   told to shorten optimises for length, because length is what it can see.
2. **Find the duplication.** Nothing stated twice, in any form. It's the most reliable sign a
   document was never tested.
3. **Check the ladder.** Anything only some branches reach goes behind a pointer.
4. **Re-read the pointers** — one trigger per branch, leading word first. A branch that needs
   material and has no pointer to it is the same finding in reverse.
5. **State every prohibition as its positive target**, unless it's a hard guardrail.

**Evidence when you cannot run it.** The no-op test is behavioural, so a review with no run behind
it yields *candidates*, not verdicts (R2). The reachable offline bar: quote the line, name the
failure mode, and say which surviving line already carries the meaning. A deletion you can point at
a single source of truth for is evidence; one justified by "reads redundant" is a guess. Mark the
guesses, and settle them by running the document.

It's working if the document got **shorter** as it got better; if a leading word is visibly doing
work in more than one place; and if nothing is stated twice.

## Report

Say what you deleted and why, in failure-mode terms — not just what you added. If the document grew,
justify the growth against the two loads.

---
*Adapted from [`writing-for-agents`](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/writing-for-agents/SKILL.md)
by Matt Pocock — MIT © 2026. Concepts and leading words are his; the harness framing and R-number
cross-references are ours. See `docs/18-influences.md`.*
