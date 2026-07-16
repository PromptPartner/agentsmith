# How to pick a profile

A profile tailors the universal core to a kind of work — it defines what "done" and "verified"
mean, the quality gates, and the failure modes to guard against. You assemble `CLAUDE.md` from
the core plus one (or a few) profiles.

## The nine profiles

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
| `autonomous-loops` | work that lands with no human checking it first — scheduled/cron agents, `/loop` runs, long unattended orchestrations |

**See one filled in.** Five of these profiles have a complete worked project under
[`../examples/`](../examples/README.md) — `software-dev` (a FastAPI service, with a bundled skill),
`document-creation` (a docs site), `data-crunching` (a churn analysis), `devops-setup` (a VPS app
server), and `marketing-outreach` (a newsletter). Read the one nearest your work to see the end
state — a filled `CLAUDE.md` project-specifics layer and a real `.harness/verify.conf`.

## Choosing

- **One main profile** is the norm. Pick the one that matches the bulk of the project's work.
- **Mixed projects** are common and supported — assemble several:
  `./setup.sh --profile devops-setup,software-dev`
  A project that ships a service *and* its install scripts wants both. A consultancy deliverable
  that's a researched report wants `deep-research,document-creation`.
- **`autonomous-loops` stacks, it doesn't replace.** It's a *modifier*: it says how the work is
  supervised, not what the work is. A loop that fixes code wants `software-dev,autonomous-loops`;
  one that sweeps a server wants `devops-setup,autonomous-loops`. Add it the moment the output
  stops passing under a human's eyes, and drop it when you go back to watching each step.
- **When in doubt**, `general-admin` is the safe catch-all — it assumes outward-facing/irreversible
  actions need confirmation and that summaries must be faithful.
- You can **re-assemble any time** as a project's focus shifts: re-run `setup.sh --assemble-only`
  with a different `--profile` list. It only rewrites the managed `CLAUDE.md` block.

## Layered: global core + per-project profile

If you work across several projects, install the universal **core** once globally and let each
project carry only its **profile**:

```bash
./setup.sh --global --operator-name "You"                                   # core → ~/.claude/CLAUDE.md
./setup.sh --profile software-dev --profile-only --target /path/to/project  # profile only
```

Claude Code loads the global `~/.claude/CLAUDE.md` *and* the project `./CLAUDE.md` together, so
the rules apply everywhere and each repo stays thin. Without `--global`, a per-project run writes
a **self-contained** core+profile file (good for one-offs). See `docs/12-platforms-and-tools.md`.

## Order matters slightly

When you list several profiles, list the **dominant** one first — its quality gates read first.
Stacking is additive: the stricter rule always wins, so combining profiles never *loosens* the
bar, it only adds gates.
