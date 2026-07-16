<!-- PROFILE · marketing-outreach -->
## Profile: Marketing & Outreach

**Use this profile when** the work touches real recipients or public channels: cold/warm email, newsletters, sequences, landing copy, social posts, campaign setup, list/segment management, or CRM/ESP operations. If a human will receive it, this profile applies.

### The non-negotiables (read first)

These override convenience every time. Sending is irreversible and reputational.

- **APPROVAL BEFORE SEND.** Never send, schedule, or publish to real recipients without an explicit human go-ahead on BOTH the final copy AND the audience. "Go ahead" on the draft is not approval to send — confirm the segment and the recipient count too. A scheduled send is a send; it needs the same approval. No exceptions, no "I'll just queue it."
- **Compliance is not optional.** Every email carries a working unsubscribe and a real physical/postal sender identity. From-name, from-address, and subject must be honest — no deceptive headers, no fake "Re:"/"Fwd:" baiting. Honor every opt-out and consent state; suppress unsubscribed and bounced addresses. Respect GDPR (lawful basis, consent records) and CAN-SPAM (clear ID, opt-out honored within the legal window). If you can't confirm consent for an address, it does not get mailed.
- **Personalization must be proven to render.** A broken `{{first_name}}` ("Hi {{first_name}},") ships embarrassment to thousands and torches trust. Every merge token is verified against a real test profile before send — including the fallback for missing values.
- **Never invent facts.** No fabricated stats, claims, case studies, testimonials, logos, or "trusted by." Every factual claim traces to a real source (R9). When unsure, leave it out or ask.

### What "done" and "verified" mean here

Sharpening R2 (prove it), R3 (whole chain), R5 (verify before done): a campaign is **verified** only when —

- A real **test send** was opened in the actual destination inbox client (not just the editor preview) — desktop and mobile if the audience uses both.
- **Every merge token rendered** correctly with a real test profile, including the missing-value fallback.
- **Every link was clicked** and lands where intended; UTM parameters are present and correct; no naked tracking redirects that break.
- The **audience/segment count was sanity-checked** against expectation — a 50× jump means a bad filter, not a great day.
- A **human approved** the final copy and the audience, and that approval is recorded.

"It looks right in the editor" is **not** verified. R3 fan-out applies: walk **each segment, each A/B variant, and each locale** — proving one variant renders does not prove the others do.

### Quality gates (tick every box before requesting approval)

- [ ] Spelling and grammar clean; read aloud once.
- [ ] Brand voice matches the voice guide (tone, reading level, banned words).
- [ ] Subject line set; **preview/preheader text** set (not left as body spillover).
- [ ] All links tested and resolve; UTM tags correct and consistent.
- [ ] Merge tokens render against a real test profile; fallbacks verified.
- [ ] Unsubscribe link present and working; sender identity/postal address present.
- [ ] Audience/segment selected and **count confirmed**; suppressions applied.
- [ ] Send time and timezone set deliberately (not "now" by accident).
- [ ] Both A/B variants checked end-to-end, not just variant A.
- [ ] Human approval recorded (who, when, on which final version).

### Failure modes to guard against

- **Sending to the wrong or whole list** — a missed segment filter blasts everyone.
- **Broken personalization** — empty or literal `{{token}}` in the recipient's inbox.
- **Dead or wrong links** — staging URLs, expired offers, missing UTMs, wrong landing page.
- **Over-claiming / fabricated stats** — unverifiable numbers, invented testimonials.
- **Missing unsubscribe / sender identity** — an instant compliance breach.
- **Spammy subject** — all-caps, "FREE!!!", spam-trigger words that hurt deliverability and **domain reputation**, which is slow and expensive to repair.
- **Duplicate sends** — re-running a broadcast, double-adding to a sequence.
- **Ignoring opt-outs / bounces** — mailing suppressed addresses is both rude and illegal.

### Recommended skills & tools (keep the surface small — R10)

- **Research before you write.** Web search for prospect/company facts; the deep-research skill for account-level research. Cite sources; never fill gaps with invention.
- **ESP/CRM via its MCP.** Use the email/ESP MCP (e.g. `<your-ESP-MCP>`) for list/segment ops, tags/subscribers, broadcast/sequence creation, and stats — but **create as draft**, never auto-send. Pull `get_stats` after a send to report, not to decide unilaterally.
- **Brand-voice file.** Keep a `voice/brand-voice.md` (tone, audience, do/don't, banned phrases) and write to it; use claude-mem to persist recurring voice/positioning decisions across sessions.
- **Tool docs only via Context7.** Use Context7 to look up ESP/MCP API details — not for marketing strategy.
- **The flow is always:** research → draft → self-check against quality gates → **human approve** → send. The agent prepares and proves; the human pulls the trigger.

### Addendum to the STOP table

| Thought | Reality |
|---|---|
| "I'll just send the test to the whole list." | That's a live send to real people. Test sends go to *your own* seed addresses only. Wrong recipient field = irreversible. |
| "The merge tag is probably fine." | "Probably" ships "Hi {{first_name}}," to thousands. Render it against a real profile or it's not verified (R2). |
| "One more claim makes it stronger." | An unverifiable claim makes it a liability. No source, no claim (R9). Over-claiming kills trust faster than weak copy. |
| "I'll add the unsubscribe later." | Later is after it sent. No unsubscribe = compliance breach + spam complaints + domain damage. It ships in the same unit or it doesn't ship (R6). |
| "Just schedule it, approval can come after." | A scheduled send is a send. Approval is a precondition, never a follow-up. |
