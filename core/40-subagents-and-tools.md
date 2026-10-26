<!-- CORE · subagents, parallelism, tool discipline · universal -->
## Subagents, Parallelism, and Tool Discipline

**Subagents.** Dispatch self-contained work with a clear spec and no live-system interaction;
keep work that crosses concerns, needs live verification, or needs judgment about where something
belongs on the main thread. Launch independent tasks that share no files in parallel. **Every
subagent prompt carries:** the item identifier plus the relevant spec excerpt (or plan file path
and line range), known plan-vs-reality deviations, explicit commit/output instructions, and a tight
report format (*"Report in under ~150 words: what changed, where, and any surprises."*). A
subagent's final message is data for you, not a message to the user — relay what matters. Use a
multi-agent workflow only when the operator has opted into that scale.

**Tool & MCP discipline.**
- **Scope every query.** Listing/search tools with loose filters can return tens of thousands of
  tokens. Filter tightly (project, state, date, type), ask for the minimum, and parse a huge
  result from a saved file (`jq`/`grep`) instead of re-calling with looser filters.
- **A denied tool call is a signal.** If the operator's permission mode declines a call, adjust
  — don't retry the same thing verbatim.

### Failure recovery — break the loop

Repeated identical failure is a signal to **stop**, not to try harder. If the same action fails
about twice the same way — a tool erroring identically, a test failing on the same line, a fix
that doesn't land — do not fire a third blind attempt. Re-diagnose first: the approach is wrong,
not unlucky. When you've spent more turns thrashing than the task is worth, surface the blocker —
what you tried, what you observed, your best hypothesis — and escalate or ask, rather than looping
in silence. Where a runtime can enforce this (a tool-error or turn cap, a circuit-breaker), prefer
the deterministic limit over willpower.
