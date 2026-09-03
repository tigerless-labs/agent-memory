---
created: 2026-09-02T23:21:21.131124700Z
updated: 2026-09-02T23:21:21.131124700Z
weight: 1.0
last_accessed: 2026-09-02T23:21:21.131124700Z
access_count: 0
pinned: false
links: []
abstract: 2023-02-23 — User compositing niece (dressed as witch) with spooky castle PNG illustration in GIMP; already masked niece's image but lighting and colors didn't match; seeking techniques to harmonize lighting and color balance between the two images
---

## Project Overview
User wants to composite two images:
1. PNG illustration of a spooky castle
2. Photo of niece dressed as a witch

## Current State
- Already manually selected niece's image using selection tool
- Applied layer mask to remove niece's background
- Pasted niece's image onto castle illustration
- **Problem:** lighting and colors between the two images don't match well

## Recommended Techniques (GIMP)
1. **Adjust Levels and Color Balance** — Colors > Levels, Colors > Color Balance
2. **Apply Color Grade/Filter** — Colors > Colorize (adjust Hue, Saturation, Lightness)
3. **Add Shadows and Highlights** — Duplicate layer, use Filters > Light and Shadow > Drop Shadow, Dodge and Burn
4. **Use Layer Blending Mode** — Try Multiply, Overlay, Soft Light
5. **Apply Light Effects** — Filters > Light and Shadow > Lighting Effects to simulate ambient light

## Layer Merging Guidance
- Merge down when satisfied with changes on that layer
- Always keep original layers as copies before merging in case revisions needed
- Consider merging when: using adjustment layers, applying blending modes, finalizing shadow/highlight effects, finalizing light effects