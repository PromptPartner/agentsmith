# Plugins, Marketplaces & Skills — what to install and why

Plugins and skills are **dynamic context**: the agent loads them on demand, so they cost no
tokens until they're needed. That's why it's safe to install the universal set everywhere and
add stack-specific ones only where they apply. `setup.sh` installs the **universal** set for
you; the **by-profile** sets are opt-in.

## Marketplaces

`setup.sh` registers these (idempotent — re-running is safe):

| Marketplace | Source (GitHub) | Provides |
|---|---|---|
| `claude-plugins-official` | `anthropics/claude-plugins-official` | superpowers, code-review, LSPs, frontend-design, … (built-in) |
| `thedotmack` | `thedotmack/claude-mem` | claude-mem (persistent memory) |
| `openai-codex` | `openai/codex-plugin-cc` | codex (second-AI adversarial review + test gate) |

Add a marketplace manually with: `/plugin marketplace add <owner>/<repo>` (in Claude Code), or
let `setup.sh` do it.

## Universal plugins (installed by default — every profile benefits)

| Plugin | Why it's universal |
|---|---|
| **superpowers** | The workflow backbone: brainstorming, writing/executing plans, systematic-debugging, TDD, requesting/receiving code review, parallel-agent dispatch, verification-before-completion, git worktrees. Maps directly onto the core operating model. |
| **claude-mem** | Persistent cross-session memory + `make-plan`/`do`/`learn-codebase`/`mem-search`. This is the "Memory" leg of the harness — it's how a fresh session isn't a blank slate, and where the System-Evolution feedback record can live. |
| **code-review** | On-demand diff review at adjustable effort. The everyday evaluation gate. |
| **codex** | A *second, independent* model that reviews **and independently tests** your work adversarially — it reads the diff for a second opinion, and can write/run its own tests or reproduce the bug (a checker that *measures* beats one that only reads). The strongest cheap "eval" you can add before shipping anything risky. Optional (needs the Codex CLI), but recommended. |

## Built-in skills worth knowing (no install needed)

- **deep-research** — the engine for the *deep-research* profile.
- **excalidraw-diagram** — clean diagrams for the *creative-design* profile.
- Plus whatever ships with your Claude Code build (`/run`, `/verify`, `/code-review`, …).

## By-profile, opt-in

Install only on projects that need them — `/plugin install <name>@<marketplace>`:

| Profile | Useful add-ons |
|---|---|
| **software-dev** | Language LSP plugins (e.g. a TypeScript/Go/Python LSP), language dev plugins (e.g. `go-dev`), a CSS/UI plugin (e.g. `tailwind`) — match your stack only. |
| **devops-setup** | An error-monitoring skill/CLI (e.g. `sentry-cli`); cloud-provider MCPs for your hosting. |
| **marketing-outreach** | Your ESP/CRM MCP (e.g. Kit.com). |
| **general-admin** | Email/calendar + file-storage MCPs (e.g. Dropbox). |
| **creative-design** | excalidraw MCP (for the diagram skill); an image/video-generation MCP; a slide skill. |
| **data-crunching** | A code-execution/notebook tool; DB/SQL MCPs for your warehouse. |
| **deep-research** | Context7 (docs), and your client's web search/fetch. |

## Opt-in plugin packs (wired into `setup.sh`)

For convenience, two curated packs can be auto-installed (always the **latest** version from the
marketplace's GitHub repo). They're **off by default** — pass `--with-plugins`, or answer the
interactive prompt:

```bash
./setup.sh --profile software-dev --with-plugins dev-workflow,stack-lsp --target .
./setup.sh --update-plugins        # later: pull the latest for everything installed
```

| Pack | Marketplace(s) added | Plugins installed |
|---|---|---|
| `dev-workflow` | `shinpr/claude-code-workflows` + official | dev-workflows, dev-workflows-frontend, feature-dev, frontend-design, qodo-skills |
| `stack-lsp` *(example: Go + web)* | `gopherguides/gopher-ai`, `Piebald-AI/claude-code-lsps` + official | go-dev, tailwind, gopls, typescript-lsp, gopls-lsp |

`stack-lsp` is an **example** mirroring the original box — **swap the LSP/stack plugins for your
own languages** (a Python LSP, a Rust plugin, etc.). Marketplaces are registered only when you
actually select the pack, so unused ones never touch your config.

## A note on restraint (R10)

Every plugin is surface area to maintain and another thing that can drift. Install the universal
four, add a by-profile pack only when a project genuinely uses it, and remove what you stop
using. A prior setup had 500+ skills and followed none of them — more is not better.
