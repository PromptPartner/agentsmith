# AgentSmith site design

The single-page `site/` launch page uses PromptPartner's visual system. Keep it static and deployable by copying the `site/` directory to a web root.

- **Palette:** navy `#14213D`, amber `#FCA311`, white `#FFFFFF`, grey `#E5E5E5`. Navy is structure; one amber action or rule per section. Amber text on white is avoided.
- **Type:** bundled SIL OFL Space Grotesk for headings and Inter for body. System fallbacks remain legible if fonts fail.
- **Logo:** the supplied PromptPartner white lockup on navy. Do not redraw or recolor it. AgentSmith is the product name in text.
- **Layout:** a navy hero with a working guided-setup terminal example; light sections for the process, proof, support, and two equal setup-route cards. Maximum content width 1120 px. Single column below 700 px.
- **Interaction:** semantic links and anchor navigation, visible keyboard focus, no JavaScript requirement, no animation dependency. A horizontal diagram may scroll on narrow screens; an adjacent ordered text description carries the same information.
- **Evidence:** claims link to the First Verified Loop bundle or the registry. The 14 other agent clients are certification targets with pending status.
- **Deployment:** `site/` is the artifact. Its internal links are relative; documentation links point to the public GitHub repository. No analytics, cookies, account system, or runtime package.

The editable `site/assets/agentsmith-flow.svg` is the canonical process diagram for the README, docs, and site. Change it once and review all three consumers.
