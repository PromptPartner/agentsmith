<!-- PROFILE · creative-design -->
## Profile: Creative & Design

**Use this profile when** the deliverable is visual — architecture/workflow/IA diagrams, slide decks, brand and visual artifacts, generated images or video, or simple graphics. The artifact IS the work product; how it looks and reads is the spec.

### What "done" and "verified" mean here

Sharpens R2/R3/R5 for visual work. A visual is **not** done when the source looks right — source/JSON has no overlap, no clipping, no kerning, no real color. Done means the **final rendered artifact**, exported in its target format (PNG/PDF/slide/MP4) and viewed **at its real size and aspect ratio**, reads clearly:

- nothing overlapping, clipped, or off-canvas;
- text legible at the size it will actually be seen (projected slide, thumbnail, full-bleed);
- alignment and spacing are deliberate, not accidental;
- colors and type are on-brand;
- and it **communicates the one point it exists to make**.

"The source looks fine, ship it" is the cardinal sin of this profile — visual bugs only appear once rendered. Open the export and look at it. Every time. That look IS the verification (R5); without it the work is unverified.

### Brand & craft standards (load-bearing)

Adhere to the project's defined brand. Do not freelance the look.

**If the palette or typeface below still reads `[TODO: set …]`, nobody has told you the brand yet.
Ask for it before you make anything visual — it's a ten-second answer, and guessing it makes every
deliverable wrong in a way that only shows up after it ships. Then offer to write the answer into
this file so the next session doesn't have to ask again.**

- **Palette:** {{BRAND_PALETTE}} — use these colors and only these (plus neutral white/ink). No off-brand hues, no "close enough" approximations, no decorative gradients unless the brand calls for them.
- **Typography:** {{BRAND_FONT}} — a legible, non-decorative font. No hand-script or novelty faces for body or labels.
- **Clean only:** straight lines and clean edges (no sketchy/hand-drawn style unless explicitly requested), consistent spacing, snapped alignment, one clear visual hierarchy (size/weight/color signal importance — not clutter).
- **Less beats more:** a diagram that says one thing clearly beats one that crams in five. Cut boxes, arrows, and labels that don't earn their place.
- **A deliverable diagram is rendered with the diagram skill**, not hand-assembled or hand-waved. Use the proper tool so lines stay straight and fonts stay legible.

### Process

1. **Draft to think.** A quick sketch, a mermaid pass, or a thumbnail to settle structure and flow. Cheap, disposable, fast.
2. **Produce the clean shipped artifact** with the proper tool (diagram skill, deck tool, media MCP). One concern per revision — R4. Don't bundle a layout change, a copy change, and a recolor into one murky edit.
3. **Render and eyeball** at target size/format. Fix what the render exposes. Repeat until it reads.
4. **Match the existing visual language** of the project before inventing a new one — R1. Look at prior diagrams/decks/assets and stay consistent with them.
5. **Keep sources and exports in a durable location.** The editable source (Excalidraw file, deck source, prompt + seed) ships alongside the export so the artifact can be revised later.

### Quality gates

Tick every box before calling a visual done:

- [ ] On-brand palette — only {{BRAND_PALETTE}}, no stray colors.
- [ ] On-brand typography — {{BRAND_FONT}}, legible, non-decorative.
- [ ] Clean lines and snapped alignment; consistent spacing.
- [ ] Legible at the actual target size (zoom to real scale and read it).
- [ ] Nothing clipped, overlapping, or off-canvas.
- [ ] The artifact communicates its intended single message.
- [ ] Exported in every required format, and **each export opened and checked** (R3).
- [ ] Source/editable file kept in a durable location (R9 — prior versions archived, never deleted).
- [ ] Rendered output actually eyeballed — not approved from the source view.

### Failure modes to guard against

- Off-brand colors or fonts sneaking in ("this blue is basically the brand blue").
- Sketchy/hand-drawn lines when clean was wanted.
- Overlapping or clipped text the source view hid.
- Labels legible in the editor but illegible at projected/thumbnail size.
- Cluttered diagrams where the point drowns in boxes and arrows.
- Shipping from the source/JSON view without ever opening the export.
- Losing earlier asset versions during a "cleanup" — archive, never delete (R9).
- Inventing a new look instead of matching the project's existing visual language (R1).

### Recommended skills & tools

Keep the toolkit tight (R10):

- **excalidraw-diagram skill** — clean architecture/workflow/IA diagrams: straight lines, legible fonts, brand palette. The default for any deliverable diagram.
- **wowerpoint skill** — turn a document/report into a slide deck.
- **Image/video generation MCP** (e.g. Higgsfield) — generated visual assets, marketing media, hero images.
- **Brand/palette guide file** — the single source of truth for {{BRAND_PALETTE}} and {{BRAND_FONT}}; consult it before picking any color or font.
- **claude-mem** — brand memory: recall prior decisions, recurring layouts, and what "on-brand" means across sessions.

**If `excalidraw-diagram` isn't installed**, still render a deliverable diagram with a real tool — never hand-wave or ASCII it. The "diagram is rendered with the diagram skill" standard holds with or without that specific skill.

### Addendum to the STOP table

| Thought | Reality |
|---------|---------|
| "The JSON/source looks fine, ship it" | Visual bugs only show when rendered. Export it, open it at real size, then judge. |
| "Close enough on the brand color" | Off-brand is off-brand. Use the exact value from the brand guide — eyeballed hues drift. |
| "Hand-drawn style is fine here" | Default is clean: straight lines, `roughness: 0`. Sketchy only when explicitly asked. |
| "The labels are probably readable" | "Probably" isn't verified. Zoom to target size and actually read every label. |
| "I'll delete the old version to tidy up" | R9 — archive prior versions, never delete. The old export may be the one that's needed. |
