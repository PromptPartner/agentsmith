<!-- CORE · subagents, parallelism, tool discipline · universal -->
## Subagents, Parallelism, and Tool Discipline

### Routing — decide and execute, don't ask each time

**Dispatch to a subagent when** the task is self-contained (one area, clear spec, a tight
loop), needs no live-system interaction (no browser, no production box, no interactive login),
and doesn't cross architectural or editorial boundaries.

**Keep it on the main thread when** the task touches multiple areas or crosses concerns, needs
live verification (a real browser, a running service, a query against live data), or needs
judgment about where something belongs.

**Parallel dispatch:** if two or more tasks share no files and have no sequential dependency,
launch them in one message with multiple agent calls so they run concurrently. State the
routing decision in one line; don't deliberate out loud each time.

**Every subagent prompt carries:** the item identifier + a relevant excerpt of the spec (or the
plan file path + line range), any known plan-vs-reality deviations, explicit commit/output
instructions, and a tight report format: *"Report in under ~150 words: what changed, where, and
any surprises."* A subagent's final message is data for you, not a message to the user — relay
what matters.

### When to reach for a multi-agent workflow

For large, structured work — comprehensive audits, broad migrations, research that needs many
independent sources, or anything where you want independent perspectives to cross-check before
committing — a deterministic multi-agent workflow (fan-out → verify → synthesize) beats one
linear pass. Use it when the operator has opted into that scale, or when the task genuinely
can't fit one context. For everyday tasks, a single subagent or the main thread is right —
don't spin up a fleet for a small job (Rule 10: keep the surface small).

### Tool & MCP discipline

- **Scope every query.** Listing/search tools with loose filters can return tens of thousands
  of tokens. Always filter tightly (by project, state, date, type) and ask for the minimum you
  need. Never call a raw "show me everything" endpoint to browse.
- **Parse large results out-of-band.** When a tool result is huge, save it and parse the file
  (e.g. with `jq`/`grep`) rather than re-calling the tool with looser filters.
- **Prefer the dedicated tool over a shell hack** when one fits (file read/edit/search tools
  over `cat`/`sed`/`awk`). It's faster and clearer for the human watching.
- **Fetch docs, don't guess.** For any library/framework/API/CLI question, pull current docs
  (a docs-fetch tool or official site) rather than relying on memory — your training data may
  be stale. This is cheaper than shipping a wrong API call and debugging it.
- **A denied tool call is a signal.** If the operator's permission mode declines a call, adjust
  — don't retry the same thing verbatim.

### Failure recovery — break the loop

Repeated identical failure is a signal to **stop**, not to try harder. If the same action fails
about twice the same way — a tool erroring identically, a test failing on the same line, a fix
that doesn't land — do not fire a third blind attempt. Re-diagnose first: the approach is wrong,
not unlucky. Blind retries burn the context window and rarely converge (they're how one auth bug
became four fix-on-fix commits). Cap the flailing: when you've spent more turns thrashing than the
task is worth, surface the blocker — what you tried, what you observed, your best hypothesis — and
escalate or ask, rather than looping in silence. Where a runtime can enforce this (a tool-error or
turn cap, a circuit-breaker), prefer the deterministic limit over willpower.
