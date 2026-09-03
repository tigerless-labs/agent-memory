---
name: optimize-race-car-dynamics-balance-polar-inertia-roll-inertia-and-cg-height-for
abstract: "Optimize race car dynamics: balance polar inertia, roll inertia, and CG height for smooth and rough tracks"
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

## Design Parameters

**Polar inertia**: resistance to rotation around vertical axis; higher values improve stability during high-speed cornering.

**Roll inertia**: resistance to rotation around longitudinal axis; higher values improve rollover resistance and traction during cornering.

**CG height**: vertical location of center of mass; lower values improve stability and rollover resistance.

## Track Performance Trade-offs

- **Smooth tracks**: favor lower inertias for agility and maneuverability
- **Rough tracks**: favor higher inertias for stability and control
- **Challenge**: finding compromise that works acceptably on both

## Testing Methodology

1. Gather track data: layout, surface conditions, performance factors
2. Create mathematical model to predict behavior
3. Test different inertia levels on-track (adjust suspension, body, components)
4. Iterate design and testing until achieving best compromise
5. Must test on both smooth and rough sections to validate trade-off

The optimal balance depends on specific vehicle design, track conditions, and driver preferences.
