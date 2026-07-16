# Example: Dispatch — weekly newsletter & outreach (marketing-outreach profile)

**Scenario.** Dispatch is a weekly product newsletter plus light outreach for a small SaaS —
issues are drafted as Markdown under `drafts/`, then sent via an ESP (a Kit/Mailchimp-style
service) where open and click rates are tracked. The operator is Nadia Rossi, a growth marketer
who tracks work in Linear. This folder shows the harness *layered onto that one outreach repo*:
the universal core is installed globally on Nadia's machine, and the project itself carries only
the marketing-outreach profile plus the project-specifics below.

**Set it up like this:**

```bash
# 1) Install the universal core once, globally (Nadia's machine, all projects):
./setup.sh --global --operator-name "Nadia Rossi" --operator-role "growth marketer"

# 2) Layer the marketing-outreach profile onto THIS repo (no core copied in — core is global):
./setup.sh --profile marketing-outreach --profile-only --target . \
  --operator-name "Nadia Rossi" --operator-role "growth marketer" \
  --tracker linear --with-hooks
```

**What to notice.**

- **`.harness/verify.conf` is the single source of truth for "shippable."** The profile says
  "copy is clean and links work — the actual SEND is gated by a human"; the conf makes that
  concrete for Dispatch (`cspell` over the draft, `lychee` over every link, and a `testsend`
  phase that is a *manual gate* — it never sends, it tells the human to send a test to themselves
  and eyeball it first). `verify.sh` and any human both read this one file, so commands never drift.
- **`CLAUDE.md` here is *only* the project-specifics layer.** It doesn't repeat the core or the
  profile — `setup.sh` stacks all three. It sharpens what "done" means for *outreach
  specifically*: every claim is verifiable, links and their UTM tags are correct, a **test send to
  yourself** lands before any broadcast, and unsubscribe + consent are respected.
- **"Done" is honest-and-safe, not just green.** A spell-clean draft is not a verified campaign.
  No fabricated stats, no dead or staging links, no `{{first_name}}` that renders empty, no send
  without a human approving both the copy *and* the audience count. Sending is irreversible, so
  the agent prepares and proves — the human pulls the trigger.
- **`--with-hooks` installs git guardrails** (secret-scan, protect-main, conventional-commit) so
  the no-secrets and atomic-commit rules are enforced deterministically — load-bearing here, where
  ESP API keys and a real subscriber export must *never* land in a commit.

**Files here:**

- `README.md` — this file.
- `CLAUDE.md` — the project-specifics layer (Dispatch's stack, "done," conventions, gotchas).
- `.harness/verify.conf` — the concrete verify phases for this newsletter & outreach repo.
