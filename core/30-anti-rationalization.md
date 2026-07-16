<!-- CORE · anti-rationalization · universal -->
## Anti-Rationalization — the STOP table

These thoughts mean you are about to skip a rule. When you catch one, STOP and reset. Every row
is a real failure mode, generalized from work that shipped broken because someone thought it.

| The thought | The reality |
|---|---|
| "I'll verify it later." | Later doesn't happen. Verify is part of the work, not after it. |
| "I'll just fix this quick." | Quick fixes with no understanding cause fix-on-fix spirals. Understand first (Rule 1). |
| "It works in my head." | Prove it. Run it, render it, diff it, look at it. Evidence, not vibes (Rule 2). |
| "This is too small to check." | The small, unchecked change is exactly the one that ships broken. |
| "One example works, ship it." | Check every consumer/recipient/format/locale the change fans out to (Rule 3). |
| "I'll batch all of these into one change." | Atomic only. N concerns = N units. Batching hides regressions (Rule 4). |
| "The docs can wait." | Same anti-rationalization as 'tests can wait.' Docs ship with the change (Rule 6). |
| "It's a private repo, the key is fine here." | No live secret in any tracked file, ever. Private ≠ safe (Rule 8). |
| "This old research is in the way, I'll delete it." | Archive, never delete. It cost real effort to produce (Rule 9). |
| "Let me add a tool/skill to handle this." | What problem does it solve that the current setup can't? Keep the surface small (Rule 10). |
| "It's connected / it's in the rules, so I'm meant to use it." | Availability is not authorization. A named system is a pointer, not permission. Ask before the first write to anything outside this repo (core/10). |
| "The checklist is too long today." | The one time the checklist gets skipped is the one time something ships broken. |
| "I'll re-prompt the agent to simplify it." | Re-prompting rarely simplifies. If output is bloated, you collapse it yourself or it ships bloated. |

When in doubt, the move is always the same: **slow down by one step, produce the evidence, then
proceed.** Speed comes from not having to redo broken work, not from skipping the check.
