# Recommended skills (by profile)

Two sources of skills: the **bundled harness pack** (ships in this repo, installed with
`--with-skills`) and **plugins** (installing the plugin gives you its skills — no separate
download). Install plugins with `./setup.sh --with-plugins ...` or `/plugin install`. A few skills
are built into Claude Code. Keep the set tight (R10) — add per need.

The `<!-- MAP ... -->` line under each profile is machine-readable: the setup wizard parses it to
recommend packs and skills for the profile you pick. Edit the prose and the MAP line together —
they're the single source of truth.

## Bundled with the harness (install with `--with-skills`)
Six small, self-contained, work-type-neutral skills — they prefer a project-local `scripts/<x>.sh`
when present, else run an inline procedure, so they work globally, in a harness project, or in a
bare repo:
- **handoff** — wrap up a session: durable note + paste-ready kickoff block (`/handoff`).
- **verify** — "is this shippable?" with evidence, never a bare "should pass" (`/verify`).
- **harness-doctor** — is this project's harness installed correctly and lean? (`/harness-doctor`).
- **harness-help** — orient a non-coder: your profile, rules, safety mode, what to type next.
- **new-research** — scaffold a durable `docs/research/` source note (R9).
- **new-feedback** — scaffold a numbered `docs/feedback/` post-incident (the System-Evolution loop).

Project mode installs these into `<project>/.claude/skills/`; `--global` installs them into
`~/.claude/skills/`.

## Universal (worth having everywhere)
- **brainstorming**, **writing-plans**, **executing-plans** — from `superpowers`. Plan before you build.
- **systematic-debugging** — from `superpowers`. Find the cause before patching.
- **verification-before-completion** — from `superpowers`. Evidence before "done".
- **requesting-code-review** / **receiving-code-review** — from `superpowers`.
- **mem-search**, **make-plan**, **learn-codebase** — from `claude-mem`. Memory + planning.
- **deep-research** — built in. The engine for the deep-research profile.

## software-dev
<!-- MAP software-dev | packs: dev-workflow,stack-lsp | skills: test-driven-development,using-git-worktrees,code-review,ui-ux-pro-max -->
- **test-driven-development**, **using-git-worktrees** — `superpowers`.
- the `code-review` skill + the **codex** two-AI gate (plugins) for review.
- language LSP / dev plugins (stack-lsp pack) for navigation + fixes.
- **ui-ux-pro-max** — third-party (MIT). Only if the work has a front end; skip it for backend,
  CLI, or library work. Needs **Python 3**, which nothing else here does. See `creative-design`
  below for the install commands.

## deep-research
<!-- MAP deep-research | packs: - | skills: deep-research -->
- **deep-research** (built in) — the primary tool: fan-out search, fetch, adversarial verify, cited synthesis.
- a docs-fetch tool (Context7) for pinning technical claims to current docs.

## creative-design
<!-- MAP creative-design | packs: - | skills: excalidraw-diagram,ui-ux-pro-max -->
- **excalidraw-diagram** — built in. Clean diagrams. (Pairs with the excalidraw MCP — see
  `../config/mcp.example.json`.)
- **ui-ux-pro-max** — third-party (MIT), for real interface work: design systems, colour/type
  pairing, layout rules. Not bundled here and deliberately so — it needs **Python 3**, which
  nothing else in this harness does, and it is only useful if you are actually designing a UI.
  Install it yourself when you want it:
  `/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill` then
  `/plugin install ui-ux-pro-max@ui-ux-pro-max-skill`.
- a slide/deck skill if your build ships one (e.g. a "document → deck" skill).

## document-creation
<!-- MAP document-creation | packs: - | skills: deep-research -->
- **deep-research** (built in) for source-grounded reports.
- a docs-fetch tool (Context7) for grounding — see `../config/mcp.example.json`.

## devops-setup
<!-- MAP devops-setup | packs: - | skills: - -->
- Leans on **MCP servers** (cloud/CI/registry) and the **sentry-cli** skill for post-deploy
  monitoring more than on bundled skills. Add a skill when you find yourself repeating a runbook.

## autonomous-loops
<!-- MAP autonomous-loops | packs: - | skills: using-git-worktrees,verify -->
- **using-git-worktrees** — one isolated worktree per fix attempt; discard it on reject.
- **verify** — what the *checker* actually runs. The check must be one the maker can't fake.
- Otherwise deliberately bare: the scheduler (`/loop`, `/schedule`, cron) and the maker/checker
  subagent split are native. Resist bolting on a loop framework — the rules are the product (R10).

## marketing-outreach / general-admin / data-crunching
<!-- MAP marketing-outreach | packs: - | skills: - -->
<!-- MAP general-admin | packs: - | skills: - -->
<!-- MAP data-crunching | packs: - | skills: - -->
- These lean on **MCP servers** (ESP/CRM, email/calendar, storage, DB) more than on skills —
  see `../config/mcp.example.json`. Add a skill when you find yourself repeating a workflow.

## Add your own
Drop a folder in `skills/` here (see `README.md` for structure), then `./setup.sh --with-skills`.
Your own brand-specific skills (e.g. a brand-specific diagram skill) are intentionally NOT bundled —
copy a scrubbed version in yourself if you want them on a new machine.
