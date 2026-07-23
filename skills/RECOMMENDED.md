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

## Security skills — where they come from
Every security skill named below ships in the opt-in **`security` pack**
(`./setup.sh --with-plugins security`), which installs two things: Anthropic's first-party
**`claude-security`** and **`cybersecurity-skills`** ([briiirussell](https://github.com/briiirussell/cybersecurity-skills),
MIT — 29 specialist workflows). The catalog is **registered, not vendored**: upstream maintains it,
updates arrive free, and the harness owns none of it (R10). It installs as one plugin carrying all
29 skills — no per-skill install, which costs nothing since skills load on demand by description.

## software-dev
<!-- MAP software-dev | packs: dev-workflow,stack-lsp,security | skills: test-driven-development,using-git-worktrees,code-review,ui-ux-pro-max,owasp-audit,dependency-audit -->
- **test-driven-development**, **using-git-worktrees** — `superpowers`.
- the `code-review` skill + the **codex** two-AI gate (plugins) for review.
- language LSP / dev plugins (stack-lsp pack) for navigation + fixes.
- **Design system (any front end):** a UI project's look is defined in a root `DESIGN.md` the agent
  reads before every UI change — set it up with `./setup.sh --design-system stub|catalog:<brand>|generate`
  (and `--with-ui-design-hook` for a nudge on UI edits). Two ways to fill it:
  - **awesome-design-md** — a catalog of 50+ ready-made `DESIGN.md` files
    ([VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)); drop one in and adapt it.
  - **ui-ux-pro-max** — third-party (MIT); generates AND persists a full design system (palette, type,
    layout, components) into `DESIGN.md`. Only if the work has a front end; skip it for backend, CLI, or
    library work. Needs **Python 3**, which nothing else here does. Install commands under `creative-design` below.
- **rtk** — token-compressing CLI proxy (Apache-2.0), **auto-installed for this profile** (pass
  `--no-rtk` to skip). Cuts `git`/test/build output 60–90% before it hits the context window. It's
  a binary + hook, not a plugin — details in `../config/plugins.md`.
- **Security (the `security` pack — `./setup.sh --with-plugins security`):** the profile's quality
  gates now ask for a security pass and a CVE check on every change. These are what you reach for
  when the answer isn't obvious:
  - **`threat-modeling`** — *before* you build anything auth-, money-, or PII-adjacent. The
    cheapest security work there is, because it's the only kind that happens pre-code.
  - **`owasp-audit`** — the workhorse source review (access control, injection, crypto, SSRF).
  - **`api-audit`** for REST/GraphQL/RPC surfaces; **`dependency-audit`** when the mechanical
    `deps` verify phase flags something and you need to judge real exploitability.
  - **`prompt-injection`** — only if the product has LLM features, and then not optional.
  - **`claude-security`** for a full pass on a risky diff: it verifies each finding independently
    before reporting, which is the difference between a review and a list of guesses.

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
<!-- MAP devops-setup | packs: security | skills: container-audit,cloud-audit,iam-audit -->
- Leans on **MCP servers** (cloud/CI/registry) and the **sentry-cli** skill for post-deploy
  monitoring more than on bundled skills. Add a skill when you find yourself repeating a runbook.
- **rtk** — token-compressing CLI proxy (Apache-2.0), **auto-installed for this profile** (pass
  `--no-rtk` to skip): compresses noisy `kubectl`/`terraform`/`docker`/test output before the agent
  reads it. Binary + hook, not a plugin — see `../config/plugins.md`.
- **Security (the `security` pack):** **`container-audit`** (Docker/K8s), **`cloud-audit`**
  (AWS/GCP/Azure misconfiguration), **`iam-audit`** (least-privilege roles). These cover the two
  quality gates this profile added — exposed surface and workload identity — where the answer needs
  more than a checklist. The permissive default is the usual finding, not a bug in your code.

## security-audit
<!-- MAP security-audit | packs: security | skills: owasp-audit,threat-modeling,finding-triage,security-comms -->
The `security` pack **is** this profile's toolset — install it (`--with-plugins security`) rather
than working from memory. Match the skill to the engagement:
- **Design/pre-code:** `threat-modeling` (STRIDE, abuse cases).
- **Source & API:** `owasp-audit`, `api-audit`, `crypto-audit`, `secrets-audit`,
  `prompt-injection` (LLM features), `mobile-audit`.
- **Infra & identity:** `cloud-audit`, `container-audit`, `iam-audit`.
- **Supply chain:** `dependency-audit`, `vuln-research`.
- **Live testing** (only inside written scope — see the profile's authorization rule): `recon`,
  `osint-recon`, `web-pentest`, `red-team-engagement`.
- **Blue team / IR:** `incident-triage`, `threat-hunting`, `siem-detection`, `disk-forensics`,
  `soc-operations`, `breach-patterns`.
- **Compliance:** `hipaa-audit`, `pci-audit`, `privacy-engineering`, `csf-mapping`,
  `ai-risk-management`.
- **Delivery — don't skip these:** `finding-triage` (disposition per finding) and `security-comms`
  (the same finding framed for an engineer vs. an exec). They're what turn a findings list into
  something that gets acted on.
- **`claude-security`** as the independent verification pass over your own findings — have it try
  to *refute* each one. Same job the `codex` two-AI gate does for a diff.

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
