# What's built in

The core rules and the profiles are the harness's *judgment*. This page is its *machinery* — the
conveniences setup can install for you, each solving a specific recurring friction. None is
required for the rules to work; reach for them as the need shows up. Everything here is opt-in via
a `setup.sh` flag (same flags on `setup.ps1`).

If you're evaluating what the harness *does* rather than what it *believes*, this is the catalog.
For the reasoning behind any of it, the cross-links point back to the doc that explains why.

- **Setup wizard** — `setup.sh --wizard` (or bare `./setup.sh`) asks the questions interactively
  and builds + runs the right command, printing it first so you learn the flags.
- **Native Windows setup** — `setup.ps1` is a PowerShell port of `setup.sh` with the same flags
  and behaviour (including `--wizard`), so Windows users don't need Git Bash just to set up.
- **Bundled skill pack** — `setup.sh --with-skills` installs six self-contained, script-aware,
  invoke-by-name skills: `/handoff`, `/verify`, `/harness-doctor`, `/harness-help`, `/new-research`,
  `/new-feedback`. They prefer a project-local `scripts/<x>.sh` when present, else run inline, so
  they work globally, in a harness project, or in a bare repo. Project mode installs them into
  `<project>/.claude/skills/`; `--global` into `~/.claude/skills/`. See [`skills/README.md`](../skills/README.md)
  and [`skills/RECOMMENDED.md`](../skills/RECOMMENDED.md).
- **Feedback / self-improvement loop** — a `docs/feedback/` convention + `scripts/new-feedback.sh`
  scaffolder makes the System-Evolution loop a one-liner (mirrors `new-research.sh`); see
  [`feedback/README.md`](feedback/README.md) and the recurring harness-review checkpoint.
- **CLAUDE.md leanness lint** — `scripts/lint-leanness.sh` (and `setup.sh --doctor`) warn when the
  assembled static context grows past its budget, nudging knowledge into skills/docs. The *why* is
  in [`04-why-your-agent-ignored-the-rule.md`](04-why-your-agent-ignored-the-rule.md).
- **Handoff hooks** — `setup.sh --with-handoff-hooks` installs a reliable "handoff"-keyword prompt
  hook plus a best-effort context-% nudge (the % part is fragile by design — see `hooks/README.md`).
- **Design-system scaffold** — `setup.sh --design-system stub|catalog:<brand>|generate` (software-dev
  UI projects) drops a root `DESIGN.md` the agent reads before building UI: an empty template to fill,
  a ready-made one from the [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) catalog,
  or the ui-ux-pro-max generate steps. Pair it with `--with-ui-design-hook` — a once-per-session
  PreToolUse nudge to consult `DESIGN.md` on UI edits. Why it exists:
  [`07-how-to-pick-a-profile.md`](07-how-to-pick-a-profile.md) (product UI is `software-dev`).
- **Guardrail hooks** — `scripts/install-git-hooks.sh` / `setup.sh --with-hooks`: secret-scan +
  protect-main + conventional-commit (default), branch-naming + tests-green (opt-in). These are the
  deterministic guards behind the rules ([`14-safety-model.md`](14-safety-model.md) covers the posture).
- **Profile-aware `verify.conf` presets** — setup drops a starter `.harness/verify.conf` matched to
  the chosen profile(s) (dev → build/test; docs → spell/links; data → row-count reconcile).
- **CI workflow (shipped example)** — [`.github/workflows/verify.yml`](../.github/workflows/verify.yml)
  runs the same `scripts/verify.sh` on every push/PR (plus a Windows `setup.ps1` job), so "green on my
  laptop" and "green in CI" can't drift. Setup does **not** install it into your project — copy it as a
  starting point. The **CI section below** covers why it's worth it, hosted-vs-self-hosted runners, and
  what *not* to run it on.
- **MCP picker** — `setup.sh --with-mcp <name[,name]>` writes the right block from
  `config/mcp.example.json` into the project's `.mcp.json`.
- **rtk output compressor** — `setup.sh`/`setup.ps1 --with-rtk` (default-ON for `software-dev` /
  `devops-setup`; `--no-rtk` to skip) installs [`rtk`](https://github.com/rtk-ai/rtk) and runs its
  own `rtk init -g` to wire a PreToolUse hook that compresses noisy CLI output 60–90% before it
  reaches context. A binary + hook, not a plugin — see [`../config/plugins.md`](../config/plugins.md).
- **Org-policy variant** — `sudo setup.sh --org-policy` installs a managed `CLAUDE.md` at the OS
  policy path (applies to all users on a shared box) + a stricter, no-bypass settings profile.
- **Cowork / claude.ai export** — `setup.sh --export-instructions` emits a single paste-ready
  instructions blob for surfaces without on-disk config (web Projects, Cowork). See
  [`12-platforms-and-tools.md`](12-platforms-and-tools.md) for which surfaces need it.

**Two more worth knowing about**, not flags but shipped assets: five **worked example projects**
in [`examples/`](../examples/README.md) (each a filled `CLAUDE.md` + real `verify.conf` for one
profile), and **`--self-update`**, which pulls a newer harness and re-assembles your managed
`CLAUDE.md` blocks in one step (README → "Keeping the harness current").

## Continuous integration — why, where, and what *not* to run it on

**Why bother.** R5 is *verify before you call it done*; CI is what stops that from depending on a
human remembering. Every push re-runs the whole gate on a clean machine, so a check that only passed
because of something uncommitted on your laptop gets caught. A discipline harness whose own discipline
is manual isn't credible — and the same holds for your project.

**Point CI at `verify.sh`, not a re-listed set of checks.** `.harness/verify.conf` is the single
definition of "shippable"; if the workflow duplicated that list, the two would drift and "green in CI"
would stop meaning "green locally." Add a phase to `verify.conf` and it runs everywhere with no YAML
edit. The shipped [`verify.yml`](../.github/workflows/verify.yml) is a copy-ready example of exactly
that.

**Hosted GitHub Actions vs a self-hosted runner** — choose by what the job actually needs:

| Hosted **GitHub Actions** when… | **Self-hosted runner** when… |
|---|---|
| Public repo (Actions minutes are free) or ordinary private use | Long/frequent builds would blow the minutes budget |
| A clean Linux / Windows / macOS box is all you need | You need a GPU, a big warm cache, or a pinned OS/toolchain |
| No private-network access required | The job must reach an internal registry, VPN, or licensed tool |
| You want zero runner maintenance | You'll own patching, isolation, and security of that box |

**Default to hosted** — free for public repos, no box to patch. Reach for self-hosted only when a row
on the right actually forces it; a self-hosted runner is real attack surface, especially if it ever
runs untrusted PRs.

**Don't run the heavy gate on docs that can't break the build — but *always* secret-scan.**
Spec / plan / handoff docs don't compile or test, so running build/test/lint on a plan-only change
just burns minutes and paints meaningless red X's. Path-filter the heavy gate to code; run a fast
**secret-scan on *everything*** — a key can leak into a Markdown plan as easily as into code, so that
one check never gets a path exception. Two small workflows do it cleanly:

```yaml
# .github/workflows/verify.yml — heavy gate, skipped on docs/plan-only changes
on:
  pull_request:
    paths-ignore: ['**/*.md', 'specs/**', 'plans/**', '.planning/**', 'docs/**']
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bash scripts/verify.sh
```
```yaml
# .github/workflows/secret-scan.yml — always runs, no path filter, ever
on: [push, pull_request]
jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bash scripts/secret-scan.sh
```

One gotcha: if `verify` is a **required** status check, a `paths-ignore` skip leaves the PR waiting on
a check that never reports — either don't mark it required, or add a tiny always-passing job for the
docs-only path. (In this repo the planning docs are gitignored so they never reach CI at all; in *your*
project specs and plans are usually tracked, which is exactly where this bites — found in real use.)
