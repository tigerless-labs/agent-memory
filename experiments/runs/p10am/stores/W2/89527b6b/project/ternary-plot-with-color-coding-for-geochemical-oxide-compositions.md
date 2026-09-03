---
name: ternary-plot-with-color-coding-for-geochemical-oxide-compositions
abstract: Ternary plot with color coding for geochemical oxide compositions
type: procedure
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

**Goal:** Visualize compositional relationships across Na2O, FeO, CaO, and other oxides with sample-specific color coding

**Dataset:** 2020_12_18_noc geochemical analysis (25 samples)

**Approach:** Python with matplotlib + scipy.spatial.ConvexHull
- Normalize oxide pairs to 100%
- Transform to Cartesian ternary coordinates
- Scatter plot with color map indexed by sample number or composition variable

**Status (2023-05-20):** Code outline drafted; implement triangle transform and legend/labeling
