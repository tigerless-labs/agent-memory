---
name: composite-niece-s-witch-photo-with-spooky-castle-illustration-using-gimp
abstract: Composite niece's witch photo with spooky castle illustration using GIMP
type: fact
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-02-23
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

**Project:** Image compositing in GIMP

**Goal:** Layer niece dressed as witch into PNG illustration of spooky castle

**Status (2023-02-23):** In progress. Initial composite created but lighting and color matching between the two images didn't align well.

**Workflow completed:**
- Manual selection of niece's image using selection tool
- Applied layer mask to remove background
- Pasted composited image into castle illustration

**Techniques to improve composite (GIMP):**

1. **Adjust Levels & Color Balance**
   - Colors > Levels: adjust black/white/gray sliders to match castle tone
   - Colors > Color Balance: adjust shadows/midtones/highlights to match palette

2. **Apply Color Grade/Filter**
   - Colors > Colorize on both layers
   - Match Hue, Saturation, Lightness to unify palette

3. **Add Shadows & Highlights**
   - Duplicate niece layer → name 'Shadows and Highlights'
   - Filters > Light and Shadow > Drop Shadow (subtle, matching castle lighting)
   - Filters > Light and Shadow > Dodge and Burn (highlights)

4. **Layer Blending Modes**
   - Experiment with Multiply, Overlay, Soft Light to integrate niece image with castle

5. **Lighting Effects**
   - Duplicate layer → name 'Light Effect'
   - Filters > Light and Shadow > Lighting Effects
   - Adjust layer opacity and blending mode for subtle effect

**When to merge down:** After each complete effect stage, if satisfied and no further tweaks planned. Always keep layer copies as backup before merging.

**Tools:** GIMP
