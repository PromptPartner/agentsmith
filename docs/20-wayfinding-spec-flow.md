# Wayfinding — from a foggy idea to an accepted spec

Use Wayfinder when you know the destination but cannot yet write a decision-complete plan. It keeps
planning work auditable without turning the tracker into a premature implementation backlog.

Invoke `/wayfinder` in Claude Code or `$wayfinder` in Codex. The skill creates a living draft under
`docs/specs/` from [`templates/wayfinder-spec.md`](../templates/wayfinder-spec.md). Repository storage
makes the reasoning available to both runtimes and future sessions; the tracker remains the record
of who owns each decision.

## The flow

1. **Chart:** define the destination and non-goals; map sharp decisions and their dependencies;
   leave unshaped, in-scope uncertainty as fog.
2. **Advance:** resolve one frontier decision per session. Record the detail once in its ticket or
   durable artifact and keep only its linked gist in the decision index.
3. **Terminal draft:** clear every blocking decision and either resolve or explicitly defer
   non-blocking fog. Split the resulting work into independent implementation-ticket drafts.
4. **Accept:** the operator explicitly accepts the spec. Only then does its status become
   `accepted`, with `accepted_by` and `accepted_at` recorded; the decision ticket can close and
   implementation becomes eligible to start.
5. **Implement separately:** each build or delivery unit gets its own implementation ticket. The
   accepted spec is its contract, not its ticket identity.

Acceptance is a decision, not a formatting convention: an agent cannot accept its own draft.
Likewise, a Linear connection is not consent. With the default ask-first policy, Wayfinder leaves
paste-ready decision tickets, implementation tickets, and closing comments for the operator to
post. See [`14-project-tracker-guide.md`](14-project-tracker-guide.md).

## What terminal means

An accepted spec has no unresolved question that an implementer must answer. Its evidence names
the observable end state, its decisions link to their rationale, and each implementation ticket can
be executed without inheriting hidden choices from the decision phase. Explicit deferrals are
allowed only when they do not block the destination and name where the deferred work will live.

Wayfinder is work-type-neutral: a destination can be code, a campaign, a research conclusion, or a
document. It plans; the active work profile still defines what implementation and verification mean.
