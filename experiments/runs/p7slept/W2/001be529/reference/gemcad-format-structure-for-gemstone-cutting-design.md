---
name: gemcad-format-structure-for-gemstone-cutting-design
abstract: GemCad format structure for gemstone cutting design
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

GemCad is a format/tool for designing faceted gemstones. Structure includes:

- **Header (H)**: Version, index count, index angle, refractive index, gemstone name, design notes
- **Facet definitions (a lines)**: Angle, height ratio, index positions, facet name, adjacent facets, symmetry group
- **Notes (F)**: Additional design details and optimization information

Example: Dalan Hargrave's Fantasy Cut (GemCad 5.0) - designed for Kashmir Blue Synthetic corundum, 8mm ring stones, RI 1.7+. 72-index design with pavilion, girdle, and crown facets.

**When explaining GemCad templates**: Show structure with labeled placeholders rather than copying full examples—helps users understand the format schema.
