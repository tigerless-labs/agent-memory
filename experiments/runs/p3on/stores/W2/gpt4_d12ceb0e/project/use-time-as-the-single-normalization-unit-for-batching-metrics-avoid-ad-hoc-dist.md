---
name: use-time-as-the-single-normalization-unit-for-batching-metrics-avoid-ad-hoc-dist
abstract: Use time as the single normalization unit for batching metrics (avoid ad-hoc distance-to-time conversion)
type: decision
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

When evaluating order batching feasibility, convert all relevant metrics to a single time-based plane rather than keeping distance and time separate. This requires an ETA engine that can predict travel time between any two points. Use time as the common unit because: (1) it directly reflects customer experience, (2) it's more intuitive than abstract distance metrics, (3) it enables consistent comparison across route efficiency and wait time factors. Avoid naive constant-speed conversions (distance ÷ average_speed) which lose route-specific information.
