# Specs

Wayfinder keeps living decision maps and terminal specs here. Start from
[`templates/wayfinder-spec.md`](../../templates/wayfinder-spec.md); initial status is `draft`, and
only explicit operator acceptance advances it to `accepted` and fills `accepted_by` / `accepted_at`.

A spec from the current template declares `schema: 2` and must name its `research` note, its
`route` with a reason, and its `reviewer_receipt`. `python3 .agentsmith/autonomous-run.py
check-specs` fails while an accepted schema-2 spec lacks one of them or points at a missing
file, and `autonomous-run` refuses such a spec. A spec without `schema:` was accepted before
these fields existed and is not checked.

The spec records decisions. Implementation proceeds through new, separately scoped tracker items;
the active tracker-write consent policy governs creating, commenting on, or closing those items.

This directory is a format guide. A project's own specs belong in its repository or private
tracker, according to that project's visibility rules. AgentSmith does not ship its internal
planning records here.
