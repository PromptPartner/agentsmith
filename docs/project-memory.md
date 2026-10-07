# Local project memory

AgentSmith recalls existing Markdown. It adds no database, embedding service,
model call or dependency. Orca remains the control UI. Recall is evidence to
review; it never changes an accepted spec, grants permission, proves completion,
executes a saved command or resumes work automatically.

## Manual recall

```sh
agentsmith memory search "startup hooks"
agentsmith memory search "startup hooks" --json
agentsmith memory read docs/research/startup-hooks.md
agentsmith memory read docs/research/startup-hooks.md --json
```

Search covers `.harness/handoffs`, `docs/research` and `docs/feedback`. Archives,
captured sources and artifact directories are excluded. Directory names containing
`source`, `sources`, `artifact`,
`artifacts` or `captured` as a hyphen/underscore-separated segment are captures
(for example `ecc-nasiko-sources-2026-10-06`) and excluded too. Markdown stays the
source of truth. Search uses Unicode-aware lexical matching and returns up to
50 references ordered by relevance, with relative path, title and SHA-256 of
the original file bytes. An empty query returns no matches. A truncated result
list is marked; narrow the query to inspect further matches.

Search and startup discovery inspect at most 500 documents, read at most
128 KiB per document and check a two-second time budget between local filesystem
operations. The native hook runs selection and discovery in a subprocess with a two-second wall-clock watchdog; timeout produces a diagnostic and continues the session. Manual CLI filesystem calls cannot be preempted. Incomplete
inspection, unreadable files, invalid metadata and symlinks produce diagnostics;
an incomplete search never means there are no matching documents elsewhere.
Reports retain at most 20 detailed diagnostics, with an omitted count when more
occur. Details are bounded before redaction; startup also checks its time budget
while redacting and rendering references.

Read accepts a relative POSIX `.md` path inside these roots. It rejects parent
traversal, excluded directories, symlinks (including project ancestors), nonregular
files, invalid UTF-8 and oversized files. Files are opened through directory
descriptors with no-follow flags, so replacing an ancestor with a symlink cannot
redirect a read. Platforms without safe no-follow access report recall unavailable.
Use the canonical project directory rather than a symlink alias.

Both reports redact secret-shaped values using AgentSmith's existing detector,
and remove terminal control characters. Redaction is heuristic, so keep secrets
out of Markdown. JSON reports have `schema_version: 1`, `operation`, `complete`
and `diagnostics`. Search adds `documents_inspected`, `documents_attempted`,
`matches` and `results_truncated`; read adds the redacted `content`. A hash describes
the original bytes, not the redacted display.

## Optional metadata

Existing notes work without edits. A note can include this JSON comment:

```markdown
<!-- agentsmith-memory: {"version":1,"branch":"feature/recall","status":"open","commit":"abcdef1","links":["docs/research/startup-hooks.md"]} -->
# Handoff — startup recall
```

Supported fields are `version` (currently `1`), `branch`, `commit`, `status`,
`superseded_by` and `links`. Links are relative paths, or objects containing
`path` and an optional SHA-256 `content_hash`. Unknown metadata fields are ignored.
Invalid supported fields or unsupported versions make inspection incomplete.
The version must be the integer `1`; JSON booleans and duplicate metadata keys
are rejected, including conflicting status or branch declarations.
`superseded_by`, or status `superseded`/`archived`, excludes a note from suggestions
and search results. Startup also excludes `closed`/`completed` handoffs.

The existing handoff line `**Branch / version:** feature/recall abcdef1` supplies
an explicit branch and optional commit when JSON metadata is absent. A passing
branch mention in ordinary prose does not establish applicability.
The CLI scaffold's `**Branch:** feature/recall   **HEAD:** abcdef1` is also
recognized. Windows currently lacks the required safe no-follow operations and
reports this capability unsupported rather than falling back to unsafe reads.

## Optional startup references

Select `--with-memory-startup` in a reviewed install preview. Disable it with
`--without-memory-startup`. Updates retain the selection; they never add it.
Project hooks use `.claude/settings.json` and `.codex/hooks.json`; user-wide
hooks use native user settings. A project choice overrides user-wide recall,
so simultaneous native registrations produce one set of references. Existing installations have it disabled until selected. Its
SessionStart handler runs for startup and resume, never compaction. It reads
local documents and supplies references to the selected native agent. AgentSmith
adds no separate export; the agent's existing provider connection processes its
context.

Startup selects the newest applicable handoff for the current branch, followed
by up to two research or feedback documents it links to. Ordinary Markdown links
to `docs/research/...` or `docs/feedback/...` work too. With no applicable handoff,
it emits no references. Startup output is at most three references and 2,000
characters, containing paths, titles and hashes, with commit drift, stale link
hash and incomplete retrieval warnings where relevant. It includes no document
bodies. Failure produces a short advisory diagnostic and lets the session continue.
Paths are rendered in full. References that cannot fit the display budget or
whose path changes during redaction are omitted with a warning; reported references
match the displayed set. Space is reserved for incomplete/drift warnings, and
accepted specs remain authoritative.

Native Claude/Codex registration is necessary but does not prove Orca delivery.
Observe a real Orca native-client startup and resume before marking that host
supported. If Orca suppresses SessionStart output, use manual CLI recall and
record startup suggestions as unsupported there; no undocumented workaround is
part of this capability.

## Attribution

This original local Markdown retrieval implementation was inspired by memory
workflow ideas in [Everything Claude Code](https://github.com/affaan-m/everything-claude-code)
(MIT). It imports no ECC implementation, service or package.
