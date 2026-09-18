# How to pick a profile

If this is your first project, do not pick from names alone. Run
`agentsmith profiles recommend --target .`, inspect the evidence behind the ranking, and preview a
switch before applying it. The [First Verified Loop proof](demos/first-verified-loop/README.md)
shows where profile selection sits in the larger status → checks → evidence → handoff journey.

A profile tailors the universal core to a kind of work — it defines what "done" and "verified"
mean, the quality gates, and the failure modes to guard against. You assemble the selected native
rule file (`CLAUDE.md`, `AGENTS.md`, or both) from the core plus one (or a few) profiles.

Inspect the available profiles or get a deterministic recommendation without changing the project:

```bash
agentsmith profiles list
agentsmith profiles recommend --target /path/to/project
```

For an existing project installation, preview a switch before applying it:

```bash
agentsmith profiles switch --target /path/to/project --profile software-dev --dry-run
agentsmith profiles switch --target /path/to/project --profile software-dev
```

The switch changes only AgentSmith-managed instruction blocks and the existing installation
manifest. It backs up changed instruction files, preserves foreign text and the exact verification
configuration, and reports verification gates the new profile does not yet represent.

## The ten profiles

| Profile | Use it when the work is… |
|---|---|
| `software-dev` | code that builds, runs, and is tested — features, fixes, refactors, libraries, services |
| `devops-setup` | provisioning, installers, Docker/compose, configs, firewalls, deploys, CI, sysadmin |
| `marketing-outreach` | email, sequences, newsletters, landing copy, social, campaigns, list/CRM ops |
| `document-creation` | reports, proposals, specs, manuals, contracts, wikis, long-form writing |
| `data-crunching` | cleaning/transforming/joining/aggregating data, analysis, metrics, ETL, SQL |
| `general-admin` | inbox/triage, scheduling, file org, summarizing, light coordination, routine ops |
| `deep-research` | multi-source investigations, competitive/market analysis, due diligence, cited reports |
| `creative-design` | diagrams, slide decks, brand/visual artifacts, generated images/video |
| `security-audit` | security *is* the deliverable — code audits, pentests, threat models, cloud/IAM reviews, incident investigations, compliance assessments |
| `autonomous-loops` | work that lands with no human checking it first — scheduled/cron agents, `/loop` runs, long unattended orchestrations |

**See one filled in.** [`../examples/`](../examples/README.md) has six complete worked projects
across five profiles — `software-dev` (two: a FastAPI service *and* a React component library, each
bundling a skill), `document-creation` (a docs site), `data-crunching` (a churn analysis),
`devops-setup` (a VPS app server), and `marketing-outreach` (a newsletter). Read the one nearest
your work to see the end state — a filled `CLAUDE.md` project-specifics layer and a real
`.harness/verify.conf`.

## Choosing

- **One main profile** is the norm. Pick the one that matches the bulk of the project's work.
- **Mixed projects** are common and supported — assemble several:
  `./setup.sh --platform codex --profile devops-setup,software-dev`
  A project that ships a service *and* its install scripts wants both. A consultancy deliverable
  that's a researched report wants `deep-research,document-creation`.
- **`autonomous-loops` stacks, it doesn't replace.** It's a *modifier*: it says how the work is
  supervised, not what the work is. A loop that fixes code wants `software-dev,autonomous-loops`;
  one that sweeps a server wants `devops-setup,autonomous-loops`. Add it the moment the output
  stops passing under a human's eyes, and drop it when you go back to watching each step.
- **Product UI is `software-dev`.** A web/app frontend lives under `software-dev` — not
  `creative-design`, which is diagrams, decks, and brand artifacts. UI projects expect a root
  `DESIGN.md`: the design system the agent reads before building any screen. Establish it at install
  (`./setup.sh --design-system stub|catalog:<brand>|generate`) or drop one in from the
  [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) catalog, so the UI isn't built
  ad-hoc and off-brand. See it worked out end to end in
  [`../examples/ui-component-library/`](../examples/ui-component-library/README.md).
- **Security as a *gate* is not `security-audit`.** A feature that touches auth, handles user
  input, or adds a dependency is still `software-dev` — its quality gates already carry a security
  pass and a CVE check. Reach for `security-audit` only when the deliverable is a *finding* rather
  than a ship: an audit, a pentest, a threat model, an incident write-up.
- **Auditing a codebase you also build? Switch, don't stack.** These two are the largest
  profiles, and `software-dev,security-audit` exceeds the leanness budget, which is
  the signal that you're asking the agent to hold two full rule sets it won't use at once. Switch
  to `security-audit` for the audit and back to `software-dev` for implementation. The profile
  switch measures both line and token budgets before its first write; do not rely on a historical
  line count because the core evolves.
- **When in doubt**, `general-admin` is the safe catch-all — it assumes outward-facing/irreversible
  actions need confirmation and that summaries must be faithful.
- You can **switch any time** as an installed project's focus shifts. Use `profiles switch` so the
  existing ownership manifest, adapters, operator identity, tracker policy, and foreign content
  remain authoritative. Use a fresh `install` only when changing installation capabilities.

## Layered: global core + per-project profile

If you work across several projects, install the universal **core** once globally and let each
project carry only its **profile**:

```bash
./setup.sh --platform both --global --operator-name "You"                   # native global core for both
./setup.sh --platform both --profile software-dev --profile-only --target /path/to/project
```

Claude loads `~/.claude/CLAUDE.md` + `./CLAUDE.md`; Codex loads `$CODEX_HOME/AGENTS.md` +
`./AGENTS.md` (`CODEX_HOME` defaults to `~/.codex`). The rules apply everywhere and each repo stays
thin. Without `--global`, a per-project run writes a **self-contained** core+profile file (good for
one-offs). See `docs/13-platforms-and-tools.md`.

## Order matters slightly

When you list several profiles, list the **dominant** one first — its quality gates read first.
Stacking is additive: the stricter rule always wins, so combining profiles never *loosens* the
bar, it only adds gates.
