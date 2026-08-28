# Updating existing AgentSmith installations

This runbook is for installations created before AgentSmith included its staged updater. The first
update is a bootstrap: run the updater from a temporary checkout of a stable release, point it at
the existing installation, and keep planning separate from applying.

## Current release and known blocker

The current stable release is `v0.2.1`, commit
`b838a77f1647cc6589009e8269c1e610a1a796a4`.

**Do not apply `v0.2.1` to a pre-manifest, Claude-only installation when skills exist only under
`~/.claude/skills` or its user-scope MCP configuration exists only in `~/.claude.json`.** In that legacy shape,
`update plan --global` can incorrectly reconstruct `skills: false` and `mcp: []`, produce no skill
changes, and report success. The post-update skill check is then skipped because it trusts the same
false capability value.

The defect is recorded in
[`feedback/0020-legacy-claude-reconstruction-skipped-skills-and-mcp.md`](feedback/0020-legacy-claude-reconstruction-skipped-skills-and-mcp.md).
Wait for a fixed release before updating that installation shape. Do not compensate by manually
editing the authenticated plan.

## Before updating

Make the installation's current state recoverable. For a project installation, commit or otherwise
back up local work and start from a clean working tree. This makes the updater's changes easy to
review and keeps locally evolved rules visible.

The preservation boundary is:

- content outside AgentSmith-managed instruction markers remains in place;
- customized installed skills are retained;
- research, source material, and unowned configuration are not deletion targets;
- edits inside AgentSmith-managed instruction blocks are regenerated and can be replaced.

Move any intentional edits inside a managed block into the appropriate source `core/` or `profiles/`
file, or preserve them separately, before applying an update.

## Bootstrap the updater once per machine

The temporary checkout does not change an installation. It supplies the new updater to an old
installation that does not have one yet.

```bash
AGENTSMITH_BOOTSTRAP_DIR="$(mktemp -d)"

git clone --depth 1 --branch v0.2.1 \
  https://github.com/PromptPartner/agentsmith.git \
  "$AGENTSMITH_BOOTSTRAP_DIR"

git -C "$AGENTSMITH_BOOTSTRAP_DIR" rev-parse HEAD
```

For `v0.2.1`, the final command must print:

```text
b838a77f1647cc6589009e8269c1e610a1a796a4
```

## Update one project installation

Use a unique plan filename for every installation. Planning reads and stages the proposed release,
but does not modify the target.

```bash
AGENTSMITH_TARGET="/absolute/path/to/project"
AGENTSMITH_PLAN="/tmp/agentsmith-project-name-v0.2.1-plan.json"

git -C "$AGENTSMITH_TARGET" status --short

python3 "$AGENTSMITH_BOOTSTRAP_DIR/agentsmith.py" update plan \
  --target "$AGENTSMITH_TARGET" \
  --version v0.2.1 \
  --save "$AGENTSMITH_PLAN"

python3 -m json.tool "$AGENTSMITH_PLAN" | less
```

Inspect `migration_warnings`, `installation.capabilities`, and `proposed_changes`. Stop if a
capability reported by `doctor` disappears from the reconstructed installation. Press `q` to leave
`less`.

Applying is the state-changing approval boundary. Run it only after approving that exact plan:

```bash
python3 "$AGENTSMITH_BOOTSTRAP_DIR/agentsmith.py" update apply \
  --plan "$AGENTSMITH_PLAN"
```

Apply prints the path to a machine-local rollback receipt. Keep it until the update is accepted,
then inspect and verify the installed result:

```bash
git -C "$AGENTSMITH_TARGET" diff

python3 "$AGENTSMITH_TARGET/.agentsmith/agentsmith.py" doctor \
  --agent all \
  --target "$AGENTSMITH_TARGET" \
  --strict
```

## Update a global installation

Global scope is separate from every project scope. Create and inspect its own plan:

```bash
AGENTSMITH_PLAN="/tmp/agentsmith-global-v0.2.1-plan.json"

python3 "$AGENTSMITH_BOOTSTRAP_DIR/agentsmith.py" update plan \
  --global \
  --version v0.2.1 \
  --save "$AGENTSMITH_PLAN"

python3 -m json.tool "$AGENTSMITH_PLAN" | less
```

Do not apply this plan if the legacy Claude-only blocker above matches the installation. Otherwise,
after approving the plan:

```bash
python3 "$AGENTSMITH_BOOTSTRAP_DIR/agentsmith.py" update apply \
  --plan "$AGENTSMITH_PLAN"
```

## Roll back

Rollback restores the exact pre-update bytes recorded during apply. It refuses to overwrite files
that changed again after the update.

```bash
python3 "$AGENTSMITH_BOOTSTRAP_DIR/agentsmith.py" update rollback \
  --receipt "/path/printed/by/update-apply.json"
```

Plans and receipts are authenticated with the local account's
`~/.agentsmith/update-integrity.key`. Do not edit a plan or receipt, and do not copy one between
machines. Repeat plan, inspection, and apply separately for every installation.
