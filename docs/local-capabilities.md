# Local capability selection

Install previews disclose file changes, process control, network/model egress, context injection,
and persistent records for each selected capability. Explicit `--with-*` flags select capabilities;
`--dry-run` shows their effects without activating them. Existing selections remain durable on reruns.

Installation state records selected capabilities and their effect versions. Update plans carry
these records in `installation.effects`; rollback restores the saved state. Expanded effects require
an explicitly reviewed install selection before update. Legacy installations retain their existing
choices. New capabilities are disabled until explicitly selected.

Doctor reports recorded selections and effects. Uninstall removes owned registration while retaining
project scaffolding and foreign configuration. Local runtime files are inert without registration;
AgentSmith provides no automatically discovered plugin entrypoint.
