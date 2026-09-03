---
name: gimp-image-compositing-color-and-lighting-matching-techniques
abstract: "GIMP image compositing: color and lighting matching techniques"
type: reference
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

Step-by-step GIMP workflow for matching colors and lighting between composite images:

1. **Levels & Color Balance** → Colors > Levels (adjust black/white/gray), then Colors > Color Balance (shadows/midtones/highlights)
2. **Colorize** → Colors > Colorize to unify palette across images
3. **Shadows/Highlights** → Duplicate layer, use Filters > Light and Shadow > Drop Shadow and Dodge and Burn for lighting effects
4. **Layer Blending Modes** → Test Multiply, Overlay, Soft Light to blend composited layer
5. **Lighting Effects** → Filters > Light and Shadow > Lighting Effects for ambient light, adjust opacity and blending
6. **Merge Down** → When satisfied with all effects, merge layers (keep copies of original)

Key practice: Always duplicate layers before destructive filters; maintain non-destructive workflow as long as possible.
