# Specs

Wayfinder keeps living decision maps and terminal specs here. Start from
[`templates/wayfinder-spec.md`](../../templates/wayfinder-spec.md); initial status is `draft`, and
only explicit operator acceptance advances it to `accepted` and fills `accepted_by` / `accepted_at`.

A spec from the current template declares `schema: 2` and must name its `research` note, its
`route` with a reason, and its `reviewer_receipt`. Commit the research note and the review
verdict: a run's worktree holds only what Git holds, so `check-specs` requires them to be tracked
and `autonomous-run` requires them in the run's base commit. `python3 .agentsmith/autonomous-run.py
check-specs` fails while an accepted schema-2 spec lacks one of them or points at a missing
file, and `autonomous-run` refuses such a spec. Only a spec with no `schema` key at all counts
as accepted before these fields existed and is not checked; any other schema value, a blank one
included, is refused, and so is a front matter key that appears twice.

A schema-2 spec must also be testable. Its body needs at least one list item under each of
`## Acceptance and evidence` (the acceptance criteria), `## Edge cases` and `## Non-goals` (what
is out of scope); a section that is missing, holds only prose, or holds only a template
placeholder such as `- <...>` counts as absent. An optional `## Assumptions` section records what
the spec takes for granted about the code. A list item that opens with a backticked reference is
checked against Git: `` `path` `` must exist (file or folder), and `` `path::symbol` `` must name a
file in which the symbol occurs as a whole word. `prepare` and `start` check these at the run's
`base_ref` and refuse a "stale assumption" by name; `check-specs` checks them against what Git
tracks. Any other list item is prose and is not checked. Specs without a `schema` key are still
not checked.

An optional `## Demo` section declares one command that shows the changed behaviour, in the first
fenced code block under the heading. At acceptance the run's controller records a transcript of it
in the verifier sandbox, and the pull-request body links it; see
[replayable demo evidence](../21-autonomous-runs.md#replayable-demo-evidence). A `## Demo` heading
with no fenced command is refused.

The spec records decisions. Implementation proceeds through new, separately scoped tracker items;
the active tracker-write consent policy governs creating, commenting on, or closing those items.

This directory is a format guide. A project's own specs belong in its repository or private
tracker, according to that project's visibility rules. AgentSmith does not ship its internal
planning records here.
